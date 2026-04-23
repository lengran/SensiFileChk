"""
Phase 3: Web API 测试
测试 Web 管理端的 API 接口
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# 确保可以导入 web-admin（目录名包含连字符，不能直接导入）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 通过 importlib 动态导入 web-admin 模块
import importlib.util
web_admin_path = os.path.join(os.path.dirname(__file__), '..', 'web-admin', 'main.py')
spec = importlib.util.spec_from_file_location("web_admin_main", web_admin_path)
web_admin_main = importlib.util.module_from_spec(spec)
sys.modules["web_admin_main"] = web_admin_main
spec.loader.exec_module(web_admin_main)

app = web_admin_main.app
load_keywords = web_admin_main.load_keywords
save_keywords = web_admin_main.save_keywords


# 测试客户端
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_config(temp_config, monkeypatch):
    """每个测试前重置配置"""
    import src.config as cfg
    # 使用测试配置路径
    monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)
    # 重置为空配置
    save_keywords([], False)
    yield
    # 测试后清理
    save_keywords([], False)


class TestGetKeywords:
    """测试获取关键词列表 API"""

    def test_get_empty_keywords(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)
        save_keywords([], False)

        response = client.get("/api/keywords")
        assert response.status_code == 200
        data = response.json()
        assert data["keywords"] == []
        assert data["count"] == 0
        assert data["ocr_enabled"] is False

    def test_get_with_keywords(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)
        save_keywords(["词1", "词2"], True)

        response = client.get("/api/keywords")
        assert response.status_code == 200
        data = response.json()
        assert "词1" in data["keywords"]
        assert "词2" in data["keywords"]
        assert data["count"] == 2
        assert data["ocr_enabled"] is True


class TestAddKeyword:
    """测试添加关键词 API"""

    def test_add_valid_keyword(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        response = client.post("/api/keywords", json={"word": "新关键词"})
        assert response.status_code == 200
        data = response.json()
        assert "新关键词" in data["keywords"]
        assert data["count"] == 1

    def test_add_empty_keyword(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        response = client.post("/api/keywords", json={"word": ""})
        assert response.status_code == 400

    def test_add_whitespace_keyword(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        response = client.post("/api/keywords", json={"word": "   "})
        assert response.status_code == 400

    def test_add_duplicate_keyword(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        # 先添加一个
        client.post("/api/keywords", json={"word": "重复词"})

        # 再添加相同的（不应报错，去重）
        response = client.post("/api/keywords", json={"word": "重复词"})
        assert response.status_code == 200
        data = response.json()
        # 应该只有一条
        assert data["keywords"].count("重复词") == 1

    def test_add_special_chars(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        response = client.post("/api/keywords", json={"word": "特殊!@#词"})
        assert response.status_code == 200
        data = response.json()
        assert "特殊!@#词" in data["keywords"]


class TestRemoveKeyword:
    """测试删除关键词 API"""

    def test_remove_existing_keyword(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        # 先添加
        client.post("/api/keywords", json={"word": "待删除"})

        # 再删除
        response = client.delete("/api/keywords/待删除")
        assert response.status_code == 200
        data = response.json()
        assert "待删除" not in data["keywords"]

    def test_remove_nonexistent_keyword(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        # 删除不存在的词不应报错
        response = client.delete("/api/keywords/不存在的词")
        assert response.status_code == 200

    def test_remove_empty_keyword(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        response = client.delete("/api/keywords/")
        # 空路径通常会被路由忽略
        assert response.status_code in [200, 404, 405]


class TestOcrConfig:
    """测试 OCR 配置 API"""

    def test_get_ocr_config(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)
        save_keywords([], True)

        response = client.get("/api/config/ocr")
        assert response.status_code == 200
        data = response.json()
        assert data["ocr_enabled"] is True

    def test_enable_ocr(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        response = client.put("/api/config/ocr", json={"enabled": True})
        assert response.status_code == 200
        data = response.json()
        assert data["ocr_enabled"] is True
        assert "开启" in data["message"]

    def test_disable_ocr(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)
        save_keywords([], True)

        response = client.put("/api/config/ocr", json={"enabled": False})
        assert response.status_code == 200
        data = response.json()
        assert data["ocr_enabled"] is False
        assert "关闭" in data["message"]


class TestCliGenerate:
    """测试 CLI 命令生成 API"""

    def test_generate_with_keywords(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)
        save_keywords(["词1", "词2"], False)

        response = client.get("/api/cli/generate")
        assert response.status_code == 200
        data = response.json()
        assert "sensi-check" in data["command"]
        assert "/path/to/scan" in data["command"]

    def test_generate_without_keywords(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)
        save_keywords([], False)

        response = client.get("/api/cli/generate")
        assert response.status_code == 200
        data = response.json()
        assert "sensi-check" in data["command"]


class TestIndexPage:
    """测试前端页面"""

    def test_index_page_loads(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_index_contains_expected_content(self):
        response = client.get("/")
        content = response.text
        assert "敏感词" in content
        assert "管理端" in content or "管理" in content


class TestApiConsistency:
    """测试 API 一致性 - 确保 CLI 和 Web 共享同一数据源"""

    def test_cli_add_visible_in_web(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        # 通过 CLI 添加
        from src.config import add_keyword
        add_keyword("CLI添加的词")

        # Web API 应该能看到
        response = client.get("/api/keywords")
        data = response.json()
        assert "CLI添加的词" in data["keywords"]

    def test_web_add_visible_in_cli(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        # 通过 Web API 添加
        client.post("/api/keywords", json={"word": "Web添加的词"})

        # CLI 应该能看到（直接读取配置验证）
        config = load_keywords()
        assert "Web添加的词" in config["keywords"]

    def test_ocr_toggle_shared(self, temp_config, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "CONFIG_PATH", temp_config)

        # Web 开启 OCR
        client.put("/api/config/ocr", json={"enabled": True})

        # CLI 配置中应该反映
        config = load_keywords()
        assert config["ocr_enabled"] is True
