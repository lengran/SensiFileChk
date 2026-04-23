"""
测试共享配置 - 跨测试文件共享的 fixtures
"""
import os
import json
import pytest
import sys


@pytest.fixture(autouse=True)
def isolated_test_config(tmp_path, monkeypatch):
    """
    自动在每个测试中使用独立的配置
    """
    import src.config as cfg
    config_dir = str(tmp_path / "config")
    config_path = os.path.join(config_dir, "keywords.json")
    os.makedirs(config_dir, exist_ok=True)

    # 初始化为空配置
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"keywords": [], "ocr_enabled": False}, f)

    # 修补配置模块
    monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg, "CONFIG_PATH", config_path)

    yield config_path

    # 清理
    if os.path.exists(config_path):
        try:
            os.remove(config_path)
            os.rmdir(config_dir)
        except:
            pass


@pytest.fixture
def temp_config(tmp_path, monkeypatch, isolated_test_config):
    """
    返回临时配置文件路径（由 isolated_test_config 自动设置）
    """
    return isolated_test_config


@pytest.fixture
def reset_config(isolated_test_config):
    """
    重置配置为默认空状态
    """
    import src.config as cfg
    from src.config import save_keywords
    # 确保配置路径已设置
    save_keywords([], False)
    yield
    # 清理
    save_keywords([], False)
