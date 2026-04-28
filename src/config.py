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


def _atomic_read_write(read_data, modify_fn):
    _ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(dict(_DEFAULT_CONFIG), f, ensure_ascii=False, indent=2)
    with open(CONFIG_PATH, "r+", encoding="utf-8") as f:
        _lock_file_exclusive(f)
        try:
            raw = json.load(f)
            if not isinstance(raw, dict) or "keywords" not in raw or "ocr_enabled" not in raw:
                raw = dict(_DEFAULT_CONFIG)
            config = modify_fn(raw)
            f.seek(0)
            f.truncate()
            json.dump(config, f, ensure_ascii=False, indent=2)
        finally:
            _unlock_file(f)
    return config


def add_keywords(words: list[str]) -> None:
    with _config_lock:
        def _modify(config):
            keywords = config["keywords"]
            for word in words:
                if word and word not in keywords:
                    keywords.append(word)
            return config
        _atomic_read_write(None, _modify)


def add_keyword(word: str) -> None:
    def _modify(config):
        keywords = config["keywords"]
        if word and word not in keywords:
            keywords.append(word)
        return config
    _atomic_read_write(None, _modify)


def remove_keyword(word: str) -> None:
    def _modify(config):
        keywords = config["keywords"]
        if word in keywords:
            keywords.remove(word)
        return config
    
    result = _atomic_read_write(None, _modify)
    return word not in result.get("keywords", [word])
