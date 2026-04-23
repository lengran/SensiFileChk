import json
import os
import tempfile
import pytest

from src.config import (
    load_keywords,
    save_keywords,
    add_keyword,
    remove_keyword,
    CONFIG_PATH,
)


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    import src.config as cfg
    config_dir = str(tmp_path / "config")
    config_path = os.path.join(config_dir, "keywords.json")
    monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)
    return config_path


class TestLoadKeywords:
    def test_load_empty(self, temp_config):
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}

    def test_load_existing(self, temp_config):
        data = {"keywords": ["词1", "词2"], "ocr_enabled": True}
        os.makedirs(os.path.dirname(temp_config), exist_ok=True)
        with open(temp_config, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = load_keywords()
        assert result == data

    def test_load_corrupted_json(self, temp_config):
        os.makedirs(os.path.dirname(temp_config), exist_ok=True)
        with open(temp_config, "w") as f:
            f.write("{invalid json")
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}

    def test_load_missing_fields(self, temp_config):
        os.makedirs(os.path.dirname(temp_config), exist_ok=True)
        with open(temp_config, "w", encoding="utf-8") as f:
            json.dump({"other": 1}, f)
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}


class TestSaveKeywords:
    def test_save_and_load(self, temp_config):
        save_keywords(["词1", "词2"], True)
        result = load_keywords()
        assert "词1" in result["keywords"]
        assert "词2" in result["keywords"]
        assert result["ocr_enabled"] is True

    def test_save_deduplicates(self, temp_config):
        save_keywords(["词1", "词1", "词2"], False)
        result = load_keywords()
        assert result["keywords"].count("词1") == 1


class TestAddKeyword:
    def test_add_new(self, temp_config):
        add_keyword("新词")
        result = load_keywords()
        assert "新词" in result["keywords"]

    def test_add_duplicate(self, temp_config):
        add_keyword("词1")
        add_keyword("词1")
        result = load_keywords()
        assert result["keywords"].count("词1") == 1

    def test_add_empty(self, temp_config):
        add_keyword("")
        result = load_keywords()
        assert "" not in result["keywords"]


class TestRemoveKeyword:
    def test_remove_existing(self, temp_config):
        add_keyword("词1")
        remove_keyword("词1")
        result = load_keywords()
        assert "词1" not in result["keywords"]

    def test_remove_nonexistent(self, temp_config):
        remove_keyword("不存在的词")
        result = load_keywords()
        assert "不存在的词" not in result["keywords"]
