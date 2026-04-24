import os
import pytest

from src.checker import (
    discover_files,
    _match_keywords,
    _extract_context,
    scan_single_file,
    scan_directory,
    Match,
    SUPPORTED_EXTENSIONS,
)


class TestMatchKeywords:
    def test_single_match(self):
        matches = _match_keywords("这是国家机密文件", ["国家机密"])
        assert len(matches) == 1
        assert matches[0].keyword == "国家机密"
        assert matches[0].start == 2

    def test_multiple_keywords(self):
        matches = _match_keywords("这是国家机密信息，包含内部资料", ["国家机密", "内部资料"])
        assert len(matches) == 2

    def test_overlapping_keywords(self):
        matches = _match_keywords("国家机密信息", ["国家机密", "机密信息"])
        assert len(matches) == 2

    def test_no_match(self):
        matches = _match_keywords("普通文本", ["机密"])
        assert len(matches) == 0

    def test_empty_keyword(self):
        matches = _match_keywords("文本", [""])
        assert len(matches) == 0

    def test_multiple_occurrences(self):
        matches = _match_keywords("机密文件和机密数据", ["机密"])
        assert len(matches) == 2

    def test_case_insensitive_english(self):
        """大小写不敏感匹配（英文关键词）"""
        matches = _match_keywords("This is SECRET information", ["secret"])
        assert len(matches) == 1
        assert matches[0].keyword == "secret"

    def test_case_insensitive_mixed(self):
        matches = _match_keywords("Secret and SECRET and secret", ["secret"])
        assert len(matches) == 3

    def test_chinese_keyword_still_case_sensitive(self):
        """中文关键词保持大小写敏感（中文无大小写）"""
        matches = _match_keywords("这是国家机密", ["国家机密"])
        assert len(matches) == 1

    def test_line_number_tracking(self):
        """行号追踪"""
        text = "第一行\n第二行机密信息\n第三行"
        matches = _match_keywords(text, ["机密信息"])
        assert len(matches) == 1
        assert matches[0].line_number == 2

    def test_line_number_first_line(self):
        text = "机密在开头"
        matches = _match_keywords(text, ["机密"])
        assert matches[0].line_number == 1


class TestExtractContext:
    def test_middle_context(self):
        text = "0123456789机密0123456789"
        ctx = _extract_context(text, 10, 12, 5)
        assert ctx == "56789机密01234"

    def test_start_boundary(self):
        text = "机密在开头"
        ctx = _extract_context(text, 0, 2, 5)
        assert ctx == "机密在开头"

    def test_end_boundary(self):
        text = "在结尾机密"
        ctx = _extract_context(text, 3, 5, 5)
        assert ctx == "在结尾机密"


class TestDiscoverFiles:
    def test_finds_supported_formats(self, tmp_path):
        (tmp_path / "a.txt").write_text("test")
        (tmp_path / "b.pdf").write_bytes(b"%PDF")
        (tmp_path / "c.docx").write_bytes(b"PK")
        files = discover_files(str(tmp_path))
        assert len(files) == 3

    def test_ignores_unsupported(self, tmp_path):
        (tmp_path / "a.txt").write_text("test")
        (tmp_path / "b.jpg").write_bytes(b"\xff\xd8")
        files = discover_files(str(tmp_path))
        assert len(files) == 1
        assert files[0].endswith("a.txt")

    def test_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.txt").write_text("test")
        (sub / "b.txt").write_text("test")
        files = discover_files(str(tmp_path))
        assert len(files) == 2

    def test_empty_dir(self, tmp_path):
        files = discover_files(str(tmp_path))
        assert files == []


