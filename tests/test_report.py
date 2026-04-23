import os
import pytest

from src.checker import scan_directory, FileResult, Match
from src.report import generate_report


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
