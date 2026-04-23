import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

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


def discover_files(dir_path: str, extensions: Optional[set] = None) -> list[str]:
    ext_filter = extensions or SUPPORTED_EXTENSIONS
    result = []
    for root, _dirs, files in os.walk(dir_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            _, ext = os.path.splitext(fname)
            if ext.lower() in ext_filter:
                result.append(fpath)
    return sorted(result)


def _match_keywords(text: str, keywords: list[str]) -> list[Match]:
    matches = []
    for keyword in keywords:
        if not keyword:
            continue
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
    files = discover_files(dir_path)
    results = []
    failures = []

    if num_workers <= 1:
        for fpath in files:
            fr = scan_single_file(fpath, keywords, context_chars, ocr_enabled, check_archives)
            if fr.error:
                failures.append(fr)
                if verbose:
                    print(f"  [失败] {fpath}: {fr.error}")
            elif fr.matches:
                results.append(fr)
                if verbose:
                    print(f"  [命中] {fpath}: {len(fr.matches)} 处匹配")
    else:
        tasks = [
            (fpath, keywords, context_chars, ocr_enabled, check_archives)
            for fpath in files
        ]
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_worker_task, t): t[0] for t in tasks}
            for future in as_completed(futures):
                fpath = futures[future]
                try:
                    fr = future.result()
                except Exception as e:
                    fr = FileResult(file_path=fpath, error=f"worker 异常: {e}")
                if fr.error:
                    failures.append(fr)
                    if verbose:
                        print(f"  [失败] {fpath}: {fr.error}")
                elif fr.matches:
                    results.append(fr)
                    if verbose:
                        print(f"  [命中] {fpath}: {len(fr.matches)} 处匹配")

    results.sort(key=lambda r: r.file_path)
    failures.sort(key=lambda r: r.file_path)
    return {"results": results, "failures": failures}
