import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

from .parsers.archive import ArchiveParser
from .parsers.base import ParserError
from .parsers.office import OfficeParser
from .parsers.pdf import PdfParser
from .parsers.txt import TxtParser

SUPPORTED_EXTENSIONS = {
    ".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".tgz", ".gz", ".rar", ".7z",
}

ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tgz", ".gz", ".rar", ".7z"}


@dataclass
class Match:
    keyword: str
    start: int
    end: int
    context: str
    line_number: int = 0


@dataclass
class FileResult:
    file_path: str
    matches: list[Match] = field(default_factory=list)
    error: Optional[str] = None


def _get_parser(file_path: str, ocr_enabled: bool = False, check_archives: bool = True):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == ".txt":
        return TxtParser()
    elif ext == ".pdf":
        return PdfParser(ocr_enabled=ocr_enabled)
    elif ext in (".docx", ".pptx", ".xlsx", ".doc", ".xls", ".ppt"):
        return OfficeParser()
    elif ext in ARCHIVE_EXTENSIONS and check_archives:
        return ArchiveParser(inner_parser_factory=lambda e: _parser_by_ext(e, ocr_enabled))
    return None


def _parser_by_ext(ext: str, ocr_enabled: bool = False):
    if ext == ".txt":
        return TxtParser()
    elif ext == ".pdf":
        return PdfParser(ocr_enabled=ocr_enabled)
    elif ext in (".docx", ".pptx", ".xlsx", ".doc", ".xls", ".ppt"):
        return OfficeParser()
    return None


def _throttled_print(last_time: float, min_interval: float, msg: str) -> float:
    now = time.time()
    if now - last_time >= min_interval:
        sys.stdout.write(f"\r{msg}")
        sys.stdout.flush()
        return now
    return last_time


def _format_scan_progress(total: int, checked: int, hits: int, match_count: int, fail_count: int) -> str:
    pct = checked * 100 // total if total > 0 else 0
    filled = checked * 10 // total if total > 0 else 0
    bar = "█" * filled + "░" * (10 - filled)
    return f"扫描中 [{bar}] {pct}% | 待检测: {total} | 已检测: {checked} | 命中: {hits} | 匹配: {match_count} | 失败: {fail_count}"


