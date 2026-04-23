import os
import pytest

from src.parsers.base import ParserError
from src.parsers.txt import TxtParser
from src.parsers.pdf import PdfParser
from src.parsers.office import OfficeParser
from src.parsers.archive import ArchiveParser


@pytest.fixture
def txt_parser():
    return TxtParser()


@pytest.fixture
def pdf_parser():
    return PdfParser(ocr_enabled=False)


@pytest.fixture
def office_parser():
    return OfficeParser()


@pytest.fixture
def archive_parser():
    from src.parsers.txt import TxtParser
    from src.parsers.pdf import PdfParser
    from src.parsers.office import OfficeParser
    def factory(ext):
        if ext == ".txt":
            return TxtParser()
        elif ext == ".pdf":
            return PdfParser(ocr_enabled=False)
        elif ext in (".docx", ".pptx", ".xlsx", ".doc", ".xls", ".ppt"):
            return OfficeParser()
        return None
    return ArchiveParser(inner_parser_factory=factory)


class TestTxtParser:
    def test_utf8(self, txt_parser, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("这是一段测试文本", encoding="utf-8")
        assert txt_parser.parse(str(f)) == "这是一段测试文本"

    def test_gbk(self, txt_parser, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("这是一段GBK编码的文本", encoding="gbk")
        assert txt_parser.parse(str(f)) == "这是一段GBK编码的文本"

    def test_gb2312(self, txt_parser, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("GB2312编码测试", encoding="gb2312")
        assert txt_parser.parse(str(f)) == "GB2312编码测试"

    def test_empty_file(self, txt_parser, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert txt_parser.parse(str(f)) == ""

    def test_binary_file(self, txt_parser, tmp_path):
        f = tmp_path / "binary.txt"
        f.write_bytes(bytes(range(128, 256)) * 100)
        with pytest.raises(ParserError):
            txt_parser.parse(str(f))

    def test_nonexistent_file(self, txt_parser):
        with pytest.raises(ParserError):
            txt_parser.parse("/nonexistent/path/test.txt")

    def test_large_file(self, txt_parser, tmp_path):
        f = tmp_path / "large.txt"
        content = "测试内容" * 10000
        f.write_text(content, encoding="utf-8")
        assert txt_parser.parse(str(f)) == content


class TestPdfParser:
    def _make_pdf(self, tmp_path, text: str, name: str = "test.pdf") -> str:
        import fitz
        path = str(tmp_path / name)
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
        doc.save(path)
        doc.close()
        return path

    def test_text_pdf(self, pdf_parser, tmp_path):
        path = self._make_pdf(tmp_path, "这是PDF测试内容")
        result = pdf_parser.parse(path)
        assert "PDF测试内容" in result

    def test_multipage_pdf(self, pdf_parser, tmp_path):
        import fitz
        path = str(tmp_path / "multi.pdf")
        doc = fitz.open()
        for i in range(5):
            page = doc.new_page()
            page.insert_text((72, 72), f"第{i+1}页内容", fontsize=12)
        doc.save(path)
        doc.close()
        result = pdf_parser.parse(path)
        for i in range(5):
            assert f"第{i+1}页" in result

    def test_empty_pdf(self, pdf_parser, tmp_path):
        import fitz
        path = str(tmp_path / "empty.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.save(path)
        doc.close()
        result = pdf_parser.parse(path)
        assert result == "" or result.strip() == ""

    def test_encrypted_pdf(self, pdf_parser, tmp_path):
        import fitz
        path = str(tmp_path / "encrypted.pdf")
        doc = fitz.open()
        doc.new_page()
        page = doc[0]
        page.insert_text((72, 72), "加密内容", fontsize=12)
        doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
        doc.close()
        with pytest.raises(ParserError, match="加密"):
            pdf_parser.parse(path)


class TestOfficeParser:
    def test_docx(self, office_parser, tmp_path):
        from docx import Document
        path = str(tmp_path / "test.docx")
        doc = Document()
        doc.add_paragraph("这是docx测试内容")
        doc.save(path)
        result = office_parser.parse(path)
        assert "docx测试内容" in result

    def test_pptx(self, office_parser, tmp_path):
        from pptx import Presentation
        path = str(tmp_path / "test.pptx")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        title = slide.shapes.title
        title.text = "这是pptx测试内容"
        prs.save(path)
        result = office_parser.parse(path)
        assert "pptx测试内容" in result

    def test_xlsx(self, office_parser, tmp_path):
        from openpyxl import Workbook
        path = str(tmp_path / "test.xlsx")
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "这是xlsx测试内容"
        wb.save(path)
        result = office_parser.parse(path)
        assert "xlsx测试内容" in result

    def test_empty_docx(self, office_parser, tmp_path):
        from docx import Document
        path = str(tmp_path / "empty.docx")
        doc = Document()
        doc.save(path)
        result = office_parser.parse(path)
        assert result == ""

    def test_corrupted_office(self, office_parser, tmp_path):
        path = str(tmp_path / "corrupt.docx")
        with open(path, "wb") as f:
            f.write(b"not a real docx file content " * 10)
        with pytest.raises(ParserError):
            office_parser.parse(path)


class TestArchiveParser:
    def _make_txt(self, tmp_path, name: str = "inner.txt", content: str = "压缩包内敏感词") -> str:
        f = tmp_path / name
        f.write_text(content, encoding="utf-8")
        return str(f)

    def test_zip(self, archive_parser, tmp_path):
        import zipfile
        inner = self._make_txt(tmp_path)
        zip_path = str(tmp_path / "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(inner, "inner.txt")
        result = archive_parser.parse(zip_path)
        assert "压缩包内敏感词" in result

    def test_tar(self, archive_parser, tmp_path):
        import tarfile
        inner = self._make_txt(tmp_path)
        tar_path = str(tmp_path / "test.tar")
        with tarfile.open(tar_path, "w") as tf:
            tf.add(inner, arcname="inner.txt")
        result = archive_parser.parse(tar_path)
        assert "压缩包内敏感词" in result

    def test_targz(self, archive_parser, tmp_path):
        import tarfile
        inner = self._make_txt(tmp_path)
        tgz_path = str(tmp_path / "test.tar.gz")
        with tarfile.open(tgz_path, "w:gz") as tf:
            tf.add(inner, arcname="inner.txt")
        result = archive_parser.parse(tgz_path)
        assert "压缩包内敏感词" in result

    def test_gz(self, archive_parser, tmp_path):
        import gzip
        inner_path = str(tmp_path / "inner.txt")
        gz_path = str(tmp_path / "inner.txt.gz")
        with open(inner_path, "w", encoding="utf-8") as f:
            f.write("gz压缩的敏感词")
        with open(inner_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.write(f_in.read())
        result = archive_parser.parse(gz_path)
        assert "gz压缩的敏感词" in result

    def test_nested_zip(self, archive_parser, tmp_path):
        import zipfile
        inner_txt = tmp_path / "inner.txt"
        inner_txt.write_text("嵌套敏感词", encoding="utf-8")
        inner_zip = str(tmp_path / "inner.zip")
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.write(str(inner_txt), "inner.txt")
        outer_zip = str(tmp_path / "outer.zip")
        with zipfile.ZipFile(outer_zip, "w") as zf:
            zf.write(inner_zip, "inner.zip")
        parser = ArchiveParser(inner_parser_factory=lambda e: TxtParser() if e == ".txt" else None)
        result = parser.parse(outer_zip)
        assert "嵌套敏感词" in result

    def test_depth_limit(self, tmp_path):
        import zipfile
        deep_parser = ArchiveParser(depth=9)
        inner = self._make_txt(tmp_path)
        zip_path = str(tmp_path / "deep.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(inner, "inner.txt")
        with pytest.raises(ParserError, match="深度超限"):
            deep_parser.parse(zip_path)

    def test_zip_slip_protection(self, archive_parser, tmp_path):
        import zipfile
        zip_path = str(tmp_path / "slip.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../../../tmp/evil.txt", "malicious")
        with pytest.raises(ParserError):
            archive_parser.parse(zip_path)

    def test_empty_zip(self, archive_parser, tmp_path):
        import zipfile
        zip_path = str(tmp_path / "empty.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            pass
        result = archive_parser.parse(zip_path)
        assert result == ""

    def test_corrupted_zip(self, archive_parser, tmp_path):
        zip_path = str(tmp_path / "corrupt.zip")
        with open(zip_path, "wb") as f:
            f.write(b"not a real zip file")
        with pytest.raises(ParserError):
            archive_parser.parse(zip_path)

    def test_rar(self, archive_parser, tmp_path):
        try:
            import rarfile
        except ImportError:
            pytest.skip("rarfile not installed")
        try:
            rarfile.tool_setup()
        except Exception:
            pytest.skip("unrar not installed")
        import zipfile
        inner = self._make_txt(tmp_path, "inner.txt", "rar内敏感词")
        zip_path = str(tmp_path / "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(inner, "inner.txt")
        try:
            import subprocess
            rar_path = str(tmp_path / "test.rar")
            r = subprocess.run(
                ["rar", "a", "-ep", rar_path, inner],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                pytest.skip("rar command not available")
            result = archive_parser.parse(rar_path)
            assert "rar内敏感词" in result
        except FileNotFoundError:
            pytest.skip("rar command not installed")

    def test_7z(self, archive_parser, tmp_path):
        try:
            import py7zr
        except ImportError:
            pytest.skip("py7zr not installed")
        import zipfile
        inner = self._make_txt(tmp_path, "inner.txt", "7z内敏感词")
        sz_path = str(tmp_path / "test.7z")
        try:
            with py7zr.SevenZipFile(sz_path, "w") as sz:
                sz.write(inner, "inner.txt")
        except Exception:
            pytest.skip("7z creation failed")
        result = archive_parser.parse(sz_path)
        assert "7z内敏感词" in result
