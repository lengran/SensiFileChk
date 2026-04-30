import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from typing import Optional

from .parsers.archive import ArchiveParser, MAX_SIZE
from .parsers.base import ParserError
from .parsers.office import OfficeParser
from .parsers.pdf import PdfParser
from .parsers.txt import TxtParser

SUPPORTED_EXTENSIONS = {
    ".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".tgz", ".gz", ".rar", ".7z",
}

ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tgz", ".gz", ".rar", ".7z"}

MAX_CONCURRENT_BYTES = 1024 * 1024 * 1024
ARCHIVE_SIZE_MULTIPLIER = 5


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


def _format_discovery(count: int) -> str:
    return f"发现文件中 | 待检测文件: {count}"


def _format_progress(checked: int, total: int, hits: int, match_count: int, fail_count: int, elapsed: float) -> str:
    pct = checked / total * 100 if total > 0 else 0.0
    return f"扫描中 | 已检测: {checked}/{total} ({pct:.1f}%) | 命中: {hits} | 匹配: {match_count} | 失败: {fail_count} | 已用时: {elapsed:.1f}s"


def _get_file_size(fpath: str) -> int:
    try:
        return os.path.getsize(fpath)
    except OSError:
        return 0


def _estimate_bytes_from_size(raw_size: int, ext: str) -> int:
    if ext.lower() in ARCHIVE_EXTENSIONS:
        return raw_size * ARCHIVE_SIZE_MULTIPLIER
    return raw_size


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


def _process_result(fr, results, failures, verbose):
    if fr.error:
        failures.append(fr)
        if verbose:
            print(f"  [失败] {fr.file_path}: {fr.error}")
        return False, 0
    elif fr.matches:
        results.append(fr)
        if verbose:
            print(f"  [命中] {fr.file_path}: {len(fr.matches)} 处匹配")
        return True, len(fr.matches)
    return False, 0


def scan_directory(
    dir_path: str,
    keywords: list[str],
    context_chars: int = 50,
    num_workers: int = 1,
    ocr_enabled: bool = False,
    check_archives: bool = True,
    verbose: bool = False,
) -> dict:
    results = []
    failures = []
    checked = 0
    hits = 0
    match_count = 0
    fail_count = 0
    _last_time = 0.0
    _start_time = time.time()

    file_list = []

    for root, _dirs, dir_files in os.walk(dir_path):
        for fname in dir_files:
            _, ext = os.path.splitext(fname)
            if ext.lower() not in SUPPORTED_EXTENSIONS:
                continue
            file_list.append(os.path.join(root, fname))
        msg = _format_discovery(len(file_list))
        _last_time = _throttled_print(_last_time, 5.0, msg)

    total = len(file_list)
    if total > 0:
        sys.stdout.write(f"\r{_format_discovery(total)}\n")
        sys.stdout.flush()

    def _handle_fr(fr):
        nonlocal checked, hits, match_count, fail_count
        checked += 1
        is_hit, n_matches = _process_result(fr, results, failures, verbose)
        if fr.error:
            fail_count += 1
        elif is_hit:
            hits += 1
            match_count += n_matches

    def _print_progress():
        nonlocal _last_time
        msg = _format_progress(checked, total, hits, match_count, fail_count, time.time() - _start_time)
        _last_time = _throttled_print(_last_time, 5.0, msg)

    if num_workers <= 1:
        for fpath in file_list:
            fr = scan_single_file(fpath, keywords, context_chars, ocr_enabled, check_archives)
            _handle_fr(fr)
            _print_progress()
    else:
        large_files = []
        try:
            pending = {}
            inflight_bytes = 0
            idx = 0
            with ProcessPoolExecutor(max_workers=num_workers) as executor:

                while idx < len(file_list):
                    fpath = file_list[idx]
                    raw_size = _get_file_size(fpath)
                    if raw_size > MAX_SIZE:
                        large_files.append(fpath)
                        idx += 1
                        continue
                    _, ext = os.path.splitext(fpath)
                    est_bytes = _estimate_bytes_from_size(raw_size, ext)

                    while inflight_bytes + est_bytes > MAX_CONCURRENT_BYTES and pending:
                        done_set, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
                        for future in done_set:
                            f, eb = pending.pop(future)
                            inflight_bytes -= eb
                            try:
                                fr = future.result()
                            except BrokenProcessPool:
                                large_files.append(f)
                                continue
                            except Exception as e:
                                fr = FileResult(file_path=f, error=f"worker 异常: {e}")
                            _handle_fr(fr)

                    future = executor.submit(_worker_task, (fpath, keywords, context_chars, ocr_enabled, check_archives))
                    pending[future] = (fpath, est_bytes)
                    inflight_bytes += est_bytes
                    idx += 1

                    done_set = {f for f in pending if f.done()}
                    for future in done_set:
                        f, eb = pending.pop(future)
                        inflight_bytes -= eb
                        try:
                            fr = future.result()
                        except BrokenProcessPool:
                            large_files.append(f)
                            continue
                        except Exception as e:
                            fr = FileResult(file_path=f, error=f"worker 异常: {e}")
                        _handle_fr(fr)

                    _print_progress()

                for future in as_completed(pending):
                    f, eb = pending.pop(future)
                    inflight_bytes -= eb
                    try:
                        fr = future.result()
                    except BrokenProcessPool:
                        large_files.append(f)
                        continue
                    except Exception as e:
                        fr = FileResult(file_path=f, error=f"worker 异常: {e}")
                    _handle_fr(fr)
                    _print_progress()

        except BrokenProcessPool:
            for _future, (f, _eb) in list(pending.items()):
                large_files.append(f)
            pending.clear()
            large_files.extend(file_list[idx:])

        for fpath in large_files:
            fr = scan_single_file(fpath, keywords, context_chars, ocr_enabled, check_archives)
            _handle_fr(fr)
            _print_progress()

        large_files = []

    if total > 0:
        msg = _format_progress(checked, total, hits, match_count, fail_count, time.time() - _start_time)
        sys.stdout.write(f"\r{msg}\n")
        sys.stdout.flush()

    results.sort(key=lambda r: r.file_path)
    failures.sort(key=lambda r: r.file_path)
    return {"results": results, "failures": failures}
