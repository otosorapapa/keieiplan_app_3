"""Streamlit entry point configuring navigation for the Keieiplan app."""

from __future__ import annotations

from functools import partial

import streamlit as st

from localization import ensure_language_defaults, get_current_language, translate
from state import ensure_session_defaults


def _build_navigation(language: str) -> list[st.Page]:
    t = partial(translate, language=language)
    return [
        st.Page(
            "pages/0_言語とローカライズ.py",
            title=t("navigation.localization"),
            icon=":globe_with_meridians:",
        ),
        st.Page(
            "pages/1_ダッシュボード.py",
            title=t("navigation.dashboard"),
            icon=":chart_with_upwards_trend:",
            default=True,
        ),
        st.Page(
            "pages/2_データ入力.py",
            title=t("navigation.data_entry"),
            icon=":pencil2:",
        ),
        st.Page(
            "pages/7_戦略フレームワーク設定.py",
            title=t("navigation.strategy"),
            icon=":dart:",
        ),
        st.Page(
            "pages/3_シナリオ&感度分析.py",
            title=t("navigation.scenario"),
            icon=":game_die:",
        ),
        st.Page(
            "pages/4_店舗_部門_チャネル分析.py",
            title=t("navigation.segment"),
            icon=":department_store:",
        ),
        st.Page(
            "pages/5_補助金_金融機関資料.py",
            title=t("navigation.funding"),
            icon=":bank:",
        ),
        st.Page(
            "pages/6_エクスポート(PPTX_Excel).py",
            title=t("navigation.export"),
            icon=":outbox_tray:",
        ),
    ]


def main() -> None:
    """Configure Streamlit and dispatch to the selected page."""

    ensure_session_defaults()
    ensure_language_defaults()

    language = get_current_language()
    st.set_page_config(
        page_title=translate("app.page_title", language=language),
        page_icon=translate("app.page_icon", language=language),
        layout="wide",
        initial_sidebar_state="expanded",
    )

    navigation = st.navigation(_build_navigation(language), position="top")
    navigation.run()


if __name__ == "__main__":
    main()
