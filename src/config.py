import json
import os
import fcntl

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "keywords.json")

_DEFAULT_CONFIG = {"keywords": [], "ocr_enabled": False}


def _ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_keywords() -> dict:
    _ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        return dict(_DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        if not isinstance(data, dict) or "keywords" not in data or "ocr_enabled" not in data:
            return dict(_DEFAULT_CONFIG)
        return data
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_CONFIG)


def save_keywords(keywords: list, ocr_enabled: bool) -> None:
    _ensure_config_dir()
    data = {"keywords": sorted(set(keywords)), "ocr_enabled": ocr_enabled}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def add_keyword(word: str) -> None:
    config = load_keywords()
    keywords = config["keywords"]
    if word and word not in keywords:
        keywords.append(word)
    save_keywords(keywords, config["ocr_enabled"])


def remove_keyword(word: str) -> None:
    config = load_keywords()
    keywords = config["keywords"]
    if word in keywords:
        keywords.remove(word)
    save_keywords(keywords, config["ocr_enabled"])
