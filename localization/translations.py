"""Translation file loading helpers."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@lru_cache(maxsize=None)
def _load_translations(language_code: str) -> Mapping[str, Any]:
    """Load the translation dictionary for *language_code* from disk."""

    path = _LOCALES_DIR / f"{language_code}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_key(data: Mapping[str, Any], key: str) -> Any | None:
    """Return the value referenced by ``key`` in a nested mapping."""

    current: Any = data
    for segment in key.split("."):
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
        else:
            return None
    return current


def get_translation(
    key: str,
    *,
    language_code: str,
    fallback_language: str | None = None,
) -> Any | None:
    """Return the translation entry for *key* in *language_code*.

    The function falls back to *fallback_language* when the key is not
    available in the requested language. ``None`` is returned if the key
    cannot be resolved in either language.
    """

    try:
        data = _load_translations(language_code)
    except FileNotFoundError:
        if fallback_language and fallback_language != language_code:
            return get_translation(key, language_code=fallback_language)
        return None

    value = _resolve_key(data, key)
    if value is not None:
        return value
    if fallback_language and fallback_language != language_code:
        return get_translation(key, language_code=fallback_language)
    return None


def available_translation_files() -> list[str]:
    """Return the list of language codes with translation files."""

    if not _LOCALES_DIR.exists():
        return []
    return [path.stem for path in _LOCALES_DIR.glob("*.json")]


__all__ = [
    "available_translation_files",
    "get_translation",
]
