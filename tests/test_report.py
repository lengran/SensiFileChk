import os
import pytest

from src.checker import scan_directory, FileResult, Match
from src.report import generate_report, _has_matches, _highlight_keyword


@pytest.fixture
def scan_result_with_matches(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("这是国家机密文件的内容", encoding="utf-8")
    return scan_directory(str(tmp_path), ["国家机密"])


@pytest.fixture
def scan_result_empty(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("普通文本", encoding="utf-8")
    return scan_directory(str(tmp_path), ["机密"])


class TestGenerateReport:
    def test_generates_html(self, scan_result_with_matches, tmp_path):
        scan_dir = str(tmp_path)
        output = str(tmp_path / "report.html")
        generate_report(scan_result_with_matches, output, scan_dir, ["国家机密"])
        assert os.path.exists(output)
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert "保密检查报告" in html
        assert "国家机密" in html

    def test_highlight_keyword(self, scan_result_with_matches, tmp_path):
        scan_dir = str(tmp_path)
        output = str(tmp_path / "report.html")
        generate_report(scan_result_with_matches, output, scan_dir, ["国家机密"])
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert '<mark class="highlight">国家机密</mark>' in html

    def test_no_results_message(self, scan_result_empty, tmp_path):
        scan_dir = str(tmp_path)
        output = str(tmp_path / "report.html")
        generate_report(scan_result_empty, output, scan_dir, ["机密"])
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert "未发现敏感词" in html

    def test_no_results_message_with_failures(self, tmp_path):
        """有失败但无匹配时仍显示'未发现敏感词'"""
        output = str(tmp_path / "report.html")
        fr = FileResult(file_path=str(tmp_path / "broken.txt"), error="解析失败")
        scan_result = {"results": [], "failures": [fr]}
        generate_report(scan_result, output, str(tmp_path), ["机密"])
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert "未发现敏感词" in html

    def test_directory_tree(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "a.txt").write_text("国家机密", encoding="utf-8")
        (tmp_path / "b.txt").write_text("内部资料", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["国家机密", "内部资料"])
        output = str(tmp_path / "report.html")
        generate_report(result, output, str(tmp_path), ["国家机密", "内部资料"])
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert "subdir" in html
        assert "a.txt" in html
        assert "b.txt" in html

    def test_header_info(self, scan_result_with_matches, tmp_path):
        scan_dir = str(tmp_path)
        output = str(tmp_path / "report.html")
        generate_report(scan_result_with_matches, output, scan_dir, ["国家机密"])
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert "检查时间" in html
        assert "关键词数量" in html

    def test_failures_section(self, tmp_path):
        output = str(tmp_path / "report.html")
        fr = FileResult(file_path=str(tmp_path / "broken.txt"), error="解析失败: 文件已损坏")
        scan_result = {"results": [], "failures": [fr]}
        generate_report(scan_result, output, str(tmp_path), ["机密"])
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert "检查失败" in html
        assert "解析失败" in html

    def test_toggle_js(self, scan_result_with_matches, tmp_path):
        scan_dir = str(tmp_path)
        output = str(tmp_path / "report.html")
        generate_report(scan_result_with_matches, output, scan_dir, ["国家机密"])
        with open(output, encoding="utf-8") as f:
            html = f.read()
        assert "function toggle" in html

    def test_line_number_display(self, tmp_path):
        """报告中显示行号"""
        f = tmp_path / "test.txt"
        f.write_text("第一行\n第二行机密信息\n第三行", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["机密信息"])
        output = str(tmp_path / "report.html")
        generate_report(result, output, str(tmp_path), ["机密信息"])
        with open(output, encoding="utf-8") as fobj:
            html = fobj.read()
        assert "行 2" in html or "line-num" in html

    def test_deep_directory_breadcrumb(self, tmp_path):
        deep = tmp_path
        for d in ["a", "b", "c", "d"]:
            deep = deep / d
            deep.mkdir()
        (deep / "secret.txt").write_text("深层机密", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["深层机密"])
        output = str(tmp_path / "report.html")
        generate_report(result, output, str(tmp_path), ["深层机密"])
        with open(output, encoding="utf-8") as fobj:
            html = fobj.read()
        assert "›" in html

    def test_has_matches_recursive(self):
        fr_match = FileResult(file_path="t.txt", matches=[Match(keyword="k", start=0, end=1, context="k", line_number=1)])
        fr_no_match = FileResult(file_path="t2.txt")
        assert _has_matches(fr_match) is True
        assert _has_matches(fr_no_match) is False
        assert _has_matches({"a": {"b": fr_match}}) is True
        assert _has_matches({"a": {"b": fr_no_match}}) is False
        assert _has_matches({}) is False

    def test_empty_keyword_highlight(self):
        result = _highlight_keyword("some text", "")
        assert result == "some text"

    def test_highlight_preserves_original_case(self):
        result = _highlight_keyword("This is SECRET data", "secret")
        assert '<mark class="highlight">SECRET</mark>' in result

        result2 = _highlight_keyword("Mixed SeCrEt case", "secret")
        assert '<mark class="highlight">SeCrEt</mark>' in result2

    def test_matched_directory_auto_expanded(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "a.txt").write_text("机密内容", encoding="utf-8")
        result = scan_directory(str(tmp_path), ["机密内容"])
        output = str(tmp_path / "report.html")
        generate_report(result, output, str(tmp_path), ["机密内容"])
        with open(output, encoding="utf-8") as fobj:
            html = fobj.read()
        assert "display:block" in html
