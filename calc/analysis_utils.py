"""Shared helpers for analysis and scenario visualisations."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from .pl import PlanConfig, compute, plan_from_models, summarize_plan_metrics
from .timeline import FinancialTimeline, build_financial_timeline
from models import FinanceBundle


def compute_plan_with_timeline(
    bundle: FinanceBundle,
    *,
    fte: Decimal,
    unit: str,
    horizon_years: int,
) -> Tuple[PlanConfig, Dict[str, Decimal], Dict[str, Decimal], FinancialTimeline]:
    """Return plan configuration, annual amounts, metrics and timeline."""

    plan_cfg = plan_from_models(
        bundle.sales,
        bundle.costs,
        bundle.capex,
        bundle.loans,
        bundle.tax,
        fte=fte,
        unit=unit,
    )
    amounts = compute(plan_cfg)
    metrics = summarize_plan_metrics(amounts)
    timeline = build_financial_timeline(bundle, plan_cfg, horizon_years=horizon_years)
    return plan_cfg, amounts, metrics, timeline


def build_fcf_steps_from_timeline(
    timeline: FinancialTimeline, year_index: int = 1
) -> List[Dict[str, float]]:
    monthly = timeline.monthly
    if monthly.empty:
        return []
    target = monthly[monthly["year_index"] == year_index]
    if target.empty:
        return []
    ebit = float(target["営業利益"].sum())
    taxes = float(target["法人税"].sum())
    depreciation = float(target["減価償却費"].sum())
    delta_wc = float(target["Δ運転資本"].sum())
    capex = float(target["投資CF"].sum())
    fcf = float(target["フリーCF"].sum())
    return [
        {"name": "EBIT", "value": ebit},
        {"name": "税金", "value": -taxes},
        {"name": "減価償却", "value": depreciation},
        {"name": "運転資本", "value": -delta_wc},
        {"name": "CAPEX", "value": capex},
        {"name": "FCF", "value": fcf},
    ]


def build_dscr_timeseries_from_timeline(
    timeline: FinancialTimeline, annual_cf: pd.DataFrame
) -> pd.DataFrame:
    loan_df = timeline.loan_schedule
    if loan_df.empty:
        return pd.DataFrame()
    cf_by_year = annual_cf.set_index("year_index") if "year_index" in annual_cf.columns else pd.DataFrame()
    loan_df = loan_df.sort_values("month")
    service = (
        loan_df.groupby("year_index")
        .agg(interest_sum=("interest", "sum"), principal_sum=("principal", "sum"), balance_start=("balance_start", "first"))
        .reset_index()
    )
    rows: List[Dict[str, float]] = []
    for _, row in service.iterrows():
        year = int(row["year_index"])
        debt_service = float(row["interest_sum"] + row["principal_sum"])
        operating_cf = (
            float(cf_by_year.at[year, "営業CF"]) if not cf_by_year.empty and year in cf_by_year.index else float("nan")
        )
        dscr = operating_cf / debt_service if debt_service > 0 else float("nan")
        balance_start = float(row["balance_start"])
        payback_years = balance_start / operating_cf if operating_cf > 0 else float("nan")
        rows.append({"年度": f"FY{year}", "DSCR": dscr, "債務償還年数": payback_years})
    return pd.DataFrame(rows)


__all__ = [
    "compute_plan_with_timeline",
    "build_fcf_steps_from_timeline",
    "build_dscr_timeseries_from_timeline",
]
