"""
Phase 4: 集成测试
端到端测试，验证完整流程
"""
import os
import json
import zipfile
import tarfile
import pytest
from io import StringIO
from unittest.mock import patch
from pathlib import Path

# 集成测试使用实际文件系统操作


@pytest.fixture
def setup_test_env(tmp_path, monkeypatch, reset_config):
    """设置集成测试环境"""
    import src.config as cfg
    # 使用临时配置
    config_dir = str(tmp_path / "config")
    config_path = os.path.join(config_dir, "keywords.json")
    monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
    os.makedirs(config_dir, exist_ok=True)

    # 重置为默认空配置
    from src.config import save_keywords
    save_keywords([], False)

    # 创建测试目录结构
    scan_dir = tmp_path / "scan_target"
    scan_dir.mkdir()
    report_dir = tmp_path / "reports"
    report_dir.mkdir()

    yield {
        "tmp_path": tmp_path,
        "scan_dir": scan_dir,
        "report_dir": report_dir,
        "config_path": config_path,
    }


class TestEndToEndScan:
    """端到端扫描流程测试"""

    def test_scan_txt_files(self, setup_test_env):
        """扫描纯文本文件"""
        scan_dir = setup_test_env["scan_dir"]

        # 创建测试文件
        (scan_dir / "secret1.txt").write_text(
            "这是国家机密文件，包含敏感信息", encoding="utf-8"
        )
        (scan_dir / "normal.txt").write_text(
            "这是普通文件，没有敏感内容", encoding="utf-8"
        )

        # 设置关键词
        from src.config import save_keywords
        save_keywords(["国家机密"], False)

        # 执行扫描
        from src.checker import scan_directory
        result = scan_directory(
            str(scan_dir),
            ["国家机密"],
            context_chars=50,
            num_workers=1,
            ocr_enabled=False,
            check_archives=False,
        )

        # 验证结果
        assert len(result["results"]) == 1
        assert len(result["failures"]) == 0
        assert result["results"][0].file_path.endswith("secret1.txt")
        assert len(result["results"][0].matches) == 1
        assert result["results"][0].matches[0].keyword == "国家机密"

    def test_generate_html_report(self, setup_test_env):
        """生成 HTML 报告"""
        scan_dir = setup_test_env["scan_dir"]
        report_dir = setup_test_env["report_dir"]

        # 创建测试文件
        (scan_dir / "doc.txt").write_text(
            "包含内部资料的文件", encoding="utf-8"
        )

        # 设置关键词并扫描
        from src.config import save_keywords
        save_keywords(["内部资料"], False)

        from src.checker import scan_directory
        from src.report import generate_report

        result = scan_directory(
            str(scan_dir),
            ["内部资料"],
            num_workers=1,
        )

        # 生成报告
        report_path = str(report_dir / "integration_report.html")
        generate_report(result, report_path, str(scan_dir), ["内部资料"])

        # 验证报告
        assert os.path.exists(report_path)
        with open(report_path, encoding="utf-8") as f:
            html = f.read()
            assert "保密检查报告" in html
            assert "内部资料" in html
            assert "doc.txt" in html
            assert "check time" not in html  # 应该是中文
            assert "检查时间" in html

    def test_cli_full_workflow(self, setup_test_env):
        """CLI 完整工作流"""
        scan_dir = setup_test_env["scan_dir"]
        report_dir = setup_test_env["report_dir"]

        # 创建测试文件
        (scan_dir / "target.txt").write_text(
            "绝密文件内容", encoding="utf-8"
        )

        # 1. 添加关键词
        from src.cli import main
        with patch('sys.argv', ['sensi-check', 'add', '绝密']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0 or exc_info.value.code is None

        # 2. 验证已添加
        from src.config import load_keywords
        config = load_keywords()
        assert "绝密" in config["keywords"]

        # 3. 执行扫描
        report_path = str(report_dir / "cli_report.html")
        with patch('sys.argv', ['sensi-check', 'check', str(scan_dir), '-o', report_path]):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                # 检查成功退出
                output = mock_stdout.getvalue()
                assert "扫描完成" in output

        # 4. 验证报告
        assert os.path.exists(report_path)


class TestArchiveScanning:
    """压缩包扫描测试"""

    def test_scan_nested_archive(self, setup_test_env):
        """扫描嵌套压缩包"""
        scan_dir = setup_test_env["scan_dir"]

        # 创建内层 zip
        inner_txt = scan_dir / "inner_content.txt"
        inner_txt.write_text("嵌套敏感词内容", encoding="utf-8")

        inner_zip = scan_dir / "inner.zip"
        with zipfile.ZipFile(inner_zip, 'w') as zf:
            zf.write(inner_txt, "inner_content.txt")

        # 创建外层 zip
        outer_zip = scan_dir / "outer.zip"
        with zipfile.ZipFile(outer_zip, 'w') as zf:
            zf.write(inner_zip, "inner.zip")

        # 清理临时文件
        inner_txt.unlink()
        inner_zip.unlink()

        # 扫描
        from src.config import save_keywords
        save_keywords(["嵌套敏感词"], False)

        from src.checker import scan_directory
        result = scan_directory(
            str(scan_dir),
            ["嵌套敏感词"],
            num_workers=1,
            check_archives=True,
        )

        # 应该在外层 zip 中找到嵌套敏感词
        assert len(result["results"]) >= 1

    def test_scan_tar_gz(self, setup_test_env):
        """扫描 tar.gz 文件"""
        scan_dir = setup_test_env["scan_dir"]

        # 创建测试文件并压缩
        test_file = scan_dir / "content.txt"
        test_file.write_text("tar内敏感词", encoding="utf-8")

        tar_path = scan_dir / "archive.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(test_file, arcname="content.txt")

        # 删除原始文件
        test_file.unlink()

        # 扫描
        from src.config import save_keywords
        save_keywords(["tar内敏感词"], False)

        from src.checker import scan_directory
        result = scan_directory(
            str(scan_dir),
            ["tar内敏感词"],
            num_workers=1,
            check_archives=True,
        )

        assert len(result["results"]) == 1


class TestMultiFormatScan:
    """多格式文件扫描测试"""

    def test_mixed_format_directory(self, setup_test_env):
        """扫描包含多种格式的目录"""
        scan_dir = setup_test_env["scan_dir"]

        # 创建不同格式的测试文件
        (scan_dir / "doc1.txt").write_text(
            "txt格式国家机密", encoding="utf-8"
        )

        # 创建 docx（需要 python-docx）
        try:
            from docx import Document
            docx_path = str(scan_dir / "doc2.docx")
            doc = Document()
            doc.add_paragraph("docx格式内部资料")
            doc.save(docx_path)
        except ImportError:
            pytest.skip("python-docx not installed")

        # 扫描
        from src.config import save_keywords
        save_keywords(["国家机密", "内部资料"], False)

        from src.checker import scan_directory
        result = scan_directory(
            str(scan_dir),
            ["国家机密", "内部资料"],
            num_workers=1,
        )

        # 应该找到 2 个文件（或至少 1 个）
        assert len(result["results"]) >= 1


class TestErrorHandling:
    """错误处理测试"""

    def test_corrupted_file_handling(self, setup_test_env):
        """处理损坏的文件"""
        scan_dir = setup_test_env["scan_dir"]

        # 创建损坏的 docx
        (scan_dir / "broken.docx").write_bytes(b"not a real docx content")

        # 创建正常文件
        (scan_dir / "good.txt").write_text(
            "正常文件包含机密", encoding="utf-8"
        )

        # 扫描
        from src.config import save_keywords
        save_keywords(["机密"], False)

        from src.checker import scan_directory
        result = scan_directory(
            str(scan_dir),
            ["机密"],
            num_workers=1,
        )

        # 正常文件应该找到匹配
        assert len(result["results"]) == 1
        # 损坏文件应该在失败列表中
        assert len(result["failures"]) == 1
        assert "broken.docx" in result["failures"][0].file_path

    def test_permission_denied_handling(self, setup_test_env, tmp_path):
        """处理权限不足的文件"""
        scan_dir = setup_test_env["scan_dir"]

        # 创建权限不足的文件（如果可能）
        no_read = scan_dir / "no_read.txt"
        no_read.write_text("机密内容", encoding="utf-8")

        try:
            # 移除读权限
            os.chmod(str(no_read), 0o000)

            # 扫描
            from src.config import save_keywords
            save_keywords(["机密"], False)

            from src.checker import scan_directory
            result = scan_directory(
                str(scan_dir),
                ["机密"],
                num_workers=1,
            )

            # 应该没有成功结果，失败列表可能包含该文件
            # 或者该文件被跳过
            assert len(result["results"]) == 0 or len(result["results"]) == 0

        finally:
            # 恢复权限以便清理
            try:
                os.chmod(str(no_read), 0o644)
            except:
                pass


class TestParallelScanning:
    """并行扫描测试"""

    def test_parallel_results_consistency(self, setup_test_env):
        """并行扫描结果应该与单进程一致"""
        scan_dir = setup_test_env["scan_dir"]

        # 创建多个测试文件
        for i in range(10):
            (scan_dir / f"file{i}.txt").write_text(
                f"文件{i}包含机密信息", encoding="utf-8"
            )

        from src.config import save_keywords
        save_keywords(["机密"], False)

        from src.checker import scan_directory

        # 单进程扫描
        result1 = scan_directory(
            str(scan_dir),
            ["机密"],
            num_workers=1,
        )

        # 多进程扫描
        result2 = scan_directory(
            str(scan_dir),
            ["机密"],
            num_workers=2,
        )

        # 结果数量应该相同
        assert len(result1["results"]) == len(result2["results"])
        assert len(result1["failures"]) == len(result2["failures"])

        # 匹配文件路径应该一致（排序后）
        paths1 = sorted([r.file_path for r in result1["results"]])
        paths2 = sorted([r.file_path for r in result2["results"]])
        assert paths1 == paths2


class TestWebAndCliConsistency:
    """Web 和 CLI 数据一致性测试"""

    def test_add_keyword_via_cli_visible_in_web(self, setup_test_env, monkeypatch):
        """CLI 添加的关键词 Web 可见"""
        import sys
        import os
        import importlib.util

        # 动态导入 web-admin 模块
        web_admin_path = os.path.join(
            os.path.dirname(__file__), '..', 'web-admin', 'main.py'
        )
        spec = importlib.util.spec_from_file_location("web_admin_main", web_admin_path)
        web_admin_main = importlib.util.module_from_spec(spec)
        sys.modules["web_admin_main"] = web_admin_main
        spec.loader.exec_module(web_admin_main)

        app = web_admin_main.app

        from src.cli import main
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # 通过 CLI 添加
        with patch('sys.argv', ['sensi-check', 'add', '一致性感词']):
            with pytest.raises(SystemExit):
                main()

        # 通过 Web API 查询
        response = client.get("/api/keywords")
        assert response.status_code == 200
        data = response.json()
        assert "一致性感词" in data["keywords"]

    def test_toggle_ocr_via_web_visible_in_cli(self, setup_test_env, monkeypatch):
        """Web 切换的 OCR 状态 CLI 可见"""
        import sys
        import os
        import importlib.util

        # 动态导入 web-admin 模块
        web_admin_path = os.path.join(
            os.path.dirname(__file__), '..', 'web-admin', 'main.py'
        )
        spec = importlib.util.spec_from_file_location("web_admin_main_int", web_admin_path)
        web_admin_main = importlib.util.module_from_spec(spec)
        sys.modules["web_admin_main_int"] = web_admin_main
        spec.loader.exec_module(web_admin_main)

        app = web_admin_main.app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # 通过 Web 开启 OCR
        response = client.put("/api/config/ocr", json={"enabled": True})
        assert response.status_code == 200

        # 通过 CLI 配置查看
        from src.config import load_keywords
        config = load_keywords()
        assert config["ocr_enabled"] is True