class TestScanSingleFile:
    def test_scan_txt_with_match(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("这是国家机密文件", encoding="utf-8")
        result = scan_single_file(str(f), ["国家机密"], 50)
        assert len(result.matches) == 1
        assert result.error is None

    def test_scan_txt_no_match(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("普通文本", encoding="utf-8")
        result = scan_single_file(str(f), ["机密"], 50)
        assert len(result.matches) == 0

    def test_scan_unsupported_format(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("内容")
        result = scan_single_file(str(f), ["内容"], 50)
        assert result.error is not None

    def test_scan_pdf(self, tmp_path):
        import fitz
        path = str(tmp_path / "test.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "secret keyword in PDF", fontsize=12)
        doc.save(path)
        doc.close()
        result = scan_single_file(path, ["secret keyword"], 50, ocr_enabled=False)
        assert len(result.matches) >= 1

    def test_scan_docx(self, tmp_path):
        from docx import Document
        path = str(tmp_path / "test.docx")
        doc = Document()
        doc.add_paragraph("docx中的国家机密")
        doc.save(path)
        result = scan_single_file(path, ["国家机密"], 50)
        assert len(result.matches) == 1

    def test_scan_pptx(self, tmp_path):
        from pptx import Presentation
        path = str(tmp_path / "test.pptx")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "pptx中的国家机密"
        prs.save(path)
        result = scan_single_file(path, ["国家机密"], 50)
        assert len(result.matches) == 1

    def test_scan_xlsx(self, tmp_path):
        from openpyxl import Workbook
        path = str(tmp_path / "test.xlsx")
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "xlsx中的国家机密"
        wb.save(path)
        result = scan_single_file(path, ["国家机密"], 50)
        assert len(result.matches) == 1

    def test_case_insensitive_scan(self, tmp_path):
        """大小写不敏感扫描"""
        f = tmp_path / "test.txt"
        f.write_text("This is SECRET data", encoding="utf-8")
        result = scan_single_file(str(f), ["secret"], 50)
        assert len(result.matches) == 1


class TestScanDirectory:
    def test_scan_with_matches(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("包含国家机密信息", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["国家机密"])
        assert len(result["results"]) == 1
        assert len(result["failures"]) == 0

    def test_scan_no_keywords_match(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("普通文本", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["机密"])
        assert len(result["results"]) == 0

    def test_scan_empty_dir(self, tmp_path):
        result = scan_directory(str(tmp_path), ["机密"])
        assert result["results"] == []
        assert result["failures"] == []

    def test_scan_mixed_formats(self, tmp_path):
        (tmp_path / "a.txt").write_text("国家机密", encoding="utf-8")
        from docx import Document
        doc = Document()
        doc.add_paragraph("内部资料")
        doc.save(str(tmp_path / "b.docx"))
        result = scan_directory(str(tmp_path), ["国家机密", "内部资料"])
        assert len(result["results"]) == 2

    def test_scan_with_failures(self, tmp_path):
        (tmp_path / "a.txt").write_text("国家机密", encoding="utf-8")
        corrupt = tmp_path / "corrupt.docx"
        corrupt.write_bytes(b"not a real docx")
        result = scan_directory(str(tmp_path), ["国家机密"])
        assert len(result["results"]) == 1
        assert len(result["failures"]) == 1


class TestParallelScan:
    def test_single_worker(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.txt").write_text(f"文件{i}国家机密", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["国家机密"], num_workers=1)
        assert len(result["results"]) == 5

    def test_multi_worker(self, tmp_path):
        for i in range(10):
            (tmp_path / f"f{i}.txt").write_text(f"文件{i}国家机密", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["国家机密"], num_workers=2)
        assert len(result["results"]) == 10

    def test_multi_worker_results_match(self, tmp_path):
        for i in range(10):
            (tmp_path / f"f{i}.txt").write_text(f"文件{i}国家机密", encoding="utf-8")
        r1 = scan_directory(str(tmp_path), ["国家机密"], num_workers=1)
        r2 = scan_directory(str(tmp_path), ["国家机密"], num_workers=2)
        paths1 = sorted(r.file_path for r in r1["results"])
        paths2 = sorted(r.file_path for r in r2["results"])
        assert paths1 == paths2
