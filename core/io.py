"""Utilities for loading and persisting application input data."""

from __future__ import annotations

from typing import Any, Mapping

UploadedFile = Any


def load_uploaded_dataset(file: UploadedFile | None) -> dict[str, Any]:
    """Parse an uploaded dataset file.

    This is a lightweight placeholder that records metadata about the upload.
    Replace this logic with the actual parser for your financial templates.
    """

    if file is None:
        return {}

    return {
        "name": getattr(file, "name", "uploaded_file"),
        "size": getattr(file, "size", 0),
        "type": getattr(file, "type", "unknown"),
    }


def snapshot_session_state(session_state: Mapping[str, Any]) -> dict[str, Any]:
    """Return a plain dictionary copy of the Streamlit session state."""

    return {key: value for key, value in session_state.items()}
