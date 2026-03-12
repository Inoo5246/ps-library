"""Configurable directory paths — env vars pot fi suprascrise din settings.json."""
import os
from config import IMAGES_DIR, SAVES_DIR, DLC_DIR


def _get_dir(setting_key, env_default):
    """Prioritate: settings.json > env var > hardcoded default."""
    try:
        from db import load_settings
        val = load_settings().get(setting_key, "")
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    return env_default


def get_images_dir() -> str:
    return _get_dir("images_dir", IMAGES_DIR)


def get_saves_dir() -> str:
    return _get_dir("saves_dir", SAVES_DIR)


def get_dlc_dir() -> str:
    return _get_dir("dlc_dir", DLC_DIR)
