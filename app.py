"""Streamlit entry point configuring navigation for the Keieiplan app."""

from __future__ import annotations

import streamlit as st


NAVIGATION_PAGES = [
    st.Page(
        "pages/1_ダッシュボード.py",
        title="ダッシュボード",
        icon=":chart_with_upwards_trend:",
        default=True,
    ),
    st.Page(
        "pages/2_データ入力.py",
        title="データ入力",
        icon=":pencil2:",
    ),
    st.Page(
        "pages/3_シナリオ&感度分析.py",
        title="シナリオ & 感度分析",
        icon=":game_die:",
    ),
    st.Page(
        "pages/4_店舗_部門_チャネル分析.py",
        title="店舗 / 部門 / チャネル分析",
        icon=":department_store:",
    ),
    st.Page(
        "pages/5_補助金_金融機関資料.py",
        title="補助金 / 金融機関資料",
        icon=":bank:",
    ),
    st.Page(
        "pages/6_エクスポート(PPTX_Excel).py",
        title="エクスポート (PPTX / Excel)",
        icon=":outbox_tray:",
    ),
]


def main() -> None:
    """Configure Streamlit and dispatch to the selected page."""

    st.set_page_config(
        page_title="経営計画ダッシュボード",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    navigation = st.navigation(NAVIGATION_PAGES, position="top")
    navigation.run()


if __name__ == "__main__":
    main()
