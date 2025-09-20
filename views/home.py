"""Render logic for the overview / tutorial home page."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict

import streamlit as st

from calc import compute, plan_from_models, summarize_plan_metrics
from formatting import format_amount_with_unit, format_ratio
from state import ensure_session_defaults, load_finance_bundle, reset_app_state
from sample_data import (
    SAMPLE_FISCAL_YEAR,
    apply_sample_data_to_session,
    sample_sales_csv_bytes,
    sample_sales_excel_bytes,
)
from theme import inject_theme
from ui.chrome import HeaderActions, render_app_footer, render_app_header, render_usage_guide_panel


def render_home_page() -> None:
    """Render the home/overview page that appears in both root and pages menu."""

    inject_theme()
    ensure_session_defaults()

    header_actions: HeaderActions = render_app_header(
        title="経営計画スタジオ",
        subtitle="入力→分析→シナリオ→レポートをワンストップで。型安全な計算ロジックで意思決定をサポートします。",
    )

    if header_actions.reset_requested:
        reset_app_state()
        st.experimental_rerun()

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
    unit = str(settings_state.get("unit", "百万円"))
    fte = Decimal(str(settings_state.get("fte", 20)))
    fiscal_year = int(settings_state.get("fiscal_year", 2025))

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
            working_capital=bundle.working_capital,
        )
        amounts = compute(plan_cfg)
        metrics = summarize_plan_metrics(amounts)

        metric_cols = st.columns(4)
        metric_cols[0].metric("売上高", format_amount_with_unit(amounts.get("REV", Decimal("0")), unit))
        metric_cols[1].metric("粗利率", format_ratio(metrics.get("gross_margin")))
        metric_cols[2].metric("経常利益", format_amount_with_unit(amounts.get("ORD", Decimal("0")), unit))
        metric_cols[3].metric("損益分岐点売上高", format_amount_with_unit(metrics.get("breakeven"), unit))

        st.caption(f"FY{fiscal_year} 計画 ｜ 表示単位: {unit} ｜ FTE: {fte}")

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
