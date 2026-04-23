"""
Phase 1: 配置模块测试
"""
import json
import os
import pytest

from src.config import (
    load_keywords,
    save_keywords,
    add_keyword,
    remove_keyword,
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """
    每个测试使用独立的配置文件
    """
    import src.config as cfg
    config_dir = str(tmp_path / "config")
    config_path = os.path.join(config_dir, "keywords.json")
    os.makedirs(config_dir, exist_ok=True)

    # 初始化为空配置
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"keywords": [], "ocr_enabled": False}, f)

    monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)

    yield config_path

    # 清理
    if os.path.exists(config_path):
        os.remove(config_path)


class TestLoadKeywords:
    def test_load_empty(self, isolated_config):
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}

    def test_load_existing(self, isolated_config):
        data = {"keywords": ["词1", "词2"], "ocr_enabled": True}
        with open(isolated_config, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = load_keywords()
        assert result == data

    def test_load_corrupted_json(self, isolated_config):
        with open(isolated_config, "w") as f:
            f.write("{invalid json")
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}

    def test_load_missing_fields(self, isolated_config):
        with open(isolated_config, "w", encoding="utf-8") as f:
            json.dump({"other": 1}, f)
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}


class TestSaveKeywords:
    def test_save_and_load(self, isolated_config):
        save_keywords(["词1", "词2"], True)
        result = load_keywords()
        assert "词1" in result["keywords"]
        assert "词2" in result["keywords"]
        assert result["ocr_enabled"] is True

    def test_save_deduplicates(self, isolated_config):
        save_keywords(["词1", "词1", "词2"], False)
        result = load_keywords()
        assert result["keywords"].count("词1") == 1


class TestAddKeyword:
    def test_add_new(self, isolated_config):
        add_keyword("新词")
        result = load_keywords()
        assert "新词" in result["keywords"]

    def test_add_duplicate(self, isolated_config):
        add_keyword("词1")
        add_keyword("词1")
        result = load_keywords()
        assert result["keywords"].count("词1") == 1

    def test_add_empty(self, isolated_config):
        add_keyword("")
        result = load_keywords()
        assert "" not in result["keywords"]


class TestRemoveKeyword:
    def test_remove_existing(self, isolated_config):
        add_keyword("词1")
        remove_keyword("词1")
        result = load_keywords()
        assert "词1" not in result["keywords"]

    def test_remove_nonexistent(self, isolated_config):
        remove_keyword("不存在的词")
        result = load_keywords()
        assert "不存在的词" not in result["keywords"]
