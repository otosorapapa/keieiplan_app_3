"""Validation helpers for input and export routines."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def validate_input_payload(data: Mapping[str, Any]) -> list[str]:
    """Return a list of validation warnings for the uploaded dataset."""

    warnings: list[str] = []
    if not data:
        warnings.append("データが読み込まれていません。テンプレートをアップロードしてください。")
    return warnings


def is_ready_for_export(session_state: Mapping[str, Any]) -> bool:
    """Check whether the app has enough data for exports."""

    return bool(session_state)


def collect_validation_summary(messages: Iterable[str]) -> str:
    """Join validation messages into a bullet-friendly string."""

    return "\n".join(f"- {message}" for message in messages)
