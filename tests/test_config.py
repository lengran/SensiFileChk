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
    add_keywords,
    remove_keyword,
)


class TestLoadKeywords:
    def test_load_empty(self, isolated_test_config):
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}

    def test_load_existing(self, isolated_test_config):
        data = {"keywords": ["词1", "词2"], "ocr_enabled": True}
        with open(isolated_test_config, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = load_keywords()
        assert result == data

    def test_load_corrupted_json(self, isolated_test_config):
        with open(isolated_test_config, "w") as f:
            f.write("{invalid json")
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}

    def test_load_missing_fields(self, isolated_test_config):
        with open(isolated_test_config, "w") as f:
            json.dump({"other": 1}, f)
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}


class TestSaveKeywords:
    def test_save_and_load(self, isolated_test_config):
        save_keywords(["词1", "词2"], True)
        result = load_keywords()
        assert "词1" in result["keywords"]
        assert "词2" in result["keywords"]
        assert result["ocr_enabled"] is True

    def test_save_deduplicates(self, isolated_test_config):
        save_keywords(["词1", "词1", "词2"], False)
        result = load_keywords()
        assert result["keywords"].count("词1") == 1

    def test_save_preserves_order(self, isolated_test_config):
        save_keywords(["词C", "词A", "词B"], False)
        result = load_keywords()
        assert result["keywords"] == ["词C", "词A", "词B"]


class TestAddKeyword:
    def test_add_new(self, isolated_test_config):
        add_keyword("新词")
        result = load_keywords()
        assert "新词" in result["keywords"]

    def test_add_duplicate(self, isolated_test_config):
        add_keyword("词1")
        add_keyword("词1")
        result = load_keywords()
        assert result["keywords"].count("词1") == 1

    def test_add_empty(self, isolated_test_config):
        add_keyword("")
        result = load_keywords()
        assert "" not in result["keywords"]


class TestAddKeywords:
    def test_batch_add(self, isolated_test_config):
        add_keywords(["词1", "词2", "词3"])
        result = load_keywords()
        assert "词1" in result["keywords"]
        assert "词2" in result["keywords"]
        assert "词3" in result["keywords"]

    def test_batch_add_deduplicates(self, isolated_test_config):
        add_keywords(["词1", "词1", "词2"])
        result = load_keywords()
        assert result["keywords"].count("词1") == 1


class TestRemoveKeyword:
    def test_remove_existing(self, isolated_test_config):
        add_keyword("词1")
        removed = remove_keyword("词1")
        result = load_keywords()
        assert "词1" not in result["keywords"]
        assert removed is True

    def test_remove_nonexistent(self, isolated_test_config):
        removed = remove_keyword("不存在的词")
        result = load_keywords()
        assert "不存在的词" not in result["keywords"]
        assert removed is False


class TestConcurrentWrite:
    def test_concurrent_add_keywords(self, isolated_test_config):
        """TC-CFG-007: 两个进程同时调用 save_keywords — 不丢失数据"""
        import threading

        words = [f"词{i}" for i in range(20)]
        errors = []

        def _add_word(word):
            try:
                add_keyword(word)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_add_word, args=(w,)) for w in words]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"并发写入出错: {errors}"
        result = load_keywords()
        for word in words:
            assert word in result["keywords"], f"并发写入丢失: {word}"


class TestMissingConfigFile:
    def test_load_returns_default_when_missing(self, isolated_test_config, monkeypatch):
        import src.config as cfg
        if os.path.exists(isolated_test_config):
            os.unlink(isolated_test_config)
        monkeypatch.setattr(cfg, "CONFIG_PATH", os.path.join(os.path.dirname(isolated_test_config), "nonexistent.json"))
        result = load_keywords()
        assert result == {"keywords": [], "ocr_enabled": False}

    def test_save_creates_file(self, isolated_test_config, monkeypatch):
        import src.config as cfg
        new_path = os.path.join(os.path.dirname(isolated_test_config), "new_keywords.json")
        monkeypatch.setattr(cfg, "CONFIG_PATH", new_path)
        if os.path.exists(new_path):
            os.unlink(new_path)
        save_keywords(["新词"], True)
        assert os.path.exists(new_path)
        with open(new_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "新词" in data["keywords"]
        assert data["ocr_enabled"] is True


class TestOcrToggle:
    def test_ocr_save_and_load(self, isolated_test_config):
        save_keywords(["词1"], True)
        result = load_keywords()
        assert result["ocr_enabled"] is True
        save_keywords(["词1"], False)
        result = load_keywords()
        assert result["ocr_enabled"] is False
