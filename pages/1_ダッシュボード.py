from __future__ import annotations

import streamlit as st

from core import charts, finance, strategy
from localization import render_language_status_alert, translate
from state import load_finance_bundle


def _render_strategy_overview() -> None:
    st.markdown("### 戦略フレームワークハイライト")

    bsc_state = st.session_state.get("strategy_bsc", {})
    pest_state = st.session_state.get("strategy_pest", {})
    swot_state = st.session_state.get("strategy_swot", {})

    has_any = (
        strategy.has_bsc_entries(bsc_state)
        or strategy.has_pest_entries(pest_state)
        or strategy.has_swot_entries(swot_state)
    )

    if not has_any:
        st.info("設定ページのBSC・PEST・SWOTに入力するとここに要約が表示されます。")
        return

    if strategy.has_bsc_entries(bsc_state):
        st.markdown("#### バランス・スコアカード")
        bsc_frame = strategy.build_bsc_display_frame(bsc_state)
        st.dataframe(bsc_frame, use_container_width=True, hide_index=True)
    else:
        st.caption("BSCは未登録です。")

    if strategy.has_pest_entries(pest_state):
        st.markdown("#### PESTサマリー")
        pest_map = strategy.build_pest_display(pest_state)
        pest_cols = st.columns(2)
        for index, (label, entries) in enumerate(pest_map.items()):
            column = pest_cols[index % 2]
            with column:
                st.markdown(f"**{label}**")
                if entries:
                    for entry in entries:
                        st.markdown(f"- {entry}")
                else:
                    st.caption("未入力です。")
    else:
        st.caption("PESTは未登録です。")

    if strategy.has_swot_entries(swot_state):
        st.markdown("#### SWOTサマリー")
        swot_map = strategy.build_swot_display(swot_state)
        swot_cols = st.columns(2)
        for index, (label, entries) in enumerate(swot_map.items()):
            column = swot_cols[index % 2]
            with column:
                st.markdown(f"**{label}**")
                if entries:
                    for entry in entries:
                        st.markdown(f"- {entry}")
                else:
                    st.caption("未入力です。")

        settings = st.session_state.get("finance_settings", {})
        unit = str(settings.get("unit", "百万円"))
        currency = str(settings.get("currency", "JPY"))
        bundle, _ = load_finance_bundle()
        finance_summary = strategy.summarize_financial_context(bundle)
        suggestions = strategy.generate_swot_suggestions(
            swot_state,
            pest_state,
            finance_summary,
            unit=unit,
            currency=currency,
            bsc_state=bsc_state,
        )
        if suggestions:
            st.markdown("**AIサポートコメント**")
            for suggestion in suggestions:
                st.markdown(f"- {suggestion}")
    else:
        st.caption("SWOTは未登録です。")


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.dashboard.title"))
    st.caption(translate("pages.dashboard.caption"))

    metrics = finance.calculate_key_metrics()
    charts.display_metric_overview(metrics)

    _render_strategy_overview()

    st.markdown(f"### {translate('pages.dashboard.todo_header')}")
    st.info(translate("pages.dashboard.todo_description"))


if __name__ == "__main__":
    main()
