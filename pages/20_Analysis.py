"""Analytics page showing KPI dashboard, break-even analysis and cash flow."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from calc import (
    ITEMS,
    build_dscr_timeseries_from_timeline,
    build_fcf_steps_from_timeline,
    compute_plan_with_timeline,
)
from formatting import format_amount_with_unit, format_ratio
from models import FinanceBundle
from state import ensure_session_defaults, load_finance_bundle
from theme import inject_theme

ITEM_LABELS = {code: label for code, label, _ in ITEMS}


def _to_decimal(value: object) -> Decimal:
    return Decimal(str(value))


@st.cache_data(show_spinner=False)
def build_cost_composition(amounts_data: Dict[str, str]) -> pd.DataFrame:
    component_codes = [
        "COGS_MAT",
        "COGS_LBR",
        "COGS_OUT_SRC",
        "COGS_OUT_CON",
        "COGS_OTH",
        "OPEX_H",
        "OPEX_K",
        "OPEX_DEP",
        "NOE_INT",
        "NOE_OTH",
    ]
    rows: List[Dict[str, float]] = []
    for code in component_codes:
        value = _to_decimal(amounts_data.get(code, "0"))
        if value <= 0:
            continue
        rows.append({"項目": ITEM_LABELS.get(code, code), "金額": float(value)})
    return pd.DataFrame(rows)


def _cost_structure(
    plan_items: Dict[str, Dict[str, str]], amounts_data: Dict[str, str]
) -> Tuple[Decimal, Decimal]:
    sales_total = _to_decimal(amounts_data.get("REV", "0"))
    gross_total = _to_decimal(amounts_data.get("GROSS", "0"))
    variable_cost = Decimal("0")
    fixed_cost = Decimal("0")
    for cfg in plan_items.values():
        method = str(cfg.get("method", ""))
        base = str(cfg.get("rate_base", "sales"))
        value = _to_decimal(cfg.get("value", "0"))
        if method == "rate":
            if base == "gross":
                ratio = gross_total / sales_total if sales_total else Decimal("0")
                variable_cost += sales_total * (value * ratio)
            elif base == "sales":
                variable_cost += sales_total * value
            elif base == "fixed":
                fixed_cost += value
        else:
            fixed_cost += value
    variable_rate = variable_cost / sales_total if sales_total else Decimal("0")
    return variable_rate, fixed_cost


@st.cache_data(show_spinner=False)
def build_cvp_dataframe(
    plan_items: Dict[str, Dict[str, str]], amounts_data: Dict[str, str]
) -> Tuple[pd.DataFrame, Decimal, Decimal, Decimal]:
    variable_rate, fixed_cost = _cost_structure(plan_items, amounts_data)
    sales_total = _to_decimal(amounts_data.get("REV", "0"))
    max_sales = sales_total * Decimal("1.3") if sales_total else Decimal("1000000")
    max_sales_float = max(float(max_sales), float(sales_total)) if sales_total else float(max_sales)
    sales_values = np.linspace(0, max_sales_float if max_sales_float > 0 else 1.0, 40)
    rows: List[Dict[str, float]] = []
    for sale in sales_values:
        sale_decimal = _to_decimal(sale)
        total_cost = fixed_cost + variable_rate * sale_decimal
        rows.append(
            {
                "売上高": float(sale_decimal),
                "総費用": float(total_cost),
            }
        )
    breakeven = _to_decimal(amounts_data.get("BE_SALES", "0"))
    return pd.DataFrame(rows), variable_rate, fixed_cost, breakeven


@st.cache_data(show_spinner=False)
def compute_plan_and_timeline(
    sales_data: Dict[str, object],
    costs_data: Dict[str, object],
    capex_data: Dict[str, object],
    loans_data: Dict[str, object],
    tax_data: Dict[str, object],
    fte_value: float,
    unit: str,
    horizon_years: int,
) -> Tuple["PlanConfig", Dict[str, Decimal], Dict[str, Decimal], "FinancialTimeline"]:
    bundle = FinanceBundle.from_dict(
        {
            "sales": sales_data,
            "costs": costs_data,
            "capex": capex_data,
            "loans": loans_data,
            "tax": tax_data,
        }
    )
    plan_cfg, amounts, metrics, timeline = compute_plan_with_timeline(
        bundle,
        fte=Decimal(str(fte_value)),
        unit=unit,
        horizon_years=horizon_years,
    )
    return plan_cfg, amounts, metrics, timeline


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

sales_dump = bundle.sales.model_dump(mode="json")
costs_dump = bundle.costs.model_dump(mode="json")
capex_dump = bundle.capex.model_dump(mode="json")
loans_dump = bundle.loans.model_dump(mode="json")
tax_dump = bundle.tax.model_dump(mode="json")

plan_cfg, amounts, metrics, timeline = compute_plan_and_timeline(
    sales_dump,
    costs_dump,
    capex_dump,
    loans_dump,
    tax_dump,
    float(fte),
    unit,
    horizon_years=15,
)

plan_items_serialized = {
    code: {
        "method": str(cfg.get("method", "")),
        "rate_base": str(cfg.get("rate_base", "sales")),
        "value": str(cfg.get("value", "0")),
    }
    for code, cfg in plan_cfg.items.items()
}
amounts_serialized = {code: str(value) for code, value in amounts.items()}
monthly_pl_df = timeline.monthly_pl.copy()
monthly_pl_df = monthly_pl_df[monthly_pl_df["year_index"] == 1].copy()
monthly_pl_df["month"] = monthly_pl_df["calendar_month"].apply(lambda m: f"{int(m)}月")
cost_df = build_cost_composition(amounts_serialized)
cvp_df, variable_rate, fixed_cost, breakeven_sales = build_cvp_dataframe(
    plan_items_serialized, amounts_serialized
)
fcf_steps = build_fcf_steps_from_timeline(timeline)
dscr_df = build_dscr_timeseries_from_timeline(timeline, timeline.annual_cf)
annual_cf_df = timeline.annual_cf.copy()
annual_bs_df = timeline.annual_bs.copy()
annual_pl_df = timeline.annual_pl.copy()

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

    monthly_pl_fig = go.Figure()
    monthly_pl_fig.add_trace(
        go.Bar(
            name='売上原価',
            x=monthly_pl_df['month'],
            y=monthly_pl_df['売上原価'],
            marker_color='#FF9F43',
            hovertemplate='月=%{x}<br>売上原価=¥%{y:,.0f}<extra></extra>',
        )
    )
    monthly_pl_fig.add_trace(
        go.Bar(
            name='販管費',
            x=monthly_pl_df['month'],
            y=monthly_pl_df['販管費'],
            marker_color='#636EFA',
            hovertemplate='月=%{x}<br>販管費=¥%{y:,.0f}<extra></extra>',
        )
    )
    monthly_pl_fig.add_trace(
        go.Bar(
            name='営業利益',
            x=monthly_pl_df['month'],
            y=monthly_pl_df['営業利益'],
            marker_color='#00CC96',
            hovertemplate='月=%{x}<br>営業利益=¥%{y:,.0f}<extra></extra>',
        )
    )
    monthly_pl_fig.add_trace(
        go.Scatter(
            name='売上高',
            x=monthly_pl_df['month'],
            y=monthly_pl_df['売上高'],
            mode='lines+markers',
            line=dict(color='#EF553B', width=3),
            hovertemplate='月=%{x}<br>売上高=¥%{y:,.0f}<extra></extra>',
        )
    )
    monthly_pl_fig.update_layout(
        barmode='stack',
        hovermode='x unified',
        legend_title_text='',
        yaxis_title='金額 (円)',
        yaxis_tickformat=',',
    )

    st.markdown('### 月次PL（スタック棒）')
    st.plotly_chart(monthly_pl_fig, use_container_width=True)

    trend_cols = st.columns(2)
    with trend_cols[0]:
        margin_fig = go.Figure()
        margin_fig.add_trace(
            go.Scatter(
                x=monthly_pl_df['month'],
                y=(monthly_pl_df['粗利率'] * 100).round(4),
                mode='lines+markers',
                name='粗利率',
                line=dict(color='#AB63FA'),
                hovertemplate='月=%{x}<br>粗利率=%{y:.1f}%<extra></extra>',
            )
        )
        margin_fig.update_layout(
            hovermode='x unified',
            yaxis_title='粗利率 (%)',
            yaxis_ticksuffix='%',
            legend_title_text='',
        )
        st.markdown('#### 粗利率推移')
        st.plotly_chart(margin_fig, use_container_width=True)

    with trend_cols[1]:
        st.markdown('#### 費用構成ドーナツ')
        if not cost_df.empty:
            cost_fig = go.Figure(
                go.Pie(
                    labels=cost_df['項目'],
                    values=cost_df['金額'],
                    hole=0.55,
                    textinfo='label+percent',
                    hovertemplate='%{label}: ¥%{value:,.0f}<extra></extra>',
                )
            )
            cost_fig.update_layout(legend_title_text='')
            st.plotly_chart(cost_fig, use_container_width=True)
        else:
            st.info('費用構成を表示するデータがありません。')

    st.markdown('### FCFウォーターフォール')
    fcf_labels = [step['name'] for step in fcf_steps]
    fcf_values = [step['value'] for step in fcf_steps]
    fcf_measures = ['relative'] * (len(fcf_values) - 1) + ['total']
    fcf_fig = go.Figure(
        go.Waterfall(
            name='FCF',
            orientation='v',
            measure=fcf_measures,
            x=fcf_labels,
            y=fcf_values,
            text=[f"¥{value:,.0f}" for value in fcf_values],
            hovertemplate='%{x}: ¥%{y:,.0f}<extra></extra>',
        )
    )
    fcf_fig.update_layout(showlegend=False, yaxis_title='金額 (円)')
    st.plotly_chart(fcf_fig, use_container_width=True)

    st.markdown('### PLサマリー')
    pl_rows: List[Dict[str, object]] = []
    for code, label, group in ITEMS:
        if code in {'BE_SALES', 'PC_SALES', 'PC_GROSS', 'PC_ORD', 'LDR'}:
            continue
        value = amounts.get(code, Decimal('0'))
        pl_rows.append({'カテゴリ': group, '項目': label, '金額': float(value)})
    pl_df = pd.DataFrame(pl_rows)
    st.dataframe(pl_df, use_container_width=True, hide_index=True)

with be_tab:
    st.subheader("損益分岐点分析")
    be_sales = metrics.get("breakeven", Decimal("0"))
    sales = amounts.get("REV", Decimal("0"))
    if isinstance(be_sales, Decimal) and be_sales.is_finite() and sales > 0:
        ratio = be_sales / sales
    else:
        ratio = Decimal("0")
    safety_margin = Decimal("1") - ratio if sales > 0 else Decimal("0")

    info_cols = st.columns(3)
    info_cols[0].metric("損益分岐点売上高", format_amount_with_unit(be_sales, unit))
    info_cols[1].metric("現在の売上高", format_amount_with_unit(sales, unit))
    info_cols[2].metric("安全余裕度", format_ratio(safety_margin))

    st.progress(min(max(float(safety_margin), 0.0), 1.0), "安全余裕度")
    st.caption("進捗バーは売上高が損益分岐点をどの程度上回っているかを可視化します。")

    cvp_fig = go.Figure()
    cvp_fig.add_trace(
        go.Scatter(
            name='売上線',
            x=cvp_df['売上高'],
            y=cvp_df['売上高'],
            mode='lines',
            line=dict(color='#636EFA'),
            hovertemplate='売上高=¥%{x:,.0f}<extra></extra>',
        )
    )
    cvp_fig.add_trace(
        go.Scatter(
            name='総費用線',
            x=cvp_df['売上高'],
            y=cvp_df['総費用'],
            mode='lines',
            line=dict(color='#EF553B'),
            hovertemplate='売上高=¥%{x:,.0f}<br>総費用=¥%{y:,.0f}<extra></extra>',
        )
    )
    if isinstance(breakeven_sales, Decimal) and breakeven_sales.is_finite() and breakeven_sales > 0:
        be_value = float(breakeven_sales)
        cvp_fig.add_trace(
            go.Scatter(
                name='損益分岐点',
                x=[be_value],
                y=[be_value],
                mode='markers',
                marker=dict(color='#00CC96', size=12, symbol='diamond'),
                hovertemplate='損益分岐点=¥%{x:,.0f}<extra></extra>',
            )
        )
    cvp_fig.update_layout(
        xaxis_title='売上高 (円)',
        yaxis_title='金額 (円)',
        hovermode='x unified',
        legend_title_text='',
    )

    st.markdown('### CVPチャート')
    st.plotly_chart(cvp_fig, use_container_width=True)
    st.caption(
        f"変動費率: {format_ratio(variable_rate)} ／ 固定費: {format_amount_with_unit(fixed_cost, unit)}"
    )

    st.markdown("### バランスシートのスナップショット")
    if not annual_bs_df.empty:
        bs_display = annual_bs_df.drop(columns=["year_index"], errors="ignore").copy()
        st.dataframe(bs_display, use_container_width=True, hide_index=True)
    else:
        st.info("バランスシートを表示するためのデータが不足しています。")

with cash_tab:
    st.subheader("キャッシュフロー")
    if not annual_cf_df.empty:
        cf_display = annual_cf_df.drop(columns=["year_index"], errors="ignore").copy()
        st.dataframe(cf_display, use_container_width=True, hide_index=True)

        cf_fig = go.Figure()
        cf_colors = {
            "営業CF": "#636EFA",
            "投資CF": "#EF553B",
            "財務CF": "#00CC96",
            "フリーCF": "#AB63FA",
        }
        for column, color in cf_colors.items():
            if column in cf_display.columns:
                cf_fig.add_trace(
                    go.Bar(
                        name=column,
                        x=cf_display["年度"],
                        y=cf_display[column],
                        marker_color=color,
                        hovertemplate="年度=%{x}<br>" + column + "=¥%{y:,.0f}<extra></extra>",
                    )
                )
        cf_fig.update_layout(barmode="group", yaxis_title="金額 (円)", legend_title_text="")
        st.plotly_chart(cf_fig, use_container_width=True)
    else:
        st.info("キャッシュフローを表示するデータがありません。")

    st.markdown('### DSCR / 債務償還年数')
    if not dscr_df.empty:
        dscr_fig = make_subplots(specs=[[{'secondary_y': True}]])
        dscr_fig.add_trace(
            go.Scatter(
                x=dscr_df['年度'],
                y=dscr_df['DSCR'],
                name='DSCR',
                mode='lines+markers',
                line=dict(color='#636EFA'),
                hovertemplate='%{x}: %{y:.2f}x<extra></extra>',
            ),
            secondary_y=False,
        )
        dscr_fig.add_trace(
            go.Scatter(
                x=dscr_df['年度'],
                y=dscr_df['債務償還年数'],
                name='債務償還年数',
                mode='lines+markers',
                line=dict(color='#EF553B'),
                hovertemplate='%{x}: %{y:.1f}年<extra></extra>',
            ),
            secondary_y=True,
        )
        dscr_fig.update_yaxes(title_text='DSCR (倍)', secondary_y=False)
        dscr_fig.update_yaxes(title_text='債務償還年数 (年)', secondary_y=True)
        dscr_fig.update_layout(hovermode='x unified', legend_title_text='')
        st.plotly_chart(dscr_fig, use_container_width=True)
    else:
        st.info('借入データが未登録のため、DSCRを算出できません。')

    st.caption("営業CFには減価償却費を足し戻し、税引後利益を反映しています。投資CFはCAPEX、財務CFは利息・元本・配当を表します。")
