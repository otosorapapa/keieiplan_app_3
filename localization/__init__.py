"""Convenience helpers for localization, language selection and tax presets."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, List

import streamlit as st

from models import TaxPolicy

from .languages import (
    DEFAULT_LANGUAGE,
    LanguageDefinition,
    available_languages,
    get_language_definition,
)
from .tax_profiles import TaxProfile, available_tax_profiles, get_tax_profile
from .translations import available_translation_files, get_translation


@dataclass(frozen=True)
class LanguageStatus:
    """Computed state describing the active language."""

    code: str
    label: str
    status: str
    locale: str
    default_tax_profile: str


def _normalize_language(code: str) -> str:
    if not code:
        return DEFAULT_LANGUAGE
    try:
        get_language_definition(code)
    except KeyError:
        return DEFAULT_LANGUAGE
    return code


def list_language_codes() -> List[str]:
    """Return the configured language codes."""

    return [definition.code for definition in available_languages()]


def list_tax_profile_codes() -> List[str]:
    """Return the configured tax profile codes."""

    return [profile.code for profile in available_tax_profiles()]


def get_current_language() -> str:
    """Return the language code stored in the current session state."""

    settings = st.session_state.get("finance_settings", {})
    if isinstance(settings, dict):
        return _normalize_language(str(settings.get("language", DEFAULT_LANGUAGE)))
    return DEFAULT_LANGUAGE


def translation(key: str, *, language: str | None = None) -> Any:
    """Fetch the raw translation entry for ``key``."""

    language_code = language or get_current_language()
    return get_translation(key, language_code=language_code, fallback_language=DEFAULT_LANGUAGE)


def translate(key: str, *, language: str | None = None, **kwargs: Any) -> str:
    """Return the localized string for ``key`` with optional formatting."""

    value = translation(key, language=language)
    if isinstance(value, str):
        if kwargs:
            try:
                return value.format(**kwargs)
            except Exception:  # pragma: no cover - defensive, keep untranslated
                return value
        return value
    if value is None:
        return key
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return "\n".join(str(item) for item in value)
    return str(value)


def translate_list(key: str, *, language: str | None = None) -> List[str]:
    """Return a translation list for ``key`` falling back to an empty list."""

    value = translation(key, language=language)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def get_language_label(code: str, *, language: str | None = None) -> str:
    return translate(f"languages.{code}.label", language=language)


def get_tax_profile_label(code: str, *, language: str | None = None) -> str:
    return translate(f"tax_profiles.{code}.label", language=language)


def get_language_status(language_code: str | None = None) -> LanguageStatus:
    """Return the presentation metadata for ``language_code``."""

    code = _normalize_language(language_code or get_current_language())
    definition = get_language_definition(code)
    return LanguageStatus(
        code=code,
        label=get_language_label(code, language=code),
        status=definition.status,
        locale=definition.locale,
        default_tax_profile=definition.default_tax_profile,
    )


def update_language(language_code: str, *, tax_profile: str | None = None) -> None:
    """Update the UI language stored in the session state."""

    definition = get_language_definition(_normalize_language(language_code))
    current_settings = dict(st.session_state.get("finance_settings", {}))
    current_settings["language"] = definition.code
    current_settings["locale"] = definition.locale

    if tax_profile is None:
        tax_profile = current_settings.get("tax_profile", definition.default_tax_profile)
    current_settings["tax_profile"] = tax_profile

    st.session_state["finance_settings"] = current_settings


def apply_tax_profile(profile_code: str) -> TaxPolicy:
    """Apply the tax profile to the session settings and models."""

    profile = get_tax_profile(profile_code)
    policy = TaxPolicy(
        corporate_tax_rate=profile.corporate_tax_rate,
        consumption_tax_rate=profile.consumption_tax_rate,
        dividend_payout_ratio=Decimal("0.0"),
    )

    models_state: Dict[str, Any] = dict(st.session_state.get("finance_models", {}))
    models_state["tax"] = policy
    st.session_state["finance_models"] = models_state

    settings_state: Dict[str, Any] = dict(st.session_state.get("finance_settings", {}))
    settings_state["tax_profile"] = profile.code
    st.session_state["finance_settings"] = settings_state

    return policy


def get_tax_profile_details(profile_code: str, *, language: str | None = None) -> Dict[str, Any]:
    """Return metadata and numeric assumptions for ``profile_code``."""

    profile = get_tax_profile(profile_code)
    lang = language or get_current_language()
    return {
        "code": profile.code,
        "label": get_tax_profile_label(profile.code, language=lang),
        "country": profile.country,
        "corporate_tax_rate": profile.corporate_tax_rate,
        "consumption_tax_rate": profile.consumption_tax_rate,
        "social_insurance_rate": profile.social_insurance_rate,
        "depreciation": translate(profile.depreciation_key, language=lang),
        "description": translate_list(f"tax_profiles.{profile.code}.description", language=lang),
    }


def render_language_status_alert() -> None:
    """Render a warning banner when the active language is not stable."""

    status = get_language_status()
    if status.status == "stable":
        return
    status_label = translate(f"languages.status_labels.{status.status}")
    message = translate(f"languages.status_messages.{status.status}")
    st.warning(f"**{status_label}** — {message}")


def ensure_language_defaults() -> None:
    """Create default session entries when missing."""

    if "finance_settings" not in st.session_state:
        st.session_state["finance_settings"] = {
            "language": DEFAULT_LANGUAGE,
            "locale": get_language_definition(DEFAULT_LANGUAGE).locale,
            "tax_profile": get_language_definition(DEFAULT_LANGUAGE).default_tax_profile,
        }
    else:
        settings = st.session_state["finance_settings"]
        if not isinstance(settings, dict):
            st.session_state["finance_settings"] = {
                "language": DEFAULT_LANGUAGE,
                "locale": get_language_definition(DEFAULT_LANGUAGE).locale,
                "tax_profile": get_language_definition(DEFAULT_LANGUAGE).default_tax_profile,
            }
            return
        if "language" not in settings:
            settings["language"] = DEFAULT_LANGUAGE
        if "locale" not in settings:
            settings["locale"] = get_language_definition(settings["language"]).locale
        if "tax_profile" not in settings:
            settings["tax_profile"] = get_language_definition(settings["language"]).default_tax_profile


__all__ = [
    "LanguageStatus",
    "apply_tax_profile",
    "available_translation_files",
    "ensure_language_defaults",
    "get_current_language",
    "get_language_label",
    "get_language_status",
    "get_tax_profile_details",
    "get_tax_profile_label",
    "list_language_codes",
    "list_tax_profile_codes",
    "render_language_status_alert",
    "translate",
    "translate_list",
    "translation",
    "update_language",
]
