"""
Phase 3: CLI 测试
测试所有 CLI 子命令功能
"""
import json
import os
import pytest
from io import StringIO
from unittest.mock import patch, MagicMock


class TestCliCheckCommand:
    """测试 check 子命令"""

    def test_check_with_valid_keywords(self, tmp_path, temp_config):
        # 设置测试环境
        from src.config import save_keywords
        save_keywords(["国家机密"], False)

        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("这是国家机密文件", encoding="utf-8")

        # 运行 check 命令
        from src.cli import main
        output_path = str(tmp_path / "report.html")

        with patch('sys.argv', ['sensi-check', 'check', str(tmp_path), '-o', output_path]):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

        # 验证报告文件已生成
        assert os.path.exists(output_path)
        with open(output_path, encoding='utf-8') as f:
            content = f.read()
            assert "保密检查报告" in content

    def test_check_empty_keywords(self, tmp_path, temp_config):
        # 不设置关键词
        from src.config import save_keywords
        save_keywords([], False)

        from src.cli import main
        with patch('sys.argv', ['sensi-check', 'check', str(tmp_path), '-o', 'report.html']):
            with patch('sys.stderr', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

    def test_check_with_workers(self, tmp_path, temp_config):
        # 设置关键词
        from src.config import save_keywords
        save_keywords(["机密"], False)

        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("包含机密信息", encoding="utf-8")

        from src.cli import main
        output_path = str(tmp_path / "report.html")

        # 使用多 worker 扫描
        with patch('sys.argv', ['sensi-check', 'check', str(tmp_path), '-o', output_path, '-w', '2']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        assert os.path.exists(output_path)

    def test_check_no_archives(self, tmp_path, temp_config):
        # 设置关键词
        from src.config import save_keywords
        save_keywords(["机密"], False)

        from src.cli import main
        output_path = str(tmp_path / "report.html")

        with patch('sys.argv', ['sensi-check', 'check', str(tmp_path), '-o', output_path, '-n']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestCliAddCommand:
    """测试 add 子命令"""

    def test_add_single_keyword(self, temp_config):
        from src.cli import main
        from src.config import load_keywords

        with patch('sys.argv', ['sensi-check', 'add', '国家机密']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        config = load_keywords()
        assert "国家机密" in config["keywords"]

    def test_add_multiple_keywords(self, temp_config):
        from src.cli import main
        from src.config import load_keywords

        with patch('sys.argv', ['sensi-check', 'add', '词1', '词2', '词3']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        config = load_keywords()
        assert "词1" in config["keywords"]
        assert "词2" in config["keywords"]
        assert "词3" in config["keywords"]

    def test_add_duplicate_keyword(self, temp_config):
        from src.cli import main
        from src.config import load_keywords

        # 先添加一个
        with patch('sys.argv', ['sensi-check', 'add', '词1']):
            with pytest.raises(SystemExit):
                main()

        # 再次添加
        with patch('sys.argv', ['sensi-check', 'add', '词1']):
            with pytest.raises(SystemExit):
                main()

        config = load_keywords()
        # 不应该重复
        assert config["keywords"].count("词1") == 1


class TestCliRemoveCommand:
    """测试 remove 子命令"""

    def test_remove_existing_keyword(self, temp_config):
        from src.cli import main
        from src.config import add_keyword, load_keywords

        # 先添加
        add_keyword("待删除词")

        # 再删除
        with patch('sys.argv', ['sensi-check', 'remove', '待删除词']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        config = load_keywords()
        assert "待删除词" not in config["keywords"]

    def test_remove_nonexistent_keyword(self, temp_config):
        # 删除不存在的词不应报错
        from src.cli import main
        from src.config import load_keywords

        with patch('sys.argv', ['sensi-check', 'remove', '不存在的词']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        # 配置应正常
        config = load_keywords()
        assert config is not None


class TestCliListCommand:
    """测试 list 子命令"""

    def test_list_empty(self, reset_config):
        from src.cli import main
        from src.config import save_keywords

        # 确保关键词列表为空
        save_keywords([], False)

        with patch('sys.argv', ['sensi-check', 'list']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                output = mock_stdout.getvalue()
                assert "关键词列表为空" in output or output.strip() == ""

    def test_list_with_keywords(self, temp_config):
        from src.cli import main
        from src.config import add_keyword

        add_keyword("关键词A")
        add_keyword("关键词B")

        with patch('sys.argv', ['sensi-check', 'list']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                output = mock_stdout.getvalue()
                assert "关键词A" in output
                assert "关键词B" in output


class TestCliConfigCommand:
    """测试 config 子命令"""

    def test_config_show_ocr(self, temp_config):
        from src.cli import main
        from src.config import save_keywords

        save_keywords(["测试词"], True)  # 开启 OCR

        with patch('sys.argv', ['sensi-check', 'config', 'show-ocr']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()
                assert "开启" in output

    def test_config_set_ocr_on(self, temp_config):
        from src.cli import main
        from src.config import load_keywords

        with patch('sys.argv', ['sensi-check', 'config', 'set-ocr', 'on']):
            with patch('sys.stdout', new_callable=StringIO):
                main()

        config = load_keywords()
        assert config["ocr_enabled"] is True

    def test_config_set_ocr_off(self, temp_config):
        from src.cli import main
        from src.config import load_keywords, save_keywords

        # 先开启
        save_keywords(["测试词"], True)

        with patch('sys.argv', ['sensi-check', 'config', 'set-ocr', 'off']):
            with patch('sys.stdout', new_callable=StringIO):
                main()

        config = load_keywords()
        assert config["ocr_enabled"] is False

    def test_config_without_subcommand(self, temp_config):
        from src.cli import main

        with patch('sys.argv', ['sensi-check', 'config']):
            with patch('sys.stderr', new_callable=StringIO):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1


class TestCliServeCommand:
    """测试 serve 子命令"""

    def test_serve_command_parses_args(self, temp_config):
        from src.cli import main

        # 测试参数解析（不实际启动服务器）
        with patch('sys.argv', ['sensi-check', 'serve', '--port', '8888']):
            with patch('uvicorn.Server.run') as mock_run:
                with patch('sys.stdout', new_callable=StringIO):
                    # 设置超时避免卡住
                    import signal
                    def timeout_handler(signum, frame):
                        raise TimeoutError()
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(1)
                    try:
                        main()
                    except TimeoutError:
                        pass
                    finally:
                        signal.alarm(0)

                    # 验证服务器被启动
                    mock_run.assert_called()


class TestCliHelp:
    """测试帮助信息"""

    def test_main_help(self):
        from src.cli import main

        with patch('sys.argv', ['sensi-check', '--help']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                output = mock_stdout.getvalue()
                assert "check" in output
                assert "add" in output
                assert "remove" in output
                assert "list" in output
                assert "config" in output
                assert "serve" in output

    def test_no_args_shows_help(self):
        from src.cli import main

        with patch('sys.argv', ['sensi-check']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
                output = mock_stdout.getvalue()
                assert "usage" in output.lower()
