"""Export utilities for generating downloadable artefacts."""

from __future__ import annotations

from typing import Any, Mapping


def export_plan_to_excel(data: Mapping[str, Any] | None = None) -> bytes:
    """Return an Excel workbook payload.

    Replace this with the real Excel export routine. The placeholder returns an
    empty workbook represented by a byte string so that download buttons remain
    interactive during UI development.
    """

    _ = data
    return b""


def export_plan_to_pptx(data: Mapping[str, Any] | None = None) -> bytes:
    """Return a PPTX presentation payload."""

    _ = data
    return b""
