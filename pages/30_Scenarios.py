"""Scenario and sensitivity analysis page for multi-scenario planning."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from calc import (
    build_dscr_timeseries_from_timeline,
    compute_plan_with_timeline,
)
from formatting import UNIT_FACTORS, format_amount_with_unit, format_delta
from models import FinanceBundle
from state import ensure_session_defaults, load_finance_bundle
from theme import inject_theme

# Scenario constants ---------------------------------------------------------
SCENARIO_KEYS: Sequence[str] = ("baseline", "best", "worst")
SCENARIO_LABELS: Mapping[str, str] = {
    "baseline": "Baseline",
    "best": "Best",
    "worst": "Worst",
}
DEFAULT_SCENARIOS: Mapping[str, Mapping[str, float]] = {
    "baseline": {"customer_pct": 0.0, "price_pct": 0.0, "cost_pct": 0.0},
    "best": {"customer_pct": 0.1, "price_pct": 0.05, "cost_pct": -0.05},
    "worst": {"customer_pct": -0.1, "price_pct": -0.05, "cost_pct": 0.05},
}
VARIABLE_OPTIONS: Mapping[str, Mapping[str, str]] = {
    "customer": {"label": "客数", "field": "customer_pct"},
    "price": {"label": "単価", "field": "price_pct"},
    "cost": {"label": "原価率", "field": "cost_pct"},
}
METRIC_OPTIONS: Mapping[str, Mapping[str, str]] = {
    "sales": {"label": "売上高", "code": "REV", "kind": "currency"},
    "gross": {"label": "粗利", "code": "GROSS", "kind": "currency"},
    "ebit": {"label": "EBIT", "code": "OP", "kind": "currency"},
    "fcf": {"label": "フリーCF", "code": "FCF", "kind": "currency"},
    "dscr": {"label": "DSCR", "code": "DSCR", "kind": "multiple"},
}


# Cached core computations ---------------------------------------------------
@st.cache_data(show_spinner=False)
def compute_plan_and_timeline_cached(
    sales_data: Dict[str, object],
    costs_data: Dict[str, object],
    capex_data: Dict[str, object],
    loans_data: Dict[str, object],
    tax_data: Dict[str, object],
    fte_value: float,
    unit: str,
    horizon_years: int,
):
    """Return plan configuration, amounts, metrics and timeline via cache."""

    bundle = FinanceBundle.from_dict(
        {
            "sales": sales_data,
            "costs": costs_data,
            "capex": capex_data,
            "loans": loans_data,
            "tax": tax_data,
        }
    )
    return compute_plan_with_timeline(
        bundle,
        fte=Decimal(str(fte_value)),
        unit=unit,
        horizon_years=horizon_years,
    )


def _first_year_fcf(timeline) -> float:
    annual_cf = timeline.annual_cf
    if annual_cf.empty:
        return float("nan")
    first = annual_cf[annual_cf["year_index"] == 1]
    if first.empty:
        return float("nan")
    return float(first.iloc[0]["フリーCF"])


def _first_year_dscr(timeline) -> float:
    dscr_df = build_dscr_timeseries_from_timeline(timeline, timeline.annual_cf)
    if dscr_df.empty:
        return float("nan")
    value = dscr_df["DSCR"].iloc[0]
    return float(value) if pd.notna(value) else float("nan")


@st.cache_data(show_spinner=False)
def evaluate_scenario_cached(
    sales_data: Dict[str, object],
    costs_data: Dict[str, object],
    capex_data: Dict[str, object],
    loans_data: Dict[str, object],
    tax_data: Dict[str, object],
    fte_value: float,
    unit: str,
    horizon_years: int,
    customer_pct: float,
    price_pct: float,
    cost_pct: float,
):
    """Compute scenario outputs with percentage adjustments."""

    bundle = FinanceBundle.from_dict(
        {
            "sales": sales_data,
            "costs": costs_data,
            "capex": capex_data,
            "loans": loans_data,
            "tax": tax_data,
        }
    )

    sales_factor = (1.0 + float(customer_pct)) * (1.0 + float(price_pct))
    sales_factor = max(0.0, sales_factor)
    scenario_sales = bundle.sales.model_copy(deep=True)
    for item in scenario_sales.items:
        item.monthly.amounts = [amount * Decimal(str(sales_factor)) for amount in item.monthly.amounts]

    scenario_costs = bundle.costs.model_copy(deep=True)
    cost_factor = Decimal("1") + Decimal(str(cost_pct))
    for code, ratio in scenario_costs.variable_ratios.items():
        scenario_costs.variable_ratios[code] = min(
            max(ratio * cost_factor, Decimal("0")),
            Decimal("1"),
        )

    scenario_bundle = FinanceBundle(
        sales=scenario_sales,
        costs=scenario_costs,
        capex=bundle.capex.model_copy(deep=True),
        loans=bundle.loans.model_copy(deep=True),
        tax=bundle.tax.model_copy(deep=True),
    )
    plan_cfg, amounts, metrics, timeline = compute_plan_with_timeline(
        scenario_bundle,
        fte=Decimal(str(fte_value)),
        unit=unit,
        horizon_years=horizon_years,
    )
    fcf_value = _first_year_fcf(timeline)
    dscr_value = _first_year_dscr(timeline)
    return {
        "plan": plan_cfg,
        "amounts": amounts,
        "metrics": metrics,
        "fcf": fcf_value,
        "dscr": dscr_value,
    }

# Helpers -------------------------------------------------------------------
def _ensure_scenario_state() -> Dict[str, Dict[str, float]]:
    key = "scenario_presets_v2"
    if key not in st.session_state or not isinstance(st.session_state[key], dict):
        st.session_state[key] = deepcopy({k: dict(v) for k, v in DEFAULT_SCENARIOS.items()})
    else:
        store = st.session_state[key]
        for k, defaults in DEFAULT_SCENARIOS.items():
            if k not in store:
                store[k] = dict(defaults)
            else:
                for field, value in defaults.items():
                    store[k].setdefault(field, value)
    return st.session_state[key]


def _format_pct(value: float) -> str:
    if value is None or np.isnan(value):
        return "—"
    return f"{value * 100:+.1f}%"


def _format_multiple(value: float) -> str:
    if value is None or np.isnan(value):
        return "—"
    return f"{value:.2f}x"


def _format_multiple_delta(delta: float) -> str:
    if delta is None or np.isnan(delta) or abs(delta) < 1e-6:
        return "±0.00x"
    sign = "+" if delta > 0 else "-"
    return f"{sign}{abs(delta):.2f}x"


def _metric_value(result: Mapping[str, object], metric_key: str) -> float:
    spec = METRIC_OPTIONS[metric_key]
    if spec["code"] == "FCF":
        return float(result.get("fcf", float("nan")))
    if spec["code"] == "DSCR":
        return float(result.get("dscr", float("nan")))
    amounts = result.get("amounts", {})
    value = amounts.get(spec["code"], Decimal("nan"))
    return float(value) if not isinstance(value, float) else value


def _build_scenario_table(
    scenarios: Mapping[str, Mapping[str, float]],
    results: Mapping[str, Mapping[str, object]],
    unit: str,
) -> pd.DataFrame:
    base_result = results.get("baseline", {})
    base_amounts = base_result.get("amounts", {})
    base_fcf = float(base_result.get("fcf", float("nan")))
    base_dscr = float(base_result.get("dscr", float("nan")))

    rows: List[Dict[str, object]] = []
    for key in SCENARIO_KEYS:
        cfg = scenarios.get(key, {})
        result = results.get(key, {})
        amounts = result.get("amounts", {})
        fcf = float(result.get("fcf", float("nan")))
        dscr = float(result.get("dscr", float("nan")))

        row = {
            "シナリオ": SCENARIO_LABELS.get(key, key.title()),
            "客数前提": float(cfg.get("customer_pct", 0.0)),
            "単価前提": float(cfg.get("price_pct", 0.0)),
            "原価率前提": float(cfg.get("cost_pct", 0.0)),
        }
        for metric_key in ("REV", "GROSS", "OP"):
            value = amounts.get(metric_key, Decimal("nan"))
            base_value = base_amounts.get(metric_key, Decimal("nan"))
            row[metric_key] = value
            row[f"{metric_key}_delta"] = value - base_value
        row["FCF"] = fcf
        row["FCF_delta"] = fcf - base_fcf if not np.isnan(fcf) else float("nan")
        row["DSCR"] = dscr
        row["DSCR_delta"] = dscr - base_dscr if not np.isnan(dscr) else float("nan")
        rows.append(row)

    df = pd.DataFrame(rows)

    display_df = df.copy()
    display_df["客数前提"] = display_df["客数前提"].apply(_format_pct)
    display_df["単価前提"] = display_df["単価前提"].apply(_format_pct)
    display_df["原価率前提"] = display_df["原価率前提"].apply(_format_pct)

    for code, label in [("REV", "売上高"), ("GROSS", "粗利"), ("OP", "EBIT")]:
        display_df[label] = display_df[code].apply(lambda x: format_amount_with_unit(x, unit))
        display_df[f"{label}差分"] = display_df[f"{code}_delta"].apply(
            lambda x: format_delta(x, unit)
        )
        display_df.drop(columns=[code, f"{code}_delta"], inplace=True)

    display_df["フリーCF"] = display_df["FCF"].apply(lambda x: format_amount_with_unit(x, unit))
    display_df["フリーCF差分"] = display_df["FCF_delta"].apply(lambda x: format_delta(x, unit))
    display_df["DSCR"] = display_df["DSCR"].apply(_format_multiple)
    display_df["DSCR差分"] = display_df["DSCR_delta"].apply(_format_multiple_delta)
    display_df.drop(columns=["FCF", "FCF_delta", "DSCR_delta"], inplace=True)

    return display_df


@st.cache_data(show_spinner=False)
def compute_sensitivity_series(
    sales_data: Dict[str, object],
    costs_data: Dict[str, object],
    capex_data: Dict[str, object],
    loans_data: Dict[str, object],
    tax_data: Dict[str, object],
    fte_value: float,
    unit: str,
    horizon_years: int,
    variable: str,
    metric_key: str,
    values: Tuple[float, ...],
) -> pd.DataFrame:
    rows: List[Dict[str, float]] = []
    for value in values:
        adjustments = {"customer_pct": 0.0, "price_pct": 0.0, "cost_pct": 0.0}
        field = VARIABLE_OPTIONS[variable]["field"]
        adjustments[field] = float(value)
        result = evaluate_scenario_cached(
            sales_data,
            costs_data,
            capex_data,
            loans_data,
            tax_data,
            fte_value,
            unit,
            horizon_years,
            adjustments["customer_pct"],
            adjustments["price_pct"],
            adjustments["cost_pct"],
        )
        metric_value = _metric_value(result, metric_key)
        rows.append({"pct": value, "value": metric_value})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def compute_heatmap_matrix(
    sales_data: Dict[str, object],
    costs_data: Dict[str, object],
    capex_data: Dict[str, object],
    loans_data: Dict[str, object],
    tax_data: Dict[str, object],
    fte_value: float,
    unit: str,
    horizon_years: int,
    x_variable: str,
    y_variable: str,
    metric_key: str,
    x_values: Tuple[float, ...],
    y_values: Tuple[float, ...],
) -> pd.DataFrame:
    rows: List[Dict[str, float]] = []
    for x_val in x_values:
        for y_val in y_values:
            adjustments = {"customer_pct": 0.0, "price_pct": 0.0, "cost_pct": 0.0}
            adjustments[VARIABLE_OPTIONS[x_variable]["field"]] = float(x_val)
            adjustments[VARIABLE_OPTIONS[y_variable]["field"]] = float(y_val)
            result = evaluate_scenario_cached(
                sales_data,
                costs_data,
                capex_data,
                loans_data,
                tax_data,
                fte_value,
                unit,
                horizon_years,
                adjustments["customer_pct"],
                adjustments["price_pct"],
                adjustments["cost_pct"],
            )
            rows.append(
                {
                    "x": x_val,
                    "y": y_val,
                    "value": _metric_value(result, metric_key),
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def run_monte_carlo(
    sales_data: Dict[str, object],
    costs_data: Dict[str, object],
    capex_data: Dict[str, object],
    loans_data: Dict[str, object],
    tax_data: Dict[str, object],
    fte_value: float,
    unit: str,
    horizon_years: int,
    num_trials: int,
    means: Tuple[float, float, float],
    stds: Tuple[float, float, float],
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    draws = rng.normal(loc=np.array(means), scale=np.array(stds), size=(num_trials, 3))
    draws = np.clip(draws, -0.8, 1.0)

    rows: List[Dict[str, float]] = []
    for customer_pct, price_pct, cost_pct in draws:
        result = evaluate_scenario_cached(
            sales_data,
            costs_data,
            capex_data,
            loans_data,
            tax_data,
            fte_value,
            unit,
            horizon_years,
            float(customer_pct),
            float(price_pct),
            float(cost_pct),
        )
        amounts = result.get("amounts", {})
        rows.append(
            {
                "customer_pct": float(customer_pct),
                "price_pct": float(price_pct),
                "cost_pct": float(cost_pct),
                "売上高": float(amounts.get("REV", Decimal("nan"))),
                "粗利": float(amounts.get("GROSS", Decimal("nan"))),
                "EBIT": float(amounts.get("OP", Decimal("nan"))),
                "フリーCF": float(result.get("fcf", float("nan"))),
                "DSCR": float(result.get("dscr", float("nan"))),
            }
        )
    return pd.DataFrame(rows)

# Page layout ----------------------------------------------------------------
st.set_page_config(
    page_title="経営計画スタジオ｜Scenarios",
    page_icon="🧮",
    layout="wide",
)

inject_theme()
ensure_session_defaults()

settings_state: Dict[str, object] = st.session_state.get("finance_settings", {})
unit = str(settings_state.get("unit", "百万円"))
fte = float(settings_state.get("fte", 20.0))
fiscal_year = int(settings_state.get("fiscal_year", 2025))

bundle, has_custom_inputs = load_finance_bundle()
if not has_custom_inputs:
    st.info("Inputsページでデータを保存すると、分析結果が更新されます。以下は既定値サンプルです。")

sales_dump = bundle.sales.model_dump(mode="json")
costs_dump = bundle.costs.model_dump(mode="json")
capex_dump = bundle.capex.model_dump(mode="json")
loans_dump = bundle.loans.model_dump(mode="json")
tax_dump = bundle.tax.model_dump(mode="json")

DEFAULT_HORIZON_YEARS = 15
MONTE_CARLO_HORIZON = 10

plan_cfg, amounts, metrics, timeline = compute_plan_and_timeline_cached(
    sales_dump,
    costs_dump,
    capex_dump,
    loans_dump,
    tax_dump,
    fte,
    unit,
    horizon_years=DEFAULT_HORIZON_YEARS,
)

baseline_result = {
    "plan": plan_cfg,
    "amounts": amounts,
    "metrics": metrics,
    "fcf": _first_year_fcf(timeline),
    "dscr": _first_year_dscr(timeline),
}

scenario_presets = _ensure_scenario_state()

st.title("🧮 シナリオ分析スタジオ")
st.caption(f"FY{fiscal_year} / 表示単位: {unit} / FTE: {fte}")

scenario_col, info_col = st.columns([3, 2])
with scenario_col:
    st.subheader("シナリオ設定")
    with st.form("scenario_form"):
        st.markdown("Best / Worstシナリオのドライバーを調整します。")
        best_col, worst_col = st.columns(2)
        with best_col:
            st.markdown("**Best**")
            best_customer = st.slider(
                "客数変化 (best)",
                min_value=-50.0,
                max_value=50.0,
                value=float(scenario_presets["best"]["customer_pct"]) * 100,
                step=0.5,
                format="%+.1f%%",
            )
            best_price = st.slider(
                "単価変化 (best)",
                min_value=-50.0,
                max_value=50.0,
                value=float(scenario_presets["best"]["price_pct"]) * 100,
                step=0.5,
                format="%+.1f%%",
            )
            best_cost = st.slider(
                "原価率変化 (best)",
                min_value=-50.0,
                max_value=50.0,
                value=float(scenario_presets["best"]["cost_pct"]) * 100,
                step=0.5,
                format="%+.1f%%",
            )
        with worst_col:
            st.markdown("**Worst**")
            worst_customer = st.slider(
                "客数変化 (worst)",
                min_value=-50.0,
                max_value=50.0,
                value=float(scenario_presets["worst"]["customer_pct"]) * 100,
                step=0.5,
                format="%+.1f%%",
            )
            worst_price = st.slider(
                "単価変化 (worst)",
                min_value=-50.0,
                max_value=50.0,
                value=float(scenario_presets["worst"]["price_pct"]) * 100,
                step=0.5,
                format="%+.1f%%",
            )
            worst_cost = st.slider(
                "原価率変化 (worst)",
                min_value=-50.0,
                max_value=50.0,
                value=float(scenario_presets["worst"]["cost_pct"]) * 100,
                step=0.5,
                format="%+.1f%%",
            )
        submitted = st.form_submit_button("シナリオを更新")
    if submitted:
        scenario_presets["best"] = {
            "customer_pct": best_customer / 100.0,
            "price_pct": best_price / 100.0,
            "cost_pct": best_cost / 100.0,
        }
        scenario_presets["worst"] = {
            "customer_pct": worst_customer / 100.0,
            "price_pct": worst_price / 100.0,
            "cost_pct": worst_cost / 100.0,
        }
        st.session_state["scenario_presets_v2"] = scenario_presets
        st.success("シナリオ前提を更新しました。")

with info_col:
    st.subheader("Baseline主要値")
    metric_cols = st.columns(3)
    metric_cols[0].metric("売上高", format_amount_with_unit(amounts.get("REV", Decimal("0")), unit))
    metric_cols[1].metric("粗利", format_amount_with_unit(amounts.get("GROSS", Decimal("0")), unit))
    metric_cols[2].metric("EBIT", format_amount_with_unit(amounts.get("OP", Decimal("0")), unit))
    extra_cols = st.columns(2)
    extra_cols[0].metric("フリーCF", format_amount_with_unit(baseline_result["fcf"], unit))
    extra_cols[1].metric("DSCR", _format_multiple(baseline_result["dscr"]))
    st.caption("Baseline値はInputsページで設定した前提に基づきます。")

scenario_results: Dict[str, Mapping[str, object]] = {"baseline": baseline_result}
for key in ("best", "worst"):
    cfg = scenario_presets.get(key, DEFAULT_SCENARIOS[key])
    scenario_results[key] = evaluate_scenario_cached(
        sales_dump,
        costs_dump,
        capex_dump,
        loans_dump,
        tax_dump,
        fte,
        unit,
        horizon_years=DEFAULT_HORIZON_YEARS,
        customer_pct=float(cfg.get("customer_pct", 0.0)),
        price_pct=float(cfg.get("price_pct", 0.0)),
        cost_pct=float(cfg.get("cost_pct", 0.0)),
    )

st.markdown("### Baseline / Best / Worst 比較")
comparison_df = _build_scenario_table(scenario_presets, scenario_results, unit)
st.dataframe(comparison_df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("ドライバー感応度分析")
tornado_tab, curve_tab, heatmap_tab = st.tabs([
    "トルネードチャート",
    "単変量感度",
    "2Dヒートマップ",
])

with tornado_tab:
    tornado_metric = st.selectbox(
        "評価指標",
        options=list(METRIC_OPTIONS.keys()),
        format_func=lambda key: METRIC_OPTIONS[key]["label"],
        key="tornado_metric",
    )
    range_cols = st.columns(3)
    customer_width = range_cols[0].slider(
        "客数変化幅",
        min_value=0.0,
        max_value=50.0,
        value=10.0,
        step=0.5,
        format="%+.1f%%",
    )
    price_width = range_cols[1].slider(
        "単価変化幅",
        min_value=0.0,
        max_value=50.0,
        value=5.0,
        step=0.5,
        format="%+.1f%%",
    )
    cost_width = range_cols[2].slider(
        "原価率変化幅",
        min_value=0.0,
        max_value=50.0,
        value=5.0,
        step=0.5,
        format="%+.1f%%",
    )
    amplitude_map = {
        "customer": customer_width / 100.0,
        "price": price_width / 100.0,
        "cost": cost_width / 100.0,
    }
    baseline_metric = _metric_value(baseline_result, tornado_metric)
    tornado_rows: List[Dict[str, float]] = []
    for variable, amplitude in amplitude_map.items():
        for direction, sign in (("増加", 1.0), ("減少", -1.0)):
            adjustments = {"customer_pct": 0.0, "price_pct": 0.0, "cost_pct": 0.0}
            adjustments[VARIABLE_OPTIONS[variable]["field"]] = amplitude * sign
            result = evaluate_scenario_cached(
                sales_dump,
                costs_dump,
                capex_dump,
                loans_dump,
                tax_dump,
                fte,
                unit,
                horizon_years=DEFAULT_HORIZON_YEARS,
                customer_pct=adjustments["customer_pct"],
                price_pct=adjustments["price_pct"],
                cost_pct=adjustments["cost_pct"],
            )
            metric_value = _metric_value(result, tornado_metric)
            tornado_rows.append(
                {
                    "ドライバー": VARIABLE_OPTIONS[variable]["label"],
                    "方向": direction,
                    "値": metric_value,
                    "差分": metric_value - baseline_metric,
                }
            )
    tornado_df = pd.DataFrame(tornado_rows)
    if tornado_df.empty:
        st.info("分析するために変化幅を調整してください。")
    else:
        tornado_df["abs_diff"] = tornado_df["差分"].abs()
        order = (
            tornado_df.groupby("ドライバー")["abs_diff"].max().sort_values(ascending=True).index.tolist()
        )
        spec = METRIC_OPTIONS[tornado_metric]
        unit_factor = float(UNIT_FACTORS.get(unit, Decimal("1")))
        fig = go.Figure()
        colors = {"増加": "#00CC96", "減少": "#EF553B"}
        for direction in ["増加", "減少"]:
            subset = tornado_df[tornado_df["方向"] == direction]
            if subset.empty:
                continue
            if spec["kind"] == "currency":
                customdata = np.column_stack(
                    [
                        subset["値"].to_numpy(dtype=float) / unit_factor,
                        subset["差分"].to_numpy(dtype=float) / unit_factor,
                    ]
                )
                hovertemplate = (
                    f"%{{y}}<br>シナリオ値=%{{customdata[0]:,.2f}}{unit}"
                    f"<br>差分=%{{customdata[1]:+.2f}}{unit}<extra></extra>"
                )
                x_values = subset["差分"].to_numpy(dtype=float) / unit_factor
                y_values = subset["ドライバー"].tolist()
            else:
                customdata = np.column_stack([subset["値"].to_numpy(dtype=float)])
                hovertemplate = (
                    "%{y}<br>シナリオ値=%{customdata[0]:.2f}x"
                    "<br>差分=%{x:+.2f}x<extra></extra>"
                )
                x_values = subset["差分"].to_numpy(dtype=float)
                y_values = subset["ドライバー"].tolist()
            fig.add_trace(
                go.Bar(
                    name=direction,
                    y=y_values,
                    x=x_values,
                    orientation="h",
                    marker_color=colors[direction],
                    customdata=customdata,
                    hovertemplate=hovertemplate,
                )
            )
        fig.update_layout(
            barmode="relative",
            legend_title_text="",
            hovermode="y unified",
            margin=dict(t=40),
        )
        fig.update_yaxes(categoryorder="array", categoryarray=order)
        if spec["kind"] == "currency":
            fig.update_xaxes(title=f"{spec['label']}差分 ({unit})")
        else:
            fig.update_xaxes(title=f"{spec['label']}差分")
        baseline_display = (
            format_amount_with_unit(baseline_metric, unit)
            if spec["kind"] == "currency"
            else _format_multiple(baseline_metric)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Baseline {spec['label']}: {baseline_display}")

with curve_tab:
    st.markdown("単一ドライバーの感度を折れ線で表示します。")
    curve_cols = st.columns(3)
    variable_choice = curve_cols[0].selectbox(
        "対象ドライバー",
        options=list(VARIABLE_OPTIONS.keys()),
        format_func=lambda key: VARIABLE_OPTIONS[key]["label"],
        key="sensitivity_variable",
    )
    metric_choice = curve_cols[1].selectbox(
        "評価指標",
        options=list(METRIC_OPTIONS.keys()),
        format_func=lambda key: METRIC_OPTIONS[key]["label"],
        key="sensitivity_metric",
    )
    steps = curve_cols[2].slider("分割数", min_value=5, max_value=25, value=15)
    pct_range = st.slider(
        "変化レンジ",
        min_value=-50.0,
        max_value=50.0,
        value=(-10.0, 10.0),
        step=0.5,
        format="%+.1f%%",
    )
    pct_values = tuple(np.linspace(pct_range[0] / 100.0, pct_range[1] / 100.0, steps))
    sensitivity_df = compute_sensitivity_series(
        sales_dump,
        costs_dump,
        capex_dump,
        loans_dump,
        tax_dump,
        fte,
        unit,
        horizon_years=DEFAULT_HORIZON_YEARS,
        variable=variable_choice,
        metric_key=metric_choice,
        values=pct_values,
    )
    spec = METRIC_OPTIONS[metric_choice]
    unit_factor = float(UNIT_FACTORS.get(unit, Decimal("1")))
    baseline_metric = _metric_value(baseline_result, metric_choice)
    if spec["kind"] == "currency":
        y_values = sensitivity_df["value"].to_numpy(dtype=float) / unit_factor
        customdata = np.column_stack([y_values])
        hovertemplate = (
            f"変化=%{{x:.1%}}<br>{spec['label']}=%{{customdata[0]:,.2f}}{unit}<extra></extra>"
        )
        y_label = f"{spec['label']} ({unit})"
        baseline_y = baseline_metric / unit_factor
    else:
        y_values = sensitivity_df["value"].to_numpy(dtype=float)
        customdata = np.column_stack([y_values])
        hovertemplate = "変化=%{x:.1%}<br>値=%{customdata[0]:.2f}x<extra></extra>"
        y_label = spec["label"]
        baseline_y = baseline_metric
    fig = go.Figure(
        go.Scatter(
            x=sensitivity_df["pct"],
            y=y_values,
            mode="lines+markers",
            line=dict(color="#636EFA", width=3),
            marker=dict(size=6),
            hovertemplate=hovertemplate,
        )
    )
    fig.add_vline(x=0.0, line_dash="dot", line_color="#9e9e9e")
    fig.add_hline(y=baseline_y, line_dash="dash", line_color="#00CC96", annotation_text="Baseline")
    fig.update_layout(legend_title_text="", hovermode="x unified")
    fig.update_xaxes(title="変化率", tickformat="+.0%")
    fig.update_yaxes(title=y_label)
    st.plotly_chart(fig, use_container_width=True)

with heatmap_tab:
    st.markdown("2変数同時の感度をヒートマップで表示します。")
    with st.form("heatmap_form"):
        col_x, col_y = st.columns(2)
        heatmap_x = col_x.selectbox(
            "横軸ドライバー",
            options=list(VARIABLE_OPTIONS.keys()),
            format_func=lambda key: VARIABLE_OPTIONS[key]["label"],
            key="heatmap_x",
        )
        available_y = [key for key in VARIABLE_OPTIONS.keys() if key != heatmap_x]
        heatmap_y = col_y.selectbox(
            "縦軸ドライバー",
            options=available_y,
            format_func=lambda key: VARIABLE_OPTIONS[key]["label"],
            key="heatmap_y",
        )
        heatmap_metric = st.selectbox(
            "評価指標",
            options=list(METRIC_OPTIONS.keys()),
            format_func=lambda key: METRIC_OPTIONS[key]["label"],
            key="heatmap_metric",
        )
        range_cols = st.columns(2)
        x_range = range_cols[0].slider(
            "横軸レンジ",
            min_value=-50.0,
            max_value=50.0,
            value=(-10.0, 10.0),
            step=1.0,
            format="%+.0f%%",
        )
        y_range = range_cols[1].slider(
            "縦軸レンジ",
            min_value=-50.0,
            max_value=50.0,
            value=(-10.0, 10.0),
            step=1.0,
            format="%+.0f%%",
        )
        grid_steps = st.slider("分割数", min_value=5, max_value=15, value=9)
        heatmap_submitted = st.form_submit_button("ヒートマップを生成")
    if heatmap_submitted:
        x_values = tuple(np.linspace(x_range[0] / 100.0, x_range[1] / 100.0, grid_steps))
        y_values = tuple(np.linspace(y_range[0] / 100.0, y_range[1] / 100.0, grid_steps))
        heatmap_df = compute_heatmap_matrix(
            sales_dump,
            costs_dump,
            capex_dump,
            loans_dump,
            tax_dump,
            fte,
            unit,
            horizon_years=DEFAULT_HORIZON_YEARS,
            x_variable=heatmap_x,
            y_variable=heatmap_y,
            metric_key=heatmap_metric,
            x_values=x_values,
            y_values=y_values,
        )
        st.session_state["scenario_heatmap_result"] = {
            "df": heatmap_df,
            "x": heatmap_x,
            "y": heatmap_y,
            "metric": heatmap_metric,
            "x_range": x_range,
            "y_range": y_range,
            "steps": grid_steps,
        }
    heatmap_state = st.session_state.get("scenario_heatmap_result")
    if heatmap_state:
        heatmap_df = heatmap_state["df"].copy()
        if heatmap_df.empty:
            st.info("計算結果が空です。レンジを見直してください。")
        else:
            pivot = heatmap_df.pivot_table(index="y", columns="x", values="value")
            pivot = pivot.sort_index().sort_index(axis=1)
            spec = METRIC_OPTIONS[heatmap_state["metric"]]
            unit_factor = float(UNIT_FACTORS.get(unit, Decimal("1")))
            if spec["kind"] == "currency":
                z_values = pivot.to_numpy(dtype=float) / unit_factor
                z_label = f"{spec['label']} ({unit})"
                hovertemplate = (
                    f"{VARIABLE_OPTIONS[heatmap_state['y']]['label']}=%{{y:.1f}}%%"
                    f"<br>{VARIABLE_OPTIONS[heatmap_state['x']]['label']}=%{{x:.1f}}%%"
                    f"<br>{spec['label']}=%{{z:,.2f}}{unit}<extra></extra>"
                )
            else:
                z_values = pivot.to_numpy(dtype=float)
                z_label = spec["label"]
                hovertemplate = (
                    f"{VARIABLE_OPTIONS[heatmap_state['y']]['label']}=%{{y:.1f}}%%"
                    f"<br>{VARIABLE_OPTIONS[heatmap_state['x']]['label']}=%{{x:.1f}}%%"
                    f"<br>{spec['label']}=%{{z:.2f}}x<extra></extra>"
                )
            fig = go.Figure(
                go.Heatmap(
                    x=[value * 100 for value in pivot.columns],
                    y=[value * 100 for value in pivot.index],
                    z=z_values,
                    colorscale="RdBu",
                    reversescale=True,
                    colorbar=dict(title=z_label),
                    hovertemplate=hovertemplate,
                )
            )
            fig.update_xaxes(title=f"{VARIABLE_OPTIONS[heatmap_state['x']]['label']}変化率", tickformat="+.0%")
            fig.update_yaxes(title=f"{VARIABLE_OPTIONS[heatmap_state['y']]['label']}変化率", tickformat="+.0%")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ヒートマップを生成するには上記フォームで条件を設定してください。")

st.divider()
st.subheader("モンテカルロシミュレーション")
with st.form("mc_form"):
    col_trials, col_seed = st.columns([3, 1])
    trial_count = col_trials.slider("試行回数", min_value=50, max_value=1000, value=300, step=50)
    seed_value = col_seed.number_input("乱数シード", min_value=0, value=42, step=1)
    mc_cols = st.columns(3)
    customer_mean = mc_cols[0].number_input("客数平均(%)", value=0.0, step=0.5, format="%+.1f")
    customer_std = mc_cols[0].number_input("客数標準偏差(%)", value=5.0, step=0.5, min_value=0.0, format="%+.1f")
    price_mean = mc_cols[1].number_input("単価平均(%)", value=0.0, step=0.5, format="%+.1f")
    price_std = mc_cols[1].number_input("単価標準偏差(%)", value=3.0, step=0.5, min_value=0.0, format="%+.1f")
    cost_mean = mc_cols[2].number_input("原価率平均(%)", value=0.0, step=0.5, format="%+.1f")
    cost_std = mc_cols[2].number_input("原価率標準偏差(%)", value=2.5, step=0.5, min_value=0.0, format="%+.1f")
    mc_submitted = st.form_submit_button("シミュレーション実行")

if mc_submitted:
    mc_df = run_monte_carlo(
        sales_dump,
        costs_dump,
        capex_dump,
        loans_dump,
        tax_dump,
        fte,
        unit,
        horizon_years=MONTE_CARLO_HORIZON,
        num_trials=int(trial_count),
        means=(customer_mean / 100.0, price_mean / 100.0, cost_mean / 100.0),
        stds=(customer_std / 100.0, price_std / 100.0, cost_std / 100.0),
        seed=int(seed_value),
    )
    st.session_state["scenario_mc_result"] = {
        "df": mc_df,
        "trials": int(trial_count),
        "seed": int(seed_value),
    }

mc_state = st.session_state.get("scenario_mc_result")
if mc_state:
    mc_df = mc_state["df"].copy()
    summary_rows: List[Dict[str, object]] = []
    metrics_to_show = ["売上高", "粗利", "EBIT", "フリーCF", "DSCR"]
    for metric_name in metrics_to_show:
        series = mc_df[metric_name].dropna()
        if series.empty:
            continue
        summary_rows.append(
            {
                "指標": metric_name,
                "平均": series.mean(),
                "標準偏差": series.std(ddof=0),
                "P5": series.quantile(0.05),
                "P50": series.quantile(0.50),
                "P95": series.quantile(0.95),
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    display_df = summary_df.copy()
    unit_factor = float(UNIT_FACTORS.get(unit, Decimal("1")))
    for idx, row in display_df.iterrows():
        metric_name = row["指標"]
        kind = "multiple" if metric_name == "DSCR" else "currency"
        for column in ["平均", "標準偏差", "P5", "P50", "P95"]:
            value = row[column]
            if kind == "currency":
                display_df.at[idx, column] = format_amount_with_unit(value, unit)
            else:
                display_df.at[idx, column] = _format_multiple(value)
    st.markdown("#### 分布統計")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    unit_factor = float(UNIT_FACTORS.get(unit, Decimal("1")))
    hist_fig = make_subplots(rows=1, cols=2, subplot_titles=("フリーCF", "DSCR"))
    fcf_series = mc_df["フリーCF"].dropna()
    if not fcf_series.empty:
        hist_fig.add_trace(
            go.Histogram(
                x=fcf_series.to_numpy(dtype=float) / unit_factor,
                nbinsx=30,
                marker_color="#636EFA",
                name="フリーCF",
                hovertemplate=f"%{{x:,.2f}}{unit}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        hist_fig.update_xaxes(title_text=f"フリーCF ({unit})", row=1, col=1)
    dscr_series = mc_df["DSCR"].dropna()
    if not dscr_series.empty:
        hist_fig.add_trace(
            go.Histogram(
                x=dscr_series.to_numpy(dtype=float),
                nbinsx=30,
                marker_color="#EF553B",
                name="DSCR",
                hovertemplate="%{x:.2f}x<extra></extra>",
            ),
            row=1,
            col=2,
        )
        hist_fig.update_xaxes(title_text="DSCR (倍)", row=1, col=2)
    hist_fig.update_layout(
        showlegend=False,
        bargap=0.05,
        hovermode="x",
        margin=dict(t=60),
    )
    hist_fig.update_yaxes(title_text="頻度", row=1, col=1)
    hist_fig.update_yaxes(title_text="頻度", row=1, col=2)
    st.plotly_chart(hist_fig, use_container_width=True)
    st.caption(
        f"{mc_state['trials']}試行の結果。平均・分位は {unit} ベース (DSCRのみ倍率) で表示しています。"
    )
else:
    st.info("シミュレーションを実行すると、分布統計とヒストグラムを表示します。")
