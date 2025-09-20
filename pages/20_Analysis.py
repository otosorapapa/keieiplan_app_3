"""Analytics page showing KPI dashboard, break-even analysis and cash flow."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from calc import (
    ITEMS,
    compute,
    generate_balance_sheet,
    generate_cash_flow,
    plan_from_models,
    summarize_plan_metrics,
)
from formatting import format_amount_with_unit, format_ratio
from state import ensure_session_defaults, load_finance_bundle
from theme import inject_theme

st.set_page_config(
    page_title="経営計画スタジオ｜Analysis",
    page_icon="📈",
    layout="wide",
)

inject_theme()
ensure_session_defaults()

settings_state: Dict[str, object] = st.session_state.get("finance_settings", {})
unit = str(settings_state.get("unit", "百万円"))
fte = Decimal(str(settings_state.get("fte", 20)))
fiscal_year = int(settings_state.get("fiscal_year", 2025))

bundle, has_custom_inputs = load_finance_bundle()
if not has_custom_inputs:
    st.info("Inputsページでデータを保存すると、分析結果が更新されます。以下は既定値サンプルです。")

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
bs_data = generate_balance_sheet(amounts, bundle.capex, bundle.loans, bundle.tax)
cf_data = generate_cash_flow(amounts, bundle.capex, bundle.loans, bundle.tax)

st.title("📈 KPI・損益分析")
st.caption(f"FY{fiscal_year} / 表示単位: {unit} / FTE: {fte}")

kpi_tab, be_tab, cash_tab = st.tabs(["KPIダッシュボード", "損益分岐点", "資金繰り"])

with kpi_tab:
    st.subheader("主要KPI")
    top_cols = st.columns(4)
    top_cols[0].metric("売上高", format_amount_with_unit(amounts.get("REV", Decimal("0")), unit))
    top_cols[1].metric("粗利", format_amount_with_unit(amounts.get("GROSS", Decimal("0")), unit))
    top_cols[2].metric("営業利益", format_amount_with_unit(amounts.get("OP", Decimal("0")), unit))
    top_cols[3].metric("経常利益", format_amount_with_unit(amounts.get("ORD", Decimal("0")), unit))

    ratio_cols = st.columns(3)
    ratio_cols[0].metric("粗利率", format_ratio(metrics.get("gross_margin")))
    ratio_cols[1].metric("営業利益率", format_ratio(metrics.get("op_margin")))
    ratio_cols[2].metric("経常利益率", format_ratio(metrics.get("ord_margin")))

    st.markdown("### PLサマリー")
    pl_rows: List[Dict[str, object]] = []
    for code, label, group in ITEMS:
        if code in {"BE_SALES", "PC_SALES", "PC_GROSS", "PC_ORD", "LDR"}:
            continue
        value = amounts.get(code, Decimal("0"))
        pl_rows.append({"カテゴリ": group, "項目": label, "金額": float(value)})
    pl_df = pd.DataFrame(pl_rows)
    st.dataframe(pl_df, use_container_width=True, hide_index=True)

    st.markdown("### コスト構成比")
    cost_codes = ["COGS_MAT", "COGS_LBR", "COGS_OUT_SRC", "COGS_OUT_CON", "COGS_OTH", "OPEX_H", "OPEX_K", "OPEX_DEP"]
    cost_rows = []
    revenue = amounts.get("REV", Decimal("0"))
    for code in cost_codes:
        label = next((lbl for item_code, lbl, _ in ITEMS if item_code == code), code)
        value = amounts.get(code, Decimal("0"))
        ratio = float((value / revenue) * Decimal("100")) if revenue > 0 else 0.0
        cost_rows.append({"項目": label, "金額": float(value), "売上比%": ratio})
    cost_df = pd.DataFrame(cost_rows)
    if not cost_df.empty:
        chart = (
            alt.Chart(cost_df)
            .mark_bar()
            .encode(
                x=alt.X("売上比%:Q", title="売上比率 (%)"),
                y=alt.Y("項目:N", sort="-x"),
                tooltip=["項目", alt.Tooltip("金額:Q", title="金額", format=","), alt.Tooltip("売上比%:Q", title="売上比", format=".1f")],
            )
            .properties(height=max(240, 20 * len(cost_df)))
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("コストデータが未設定です。")

with be_tab:
    st.subheader("損益分岐点分析")
    be_sales = metrics.get("breakeven", Decimal("0"))
    sales = amounts.get("REV", Decimal("0"))
    ratio = (be_sales / sales) if sales > 0 else Decimal("0")

    info_cols = st.columns(3)
    info_cols[0].metric("損益分岐点売上高", format_amount_with_unit(be_sales, unit))
    info_cols[1].metric("現在の売上高", format_amount_with_unit(sales, unit))
    info_cols[2].metric("安全余裕度", format_ratio(Decimal("1") - ratio if sales > 0 else Decimal("0")))

    st.progress(min(max(float(1 - ratio), 0.0), 1.0), "安全余裕度")
    st.caption("進捗バーは売上高が損益分岐点をどの程度上回っているかを可視化します。")

    st.markdown("### バランスシートのスナップショット")
    bs_rows = []
    for section, records in (("資産", bs_data["assets"]), ("負債・純資産", bs_data["liabilities"])):
        for name, value in records.items():
            bs_rows.append({"区分": section, "項目": name, "金額": float(value)})
    bs_df = pd.DataFrame(bs_rows)
    st.dataframe(bs_df, use_container_width=True, hide_index=True)

with cash_tab:
    st.subheader("キャッシュフロー")
    cf_rows = [{"区分": key, "金額": float(value)} for key, value in cf_data.items()]
    cf_df = pd.DataFrame(cf_rows)
    st.dataframe(cf_df, use_container_width=True, hide_index=True)

    chart = (
        alt.Chart(cf_df)
        .mark_bar()
        .encode(
            x=alt.X("区分:N", sort=None),
            y=alt.Y("金額:Q", title="金額", axis=alt.Axis(format="~s")),
            color=alt.Color("区分:N", legend=None),
            tooltip=["区分", alt.Tooltip("金額:Q", title="金額", format=",")],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)

    st.caption("営業CFには減価償却費を足し戻し、税引後利益を反映しています。投資CFはCapex、財務CFは利息支払を表します。")
