"""Financial calculation helpers used throughout the application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import pandas as pd

DEFAULT_METRICS: Mapping[str, float] = {
    "売上高": 0.0,
    "営業利益": 0.0,
    "営業CF": 0.0,
}


@dataclass
class Scenario:
    """Simple container for scenario planning results."""

    name: str
    revenue_multiplier: float
    operating_income: float
    cash_flow: float


def calculate_key_metrics(data: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Aggregate KPI metrics from the provided dataset."""

    if not data:
        return dict(DEFAULT_METRICS)

    metrics = dict(DEFAULT_METRICS)
    for key, value in data.items():
        if isinstance(value, (int, float)):
            metrics[key] = float(value)
    return metrics


def generate_scenarios() -> list[Scenario]:
    """Return placeholder scenario assumptions for the scenario page."""

    return [
        Scenario("ベース", 1.0, 0.0, 0.0),
        Scenario("強気", 1.1, 0.0, 0.0),
        Scenario("弱気", 0.9, 0.0, 0.0),
    ]


def scenarios_as_dataframe(scenarios: Iterable[Scenario]) -> pd.DataFrame:
    """Convert scenarios into a tabular representation."""

    return pd.DataFrame(
        [
            {
                "シナリオ": scenario.name,
                "売上高倍率": scenario.revenue_multiplier,
                "営業利益": scenario.operating_income,
                "営業CF": scenario.cash_flow,
            }
            for scenario in scenarios
        ]
    )


def generate_sensitivity_matrix() -> pd.DataFrame:
    """Return a template for sensitivity analysis results."""

    index = pd.Index([80, 90, 100, 110, 120], name="売上達成率 (%)")
    columns = ["営業利益 (百万円)"]
    data = [[0.0] for _ in index]
    return pd.DataFrame(data, index=index, columns=columns)


def build_segment_performance() -> pd.DataFrame:
    """Return a placeholder dataset for store / channel level performance."""

    return pd.DataFrame(
        {
            "セグメント": ["本店", "支店A", "支店B"],
            "売上高": [0.0, 0.0, 0.0],
            "営業利益": [0.0, 0.0, 0.0],
        }
    )


def estimate_funding_requirements(inputs: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Compute a simple funding requirement overview."""

    base = {"必要資金": 0.0, "返済期間": 0.0, "DSCR": 0.0}
    if not inputs:
        return base

    result = base.copy()
    for key in base:
        if key in inputs and isinstance(inputs[key], (int, float)):
            result[key] = float(inputs[key])
    return result
