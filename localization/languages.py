"""Language metadata used to drive localization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable


@dataclass(frozen=True)
class LanguageDefinition:
    """Information about a supported UI language."""

    code: str
    locale: str
    status: str
    default_tax_profile: str


LANGUAGE_DEFINITIONS: Dict[str, LanguageDefinition] = {
    "ja": LanguageDefinition(
        code="ja",
        locale="ja-JP",
        status="stable",
        default_tax_profile="jp_sme",
    ),
    "en": LanguageDefinition(
        code="en",
        locale="en-US",
        status="beta",
        default_tax_profile="us_standard",
    ),
    "zh-Hans": LanguageDefinition(
        code="zh-Hans",
        locale="zh-CN",
        status="preview",
        default_tax_profile="cn_standard",
    ),
    "ko": LanguageDefinition(
        code="ko",
        locale="ko-KR",
        status="preview",
        default_tax_profile="kr_standard",
    ),
}

DEFAULT_LANGUAGE = "ja"


def get_language_definition(code: str) -> LanguageDefinition:
    """Return the metadata for *code* raising ``KeyError`` if unknown."""

    if code not in LANGUAGE_DEFINITIONS:
        raise KeyError(f"Unsupported language code: {code}")
    return LANGUAGE_DEFINITIONS[code]


def available_languages() -> Iterable[LanguageDefinition]:
    """Iterate through the configured language definitions."""

    return LANGUAGE_DEFINITIONS.values()


__all__ = [
    "DEFAULT_LANGUAGE",
    "LanguageDefinition",
    "LANGUAGE_DEFINITIONS",
    "available_languages",
    "get_language_definition",
]
