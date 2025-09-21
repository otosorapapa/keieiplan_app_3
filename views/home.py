"""Render logic for the overview / tutorial home page."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

import pandas as pd
import streamlit as st

from calc import compute, plan_from_models, summarize_plan_metrics
from formatting import format_amount_with_unit, format_ratio
from state import ensure_session_defaults, load_finance_bundle
from sample_data import (
    SAMPLE_FISCAL_YEAR,
    apply_sample_data_to_session,
    sample_sales_csv_bytes,
    sample_sales_excel_bytes,
)
from theme import inject_theme
from ui.chrome import HeaderActions, render_app_footer, render_app_header, render_usage_guide_panel

UNIT_OPTIONS: List[str] = ["円換算なし", "円", "千円", "万円", "百万円", "千万円"]
CURRENCY_OPTIONS: Dict[str, Dict[str, str]] = {
    "JPY": {"label": "日本円 (¥)", "symbol": "¥"},
    "USD": {"label": "米ドル ($)", "symbol": "$"},
    "EUR": {"label": "ユーロ (€)", "symbol": "€"},
    "GBP": {"label": "英ポンド (£)", "symbol": "£"},
}
FORECAST_PERIOD_OPTIONS: Dict[int, str] = {
    1: "短期（1年）",
    2: "2年",
    3: "中期（3年）",
    4: "4年",
    5: "長期（5年）",
}
MONTH_CHOICES: List[int] = list(range(1, 13))
FTE_TOOLTIP = "FTE (Full-Time Equivalent) は1.0が常勤者1人、0.5が半分の労働量を示す単位です。"
DEFAULT_UNIT = "百万円"
DEFAULT_CURRENCY = "JPY"
DEFAULT_START_MONTH = 4
DEFAULT_FORECAST_YEARS = 3


def _safe_index(options: List, value, default: int = 0) -> int:
    try:
        return options.index(value)
    except ValueError:
        return default


def _currency_label(currency: str) -> str:
    info = CURRENCY_OPTIONS.get(str(currency).upper(), {})
    return info.get("label", str(currency).upper())


def _render_finance_control_panel(settings_state: Dict[str, object]) -> None:
    current_unit = str(settings_state.get("unit", DEFAULT_UNIT))
    current_currency = str(settings_state.get("currency", DEFAULT_CURRENCY)).upper()
    current_fiscal_year = int(settings_state.get("fiscal_year", 2025))
    current_start_month = int(settings_state.get("fiscal_year_start_month", DEFAULT_START_MONTH))
    current_forecast_years = int(settings_state.get("forecast_years", DEFAULT_FORECAST_YEARS))
    current_fte = float(settings_state.get("fte", 0.0))

    with st.container():
        st.markdown("### ⚙️ コントロールハブ")
        with st.form("finance_settings_form"):
            row1_col1, row1_col2 = st.columns(2)
            selected_unit = row1_col1.selectbox(
                "表示単位",
                UNIT_OPTIONS,
                index=_safe_index(UNIT_OPTIONS, current_unit, default=_safe_index(UNIT_OPTIONS, DEFAULT_UNIT)),
            )
            selected_currency = row1_col2.selectbox(
                "通貨",
                options=list(CURRENCY_OPTIONS.keys()),
                index=_safe_index(list(CURRENCY_OPTIONS.keys()), current_currency, default=_safe_index(list(CURRENCY_OPTIONS.keys()), DEFAULT_CURRENCY)),
                format_func=_currency_label,
            )

            row2_col1, row2_col2 = st.columns(2)
            fiscal_year_value = row2_col1.number_input(
                "会計年度",
                min_value=2000,
                max_value=2100,
                step=1,
                value=int(current_fiscal_year),
            )
            start_month_value = row2_col2.selectbox(
                "会計年度の開始月",
                options=MONTH_CHOICES,
                index=_safe_index(
                    MONTH_CHOICES,
                    current_start_month,
                    default=_safe_index(MONTH_CHOICES, DEFAULT_START_MONTH),
                ),
                format_func=lambda month: f"{month}月",
            )

            row3_col1, row3_col2 = st.columns(2)
            period_value = row3_col1.selectbox(
                "経営計画期間",
                options=list(FORECAST_PERIOD_OPTIONS.keys()),
                index=_safe_index(
                    list(FORECAST_PERIOD_OPTIONS.keys()),
                    current_forecast_years,
                    default=_safe_index(list(FORECAST_PERIOD_OPTIONS.keys()), DEFAULT_FORECAST_YEARS),
                ),
                format_func=lambda year: FORECAST_PERIOD_OPTIONS.get(year, f"{year}年"),
            )
            fte_value = row3_col2.number_input(
                "FTE（フルタイム換算）",
                min_value=0.0,
                step=0.1,
                value=float(current_fte),
                help=FTE_TOOLTIP,
            )

            submitted = st.form_submit_button("設定を更新")

        if submitted:
            updated = dict(settings_state)
            updated.update(
                {
                    "unit": selected_unit,
                    "currency": str(selected_currency).upper(),
                    "fiscal_year": int(fiscal_year_value),
                    "fiscal_year_start_month": int(start_month_value),
                    "forecast_years": int(period_value),
                    "fte": float(fte_value),
                }
            )
            st.session_state["finance_settings"] = updated
            st.toast("共通設定を更新しました", icon="✅")

    refreshed = st.session_state.get("finance_settings", settings_state)
    current_fte_decimal = Decimal(str(refreshed.get("fte", current_fte)))
    _render_fte_calculator(current_fte_decimal)


def _render_fte_calculator(current_fte: Decimal) -> None:
    with st.expander("🧮 FTE計算ツール", expanded=False):
        st.write("パートタイマーやアルバイトの人数からフルタイム換算値を算出します。")
        calc_col1, calc_col2 = st.columns(2)
        full_time_count = calc_col1.number_input(
            "常勤者（フルタイム）人数",
            min_value=0.0,
            step=1.0,
            key="fte_calc_full_time_count",
            value=st.session_state.get("fte_calc_full_time_count", 0.0),
        )
        part_time_count = calc_col2.number_input(
            "パート・アルバイト人数",
            min_value=0.0,
            step=1.0,
            key="fte_calc_part_time_count",
            value=st.session_state.get("fte_calc_part_time_count", 0.0),
        )
        part_time_hours = calc_col1.number_input(
            "1人あたり週勤務時間（平均）",
            min_value=0.0,
            max_value=80.0,
            step=0.5,
            key="fte_calc_part_time_hours",
            value=st.session_state.get("fte_calc_part_time_hours", 20.0),
        )
        full_time_hours = calc_col2.number_input(
            "フルタイム1人の週勤務時間",
            min_value=1.0,
            max_value=80.0,
            step=0.5,
            key="fte_calc_full_time_hours",
            value=st.session_state.get("fte_calc_full_time_hours", 40.0),
        )

        fte_from_part_time = 0.0
        if full_time_hours > 0:
            fte_from_part_time = float(part_time_count) * float(part_time_hours) / float(full_time_hours)
        total_fte = float(full_time_count) + fte_from_part_time
        delta_value = total_fte - float(current_fte)
        st.metric("換算FTE", f"{total_fte:.2f}", delta=f"{delta_value:+.2f}")
        st.caption("FTE = 常勤者人数 + パート人数 × (平均勤務時間 ÷ フルタイム勤務時間)")

        if st.button("計算結果をFTEに反映", key="apply_fte_from_calculator"):
            updated = dict(st.session_state.get("finance_settings", {}))
            updated["fte"] = round(total_fte, 2)
            st.session_state["finance_settings"] = updated
            st.toast(f"FTEを {total_fte:.2f} として保存しました", icon="👥")
            st.experimental_rerun()


def _forecast_summary_rows(
    amounts: Dict[str, Decimal],
    fiscal_year: int,
    forecast_years: int,
    unit: str,
    currency: str,
) -> List[Dict[str, str]]:
    metrics = [
        ("売上高", "REV"),
        ("粗利", "GROSS"),
        ("営業利益", "OP"),
        ("経常利益", "ORD"),
        ("当期純利益", "NET"),
    ]
    rows: List[Dict[str, str]] = []
    for label, key in metrics:
        base_value = Decimal(amounts.get(key, Decimal("0")))
        row = {"指標": label}
        for offset in range(forecast_years):
            column = f"FY{fiscal_year + offset}"
            row[column] = format_amount_with_unit(base_value, unit, currency=currency)
        rows.append(row)
    return rows


def _monthly_highlight_rows(
    statements, fiscal_year: int, unit: str, currency: str
) -> List[Dict[str, str]]:
    if not statements or not getattr(statements, "monthly", None):
        return []
    rows: List[Dict[str, str]] = []
    previous_month = None
    year_offset = 0
    for entry in statements.monthly:
        month_value = int(entry.month)
        if previous_month is not None and month_value < previous_month:
            year_offset += 1
        year_label = fiscal_year + year_offset
        label = f"{year_label}年{month_value:02d}月"
        rows.append(
            {
                "月": label,
                "売上高": format_amount_with_unit(entry.pl.get("REV", Decimal("0")), unit, currency=currency),
                "営業利益": format_amount_with_unit(entry.pl.get("OP", Decimal("0")), unit, currency=currency),
                "経常利益": format_amount_with_unit(entry.pl.get("ORD", Decimal("0")), unit, currency=currency),
            }
        )
        previous_month = month_value
    return rows


def render_home_page() -> None:
    """Render the home/overview page that appears in both root and pages menu."""

    inject_theme()
    ensure_session_defaults()

    header_actions: HeaderActions = render_app_header(
        title="経営計画スタジオ",
        subtitle="入力→分析→シナリオ→レポートをワンストップで。型安全な計算ロジックで意思決定をサポートします。",
    )

    if header_actions.toggled_help:
        st.session_state["show_usage_guide"] = not st.session_state.get("show_usage_guide", False)

    render_usage_guide_panel()

    with st.container():
        st.markdown(
            """
            <div class="hero-card">
                <h1>McKinsey Inspired 経営計画ダッシュボード</h1>
                <p>チャネル×商品×月次の売上設計からKPI分析、シナリオ比較、ドキュメント出力までを一気通貫で支援します。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    settings_state: Dict[str, object] = st.session_state.get("finance_settings", {})
    _render_finance_control_panel(settings_state)
    refreshed_settings: Dict[str, object] = st.session_state.get("finance_settings", settings_state)

    unit = str(refreshed_settings.get("unit", DEFAULT_UNIT))
    currency = str(refreshed_settings.get("currency", DEFAULT_CURRENCY)).upper()
    try:
        fte = Decimal(str(refreshed_settings.get("fte", 20)))
    except Exception:
        fte = Decimal("20")
    try:
        fiscal_year = int(refreshed_settings.get("fiscal_year", 2025))
    except Exception:
        fiscal_year = 2025
    try:
        start_month = int(refreshed_settings.get("fiscal_year_start_month", DEFAULT_START_MONTH))
    except Exception:
        start_month = DEFAULT_START_MONTH
    if start_month < 1 or start_month > 12:
        start_month = DEFAULT_START_MONTH
    try:
        forecast_years = int(refreshed_settings.get("forecast_years", DEFAULT_FORECAST_YEARS))
    except Exception:
        forecast_years = DEFAULT_FORECAST_YEARS
    if forecast_years <= 0:
        forecast_years = DEFAULT_FORECAST_YEARS

    bundle, has_custom_inputs = load_finance_bundle()
    sample_loaded = bool(st.session_state.get("sample_data_loaded", False))

    summary_tab, tutorial_tab = st.tabs(["概要", "チュートリアル"])

    with summary_tab:
        st.subheader("📌 現状サマリー")

        if not has_custom_inputs:
            st.info(
                "まだ入力データがありません。サンプルを読み込むか、Inputsページで売上・コストなどを登録しましょう。"
            )
            prompt_cols = st.columns([1.6, 1, 1])
            with prompt_cols[0]:
                if st.button(
                    "サンプルデータをロード",
                    use_container_width=True,
                    type="primary",
                ):
                    apply_sample_data_to_session()
                    st.toast("サンプルデータを読み込みました。各ページが起動済みです。", icon="📦")
                    st.experimental_rerun()
            sample_csv = sample_sales_csv_bytes()
            sample_excel = sample_sales_excel_bytes()
            with prompt_cols[1]:
                st.download_button(
                    "CSVサンプルDL",
                    data=sample_csv,
                    file_name=f"sample_sales_{SAMPLE_FISCAL_YEAR}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="sample_csv_download_home",
                )
            with prompt_cols[2]:
                st.download_button(
                    "ExcelサンプルDL",
                    data=sample_excel,
                    file_name=f"sample_sales_{SAMPLE_FISCAL_YEAR}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="sample_excel_download_home",
                )
            st.caption(
                "サンプルはカテゴリ・数量・月度（YYYY-MM）を含むデータセットです。オフラインで編集してテンプレートに貼り付けることもできます。"
            )
        elif sample_loaded:
            st.success("サンプルデータを適用中です。Inputsページで自社データに置き換えて保存してください。")

        plan_cfg = plan_from_models(
            bundle.sales,
            bundle.costs,
            bundle.capex,
            bundle.loans,
            bundle.tax,
            fte=fte,
            unit=unit,
            currency=currency,
            fiscal_year_start_month=start_month,
            forecast_years=forecast_years,
            working_capital=bundle.working_capital,
        )
        amounts = compute(plan_cfg)
        metrics = summarize_plan_metrics(amounts)

        metric_cols = st.columns(4)
        metric_cols[0].metric(
            "売上高",
            format_amount_with_unit(amounts.get("REV", Decimal("0")), unit, currency=currency),
        )
        metric_cols[1].metric("粗利率", format_ratio(metrics.get("gross_margin")))
        metric_cols[2].metric(
            "経常利益",
            format_amount_with_unit(amounts.get("ORD", Decimal("0")), unit, currency=currency),
        )
        metric_cols[3].metric(
            "損益分岐点売上高",
            format_amount_with_unit(metrics.get("breakeven"), unit, currency=currency),
        )

        currency_label = _currency_label(currency)
        period_label = FORECAST_PERIOD_OPTIONS.get(forecast_years, f"{forecast_years}年")
        st.caption(
            f"FY{fiscal_year}（{start_month}月開始） 計画 ｜ 通貨: {currency_label} ｜ 表示単位: {unit} ｜ 期間: {period_label} ｜ FTE: {fte:.2f}"
        )

        forecast_rows = _forecast_summary_rows(amounts, fiscal_year, forecast_years, unit, currency)
        if forecast_rows:
            st.markdown("### 計画期間サマリー")
            forecast_df = pd.DataFrame(forecast_rows).set_index("指標")
            st.dataframe(forecast_df, use_container_width=True)
            st.caption("※ 計画期間サマリーは現状、基準年度の数値を年度別に横展開しています。")

        statements = getattr(plan_cfg, "latest_statements", None)
        monthly_rows = _monthly_highlight_rows(statements, fiscal_year, unit, currency)
        if monthly_rows:
            st.markdown("### 月次ハイライト（起点調整済み）")
            monthly_df = pd.DataFrame(monthly_rows)
            st.dataframe(monthly_df, use_container_width=True)

        st.markdown("### 次のステップ")
        st.markdown(
            """
            1. **Inputs** ページで売上・原価・費用・投資・借入・税制を登録する
            2. **Analysis** ページでPL/BS/CFとKPIを確認し、損益分岐点や資金繰りをチェック
            3. **Scenarios** ページで感度分析やシナリオ比較を行い、意思決定を支援
            4. **Report** ページでPDF / Excel / Word を生成し、ステークホルダーと共有
            5. **Settings** ページで単位や言語、既定値をカスタマイズ
            """
        )

    with tutorial_tab:
        st.subheader("🧭 チュートリアル")
        st.markdown(
            """
            - **セッションの保持**: サイドバーのページ遷移でも入力値はセッションステートに保存されます。
            - **URLダイレクトアクセス**: 各ページは初期化時に既定値をロードし、入力が無くても破綻しないようにガードしています。
            - **型安全な計算**: すべての計算は Pydantic モデルを通じて検証され、通貨は Decimal 基本で処理されます。
            - **エラーハンドリング**: 入力チェックに失敗すると、赤いトーストとフィールド強調で異常値を通知します。
            """
        )

    render_app_footer(
        caption="© 経営計画スタジオ | 情報設計の最適化と精緻な財務モデリングを提供します。",
    )
