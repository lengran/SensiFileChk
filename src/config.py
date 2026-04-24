import json
import os
import sys
import threading

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "keywords.json")

_DEFAULT_CONFIG = {"keywords": [], "ocr_enabled": False}

_config_lock = threading.Lock()

if sys.platform == "win32":
    import msvcrt

    def _lock_file_shared(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _lock_file_exclusive(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock_file_shared(f):
        fcntl.flock(f, fcntl.LOCK_SH)

    def _lock_file_exclusive(f):
        fcntl.flock(f, fcntl.LOCK_EX)

    def _unlock_file(f):
        fcntl.flock(f, fcntl.LOCK_UN)


def _ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_keywords() -> dict:
    _ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        return dict(_DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _lock_file_shared(f)
            try:
                data = json.load(f)
            finally:
                _unlock_file(f)
        if not isinstance(data, dict) or "keywords" not in data or "ocr_enabled" not in data:
            return dict(_DEFAULT_CONFIG)
        return data
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_CONFIG)


def save_keywords(keywords: list, ocr_enabled: bool) -> None:
    _ensure_config_dir()
    unique_keywords = list(dict.fromkeys(keywords))
    data = {"keywords": unique_keywords, "ocr_enabled": ocr_enabled}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        _lock_file_exclusive(f)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            _unlock_file(f)


def add_keywords(words: list[str]) -> None:
    with _config_lock:
        config = load_keywords()
        keywords = config["keywords"]
        changed = False
        for word in words:
            if word and word not in keywords:
                keywords.append(word)
                changed = True
        if changed:
            save_keywords(keywords, config["ocr_enabled"])


def add_keyword(word: str) -> None:
    with _config_lock:
        config = load_keywords()
        keywords = config["keywords"]
        if word and word not in keywords:
            keywords.append(word)
            save_keywords(keywords, config["ocr_enabled"])


def remove_keyword(word: str) -> None:
    with _config_lock:
        config = load_keywords()
        keywords = config["keywords"]
        if word in keywords:
            keywords.remove(word)
            save_keywords(keywords, config["ocr_enabled"])
            return True
    return False
