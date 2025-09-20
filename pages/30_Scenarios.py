"""Scenario and sensitivity analysis page."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from calc import compute, plan_from_models, summarize_plan_metrics
from formatting import (
    format_amount_with_unit,
    format_delta,
    format_ratio,
    format_ratio_delta,
)
from state import ensure_session_defaults, load_finance_bundle
from theme import inject_theme

st.set_page_config(
    page_title="経営計画スタジオ｜Scenarios",
    page_icon="🧮",
    layout="wide",
)

inject_theme()
ensure_session_defaults()

settings_state: Dict[str, object] = st.session_state.get("finance_settings", {})
unit = str(settings_state.get("unit", "百万円"))
fte = Decimal(str(settings_state.get("fte", 20)))

bundle, has_custom_inputs = load_finance_bundle()
if not has_custom_inputs:
    st.info("入力データが未保存のため、既定値でシナリオを算出しています。")

plan_cfg = plan_from_models(
    bundle.sales,
    bundle.costs,
    bundle.capex,
    bundle.loans,
    bundle.tax,
    fte=fte,
    unit=unit,
)
base_amounts = compute(plan_cfg)
base_metrics = summarize_plan_metrics(base_amounts)

st.title("🧮 シナリオ / 感度分析")

sensitivity_tab, scenario_tab = st.tabs(["感度分析", "シナリオ比較"])

cogs_codes = ["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC", "COGS_OUT_CON", "COGS_OTH"]
opex_codes = ["OPEX_H", "OPEX_K", "OPEX_DEP"]

with sensitivity_tab:
    st.subheader("キー変数の感度分析")
    st.caption("売上高、原価、販管費の変動が経常利益に与える影響を試算します。")

    col1, col2, col3 = st.columns(3)
    sales_pct = Decimal(str(col1.slider("売上高変動 (%)", min_value=-30, max_value=30, value=0, step=1))) / Decimal("100")
    cogs_pct = Decimal(str(col2.slider("原価変動 (%)", min_value=-20, max_value=20, value=0, step=1))) / Decimal("100")
    opex_pct = Decimal(str(col3.slider("販管費変動 (%)", min_value=-20, max_value=20, value=0, step=1))) / Decimal("100")

    sales_override = plan_cfg.base_sales * (Decimal("1") + sales_pct)
    amount_overrides: Dict[str, Decimal] = {}
    for code in cogs_codes:
        amount_overrides[code] = base_amounts.get(code, Decimal("0")) * (Decimal("1") + cogs_pct)
    for code in opex_codes:
        amount_overrides[code] = base_amounts.get(code, Decimal("0")) * (Decimal("1") + opex_pct)

    sensitivity_amounts = compute(plan_cfg, sales_override=sales_override, amount_overrides=amount_overrides)
    sensitivity_metrics = summarize_plan_metrics(sensitivity_amounts)

    metric_cols = st.columns(3)
    metric_cols[0].metric(
        "売上高",
        format_amount_with_unit(sensitivity_amounts.get("REV", Decimal("0")), unit),
        delta=format_delta(sensitivity_amounts.get("REV", Decimal("0")) - base_amounts.get("REV", Decimal("0")), unit),
    )
    metric_cols[1].metric(
        "粗利率",
        format_ratio(sensitivity_metrics.get("gross_margin")),
        delta=format_ratio_delta(
            (sensitivity_metrics.get("gross_margin", Decimal("0")) or Decimal("0"))
            - (base_metrics.get("gross_margin", Decimal("0")) or Decimal("0"))
        ),
    )
    metric_cols[2].metric(
        "経常利益",
        format_amount_with_unit(sensitivity_amounts.get("ORD", Decimal("0")), unit),
        delta=format_delta(sensitivity_amounts.get("ORD", Decimal("0")) - base_amounts.get("ORD", Decimal("0")), unit),
    )

    chart_df = pd.DataFrame(
        {
            "項目": ["売上高", "経常利益"],
            "ベース": [float(base_amounts.get("REV", Decimal("0"))), float(base_amounts.get("ORD", Decimal("0")))],
            "シナリオ": [
                float(sensitivity_amounts.get("REV", Decimal("0"))),
                float(sensitivity_amounts.get("ORD", Decimal("0"))),
            ],
        }
    )
    chart_df = chart_df.melt(id_vars="項目", var_name="ケース", value_name="金額")
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("項目:N", sort=None),
            y=alt.Y("金額:Q", axis=alt.Axis(format="~s")),
            color=alt.Color("ケース:N", scale=alt.Scale(range=["#8FA9C4", "#F2C57C"])),
            column=alt.Column("ケース:N", header=alt.Header(labelOrient="bottom")),
        )
    )
    st.altair_chart(chart, use_container_width=True)

with scenario_tab:
    st.subheader("シナリオ比較")
    st.caption("売上・原価・販管費の変動率を設定し、ベースとの比較を行います。")

    default_scenarios = [
        {"シナリオ": "Base", "売上%": 0.0, "原価%": 0.0, "販管費%": 0.0},
        {"シナリオ": "Optimistic", "売上%": 10.0, "原価%": -3.0, "販管費%": -2.0},
        {"シナリオ": "Conservative", "売上%": -5.0, "原価%": 2.0, "販管費%": 1.0},
    ]
    scenario_state = st.session_state.setdefault("scenario_table", default_scenarios)
    scenario_df = pd.DataFrame(scenario_state)
    edited_df = st.data_editor(
        scenario_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "売上%": st.column_config.NumberColumn("売上変化%", min_value=-50.0, max_value=50.0, step=1.0),
            "原価%": st.column_config.NumberColumn("原価変化%", min_value=-30.0, max_value=30.0, step=1.0),
            "販管費%": st.column_config.NumberColumn("販管費変化%", min_value=-30.0, max_value=30.0, step=1.0),
        },
        hide_index=True,
        key="scenario_editor_table",
    )
    st.session_state["scenario_table"] = edited_df.to_dict(orient="records")

    comparison_rows = []
    for _, row in edited_df.iterrows():
        name = str(row.get("シナリオ", "Case")).strip() or "Case"
        sales_factor = Decimal("1") + Decimal(str(row.get("売上%", 0.0))) / Decimal("100")
        cogs_factor = Decimal("1") + Decimal(str(row.get("原価%", 0.0))) / Decimal("100")
        opex_factor = Decimal("1") + Decimal(str(row.get("販管費%", 0.0))) / Decimal("100")

        overrides: Dict[str, Decimal] = {}
        for code in cogs_codes:
            overrides[code] = base_amounts.get(code, Decimal("0")) * cogs_factor
        for code in opex_codes:
            overrides[code] = base_amounts.get(code, Decimal("0")) * opex_factor

        scenario_amounts = compute(plan_cfg, sales_override=plan_cfg.base_sales * sales_factor, amount_overrides=overrides)
        scenario_metrics = summarize_plan_metrics(scenario_amounts)

        comparison_rows.append(
            {
                "シナリオ": name,
                "売上高": format_amount_with_unit(scenario_amounts.get("REV", Decimal("0")), unit),
                "経常利益": format_amount_with_unit(scenario_amounts.get("ORD", Decimal("0")), unit),
                "経常利益率": format_ratio(scenario_metrics.get("ord_margin")),
                "Δ売上": format_delta(
                    scenario_amounts.get("REV", Decimal("0")) - base_amounts.get("REV", Decimal("0")), unit
                ),
                "Δ経常利益": format_delta(
                    scenario_amounts.get("ORD", Decimal("0")) - base_amounts.get("ORD", Decimal("0")), unit
                ),
                "売上高数値": float(scenario_amounts.get("REV", Decimal("0"))),
                "経常利益数値": float(scenario_amounts.get("ORD", Decimal("0"))),
            }
        )

    comparison_df = pd.DataFrame(comparison_rows)
    display_df = comparison_df.drop(columns=["売上高数値", "経常利益数値"], errors="ignore")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    chart_df = comparison_df.copy()
    if not chart_df.empty:
        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("シナリオ:N", sort=None),
                y=alt.Y("経常利益数値:Q", axis=alt.Axis(format="~s")),
                color=alt.Color("シナリオ:N", legend=None),
                tooltip=["シナリオ", "経常利益", "経常利益率"],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, use_container_width=True)