def discover_files(dir_path: str, extensions: Optional[set] = None, progress_callback: Optional[Callable[[int], None]] = None) -> list[str]:
    ext_filter = extensions or SUPPORTED_EXTENSIONS
    result = []
    for root, _dirs, files in os.walk(dir_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            _, ext = os.path.splitext(fname)
            if ext.lower() in ext_filter:
                result.append(fpath)
                if progress_callback is not None:
                    progress_callback(len(result))
    return sorted(result)


def _compute_line_number(text: str, char_pos: int) -> int:
    return text[:char_pos].count('\n') + 1


def _match_keywords(text: str, keywords: list[str]) -> list[Match]:
    matches = []
    for keyword in keywords:
        if not keyword:
            continue
        if keyword.isascii() and keyword.isalpha():
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            for m in pattern.finditer(text):
                matches.append(Match(
                    keyword=keyword,
                    start=m.start(),
                    end=m.end(),
                    context="",
                    line_number=_compute_line_number(text, m.start()),
                ))
        else:
            start = 0
            while True:
                idx = text.find(keyword, start)
                if idx == -1:
                    break
                matches.append(Match(
                    keyword=keyword,
                    start=idx,
                    end=idx + len(keyword),
                    context="",
                    line_number=_compute_line_number(text, idx),
                ))
                start = idx + 1
    matches.sort(key=lambda m: m.start)
    return matches


def _extract_context(text: str, start: int, end: int, context_chars: int = 50) -> str:
    ctx_start = max(0, start - context_chars)
    ctx_end = min(len(text), end + context_chars)
    return text[ctx_start:ctx_end]


def scan_single_file(
    file_path: str,
    keywords: list[str],
    context_chars: int = 50,
    ocr_enabled: bool = False,
    check_archives: bool = True,
) -> FileResult:
    parser = _get_parser(file_path, ocr_enabled, check_archives)
    if parser is None:
        return FileResult(file_path=file_path, error="不支持的文件格式")
    try:
        text = parser.parse(file_path)
    except ParserError as e:
        return FileResult(file_path=file_path, error=str(e))
    except Exception as e:
        return FileResult(file_path=file_path, error=f"解析失败: {e}")

    raw_matches = _match_keywords(text, keywords)
    for m in raw_matches:
        m.context = _extract_context(text, m.start, m.end, context_chars)
    return FileResult(file_path=file_path, matches=raw_matches)


def _worker_task(args: tuple) -> FileResult:
    file_path, keywords, context_chars, ocr_enabled, check_archives = args
    return scan_single_file(file_path, keywords, context_chars, ocr_enabled, check_archives)


def scan_directory(
    dir_path: str,
    keywords: list[str],
    context_chars: int = 50,
    num_workers: int = 1,
    ocr_enabled: bool = False,
    check_archives: bool = True,
    verbose: bool = False,
) -> dict:
    _last_disc_time = 0.0

    def _disc_cb(count: int):
        nonlocal _last_disc_time
        _last_disc_time = _throttled_print(_last_disc_time, 5.0, f"发现文件中... 已发现: {count}")

    files = discover_files(dir_path, progress_callback=_disc_cb)
    total = len(files)
    if total > 0:
        sys.stdout.write(f"\r发现文件中... 已发现: {total}\n")
        sys.stdout.flush()

    results = []
    failures = []
    checked = 0
    hits = 0
    match_count = 0
    fail_count = 0
    _last_scan_time = 0.0

    if num_workers <= 1:
        for idx, fpath in enumerate(files):
            fr = scan_single_file(fpath, keywords, context_chars, ocr_enabled, check_archives)
            checked += 1
            if fr.error:
                failures.append(fr)
                fail_count += 1
                if verbose:
                    print(f"  [失败] {fpath}: {fr.error}")
            elif fr.matches:
                results.append(fr)
                hits += 1
                match_count += len(fr.matches)
                if verbose:
                    print(f"  [命中] {fpath}: {len(fr.matches)} 处匹配")
            msg = _format_scan_progress(total, checked, hits, match_count, fail_count)
            if idx == len(files) - 1:
                sys.stdout.write(f"\r{msg}\n")
                sys.stdout.flush()
            else:
                _last_scan_time = _throttled_print(_last_scan_time, 5.0, msg)
    else:
        tasks = [
            (fpath, keywords, context_chars, ocr_enabled, check_archives)
            for fpath in files
        ]
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_worker_task, t): t[0] for t in tasks}
            done_count = 0
            for future in as_completed(futures):
                fpath = futures[future]
                try:
                    fr = future.result()
                except Exception as e:
                    fr = FileResult(file_path=fpath, error=f"worker 异常: {e}")
                checked += 1
                done_count += 1
                if fr.error:
                    failures.append(fr)
                    fail_count += 1
                    if verbose:
                        print(f"  [失败] {fpath}: {fr.error}")
                elif fr.matches:
                    results.append(fr)
                    hits += 1
                    match_count += len(fr.matches)
                    if verbose:
                        print(f"  [命中] {fpath}: {len(fr.matches)} 处匹配")
                msg = _format_scan_progress(total, checked, hits, match_count, fail_count)
                if done_count == len(futures):
                    sys.stdout.write(f"\r{msg}\n")
                    sys.stdout.flush()
                else:
                    _last_scan_time = _throttled_print(_last_scan_time, 5.0, msg)

    results.sort(key=lambda r: r.file_path)
    failures.sort(key=lambda r: r.file_path)
    return {"results": results, "failures": failures}
