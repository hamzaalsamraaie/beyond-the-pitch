"""Load and expose settings.yaml as a typed dictionary."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get(section: str, key: str, default: Any = None) -> Any:
    return load_settings().get(section, {}).get(key, default)


def get_section(section: str) -> dict[str, Any]:
    return load_settings().get(section, {})


def reload() -> None:
    """Force a re-read of settings.yaml (used in tests)."""
    load_settings.cache_clear()
