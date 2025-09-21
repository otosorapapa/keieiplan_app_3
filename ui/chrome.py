from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime
from inspect import signature
from pathlib import Path
from typing import Callable, Dict

import streamlit as st

from state import (
    create_state_backup,
    delete_state_backup,
    list_state_backups,
    reset_analysis_parameters,
    reset_app_state,
    reset_input_data,
    restore_state_backup,
)

APP_PAGE_TITLE = "経営計画スタジオ"
APP_PAGE_ICON = "📊"
APP_PAGE_CONFIG = {
    "page_title": APP_PAGE_TITLE,
    "page_icon": APP_PAGE_ICON,
    "layout": "wide",
}

LOGO_LIGHT_PATH = Path("assets/logo.png")
LOGO_DARK_PATH = Path("assets/logo_dark.png")
LOGO_ALT_TEXT = "経営計画スタジオのロゴ"
PLACEHOLDER_LOGO_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
)

_LOGO_SUPPORTS_ALT = "alt" in signature(st.logo).parameters

ENVIRONMENT_SETTINGS_KEY = "environment_settings"
ENVIRONMENT_DEFAULTS: Dict[str, float | int | str] = {
    "currency": "JPY (¥)",
    "consumption_tax_rate": 0.1,
    "fiscal_year": 2025,
    "decimal_places": 0,
}

ENVIRONMENT_WIDGET_KEYS = {
    "currency": "environment_currency",
    "consumption_tax_rate": "environment_consumption_tax_percent",
    "fiscal_year": "environment_fiscal_year",
    "decimal_places": "environment_decimal_places",
}

CURRENCY_OPTIONS = [
    "JPY (¥)",
    "USD ($)",
    "EUR (€)",
    "GBP (£)",
]

DECIMAL_PLACE_OPTIONS = [0, 1, 2, 3]

USAGE_GUIDE_TEXT = (
    "1. **入力を整える**: コントロールハブで売上・コストのレバーと会計年度、FTEを設定します。\n"
    "2. **検証と分析**: シナリオ/感応度タブで前提を比較し、AIインサイトでチェックポイントを確認します。\n"
    "3. **可視化と出力**: グラフや表で可視化し、エクスポートタブからExcelをダウンロードして共有します。"
)


def apply_app_chrome() -> None:
    """Configure the Streamlit page and global chrome elements."""

    st.set_page_config(**APP_PAGE_CONFIG)
    _render_logo()
    _render_environment_sidebar()


def _render_logo() -> None:
    """Display the application logo with graceful fallbacks."""

    logo_source: str | Dict[str, str]
    try:
        if not LOGO_LIGHT_PATH.exists():
            raise FileNotFoundError(LOGO_LIGHT_PATH)
        if LOGO_DARK_PATH.exists():
            logo_source = {
                "light": str(LOGO_LIGHT_PATH),
                "dark": str(LOGO_DARK_PATH),
            }
        else:
            logo_source = str(LOGO_LIGHT_PATH)
        _display_logo(logo_source, icon_image=str(LOGO_LIGHT_PATH))
    except FileNotFoundError:
        _display_logo(PLACEHOLDER_LOGO_BYTES)
        st.sidebar.info("assets/logo.png を配置するとブランドロゴが表示されます。")
    except Exception as exc:  # pragma: no cover - defensive UI feedback
        _display_logo(PLACEHOLDER_LOGO_BYTES)
        st.sidebar.warning(f"ロゴを読み込めませんでした: {exc}")


def _display_logo(image: str | Dict[str, str] | bytes, *, icon_image: str | None = None) -> None:
    """Render the logo while gracefully handling optional keyword support."""

    logo_kwargs: Dict[str, str] = {}
    if icon_image is not None:
        logo_kwargs["icon_image"] = icon_image
    if _LOGO_SUPPORTS_ALT:
        logo_kwargs["alt"] = LOGO_ALT_TEXT
    st.logo(image, **logo_kwargs)


def _render_environment_sidebar() -> None:
    """Render shared environment preferences in the sidebar."""

    defaults = _ensure_environment_defaults()

    st.session_state.setdefault(
        ENVIRONMENT_WIDGET_KEYS["currency"], defaults["currency"]
    )
    st.session_state.setdefault(
        ENVIRONMENT_WIDGET_KEYS["consumption_tax_rate"],
        defaults["consumption_tax_rate"] * 100,
    )
    st.session_state.setdefault(
        ENVIRONMENT_WIDGET_KEYS["fiscal_year"], defaults["fiscal_year"]
    )
    st.session_state.setdefault(
        ENVIRONMENT_WIDGET_KEYS["decimal_places"], defaults["decimal_places"]
    )

    with st.sidebar:
        st.markdown("### ⚙️ 環境設定")
        selected_currency = st.selectbox(
            "通貨",
            options=CURRENCY_OPTIONS,
            key=ENVIRONMENT_WIDGET_KEYS["currency"],
        )
        consumption_tax_percent = st.number_input(
            "消費税率 (%)",
            min_value=0.0,
            max_value=25.0,
            step=0.1,
            format="%.1f",
            key=ENVIRONMENT_WIDGET_KEYS["consumption_tax_rate"],
        )
        fiscal_year = st.number_input(
            "会計年度",
            min_value=2000,
            max_value=2100,
            step=1,
            key=ENVIRONMENT_WIDGET_KEYS["fiscal_year"],
        )
        decimal_places = st.selectbox(
            "小数点桁",
            options=DECIMAL_PLACE_OPTIONS,
            key=ENVIRONMENT_WIDGET_KEYS["decimal_places"],
            format_func=lambda value: f"{value}桁",
        )
        st.caption("設定はセッション内で保持され、全ページで共有されます。")

    st.session_state[ENVIRONMENT_SETTINGS_KEY] = {
        "currency": selected_currency,
        "consumption_tax_rate": round(consumption_tax_percent / 100, 4),
        "fiscal_year": int(fiscal_year),
        "decimal_places": int(decimal_places),
    }


def _ensure_environment_defaults() -> Dict[str, float | int | str]:
    """Ensure default environment settings exist in the session."""

    stored = st.session_state.get(ENVIRONMENT_SETTINGS_KEY)
    defaults = ENVIRONMENT_DEFAULTS.copy()
    if isinstance(stored, dict):
        for key, value in stored.items():
            if key in defaults:
                defaults[key] = value
    st.session_state[ENVIRONMENT_SETTINGS_KEY] = defaults
    return defaults


@dataclass(frozen=True)
class HeaderActions:
    """User interactions emitted from the global header."""

    toggled_help: bool = False
    reset_requested: bool = False


def render_app_header(
    *,
    title: str,
    subtitle: str,
    help_key: str = "show_usage_guide",
    help_button_label: str = "使い方ガイド",
    reset_label: str = "既定値で再初期化",
    show_reset: bool = True,
    on_reset: Callable[[], None] | None = None,
) -> HeaderActions:
    """Render the global header with help and reset controls."""

    toggled_help = False
    reset_requested = False

    with st.container():
        columns = st.columns([4, 1, 1] if show_reset else [4, 1], gap="large")
        with columns[0]:
            st.title(title)
            st.caption(subtitle)
        help_col = columns[1]
        with help_col:
            if st.button(
                help_button_label,
                use_container_width=True,
                key=f"{help_key}_toggle_button",
            ):
                toggled_help = True
        if show_reset:
            reset_col = columns[2]
            with reset_col:
                _render_data_management_menu(on_reset=on_reset, label=reset_label)

    return HeaderActions(toggled_help=toggled_help, reset_requested=reset_requested)


def _render_data_management_menu(
    *, on_reset: Callable[[], None] | None, label: str
) -> None:
    """Render the backup and reset controls within a popover/expander."""

    trigger = (
        st.popover(label, use_container_width=True)
        if hasattr(st, "popover")
        else st.expander(label, expanded=False)
    )
    with trigger:
        _render_backup_controls()
        st.divider()
        _render_reset_controls(on_reset=on_reset)


def _render_backup_controls() -> None:
    st.markdown("#### 💾 バックアップ")
    if "header_backup_label" not in st.session_state:
        st.session_state["header_backup_label"] = datetime.now().strftime(
            "backup_%Y%m%d_%H%M%S"
        )
    label = st.text_input("バックアップ名", key="header_backup_label")
    if st.button("バックアップを保存", key="header_create_backup", use_container_width=True):
        entry = create_state_backup(label)
        st.session_state["header_backup_label"] = datetime.now().strftime(
            "backup_%Y%m%d_%H%M%S"
        )
        st.toast(f"バックアップ『{entry['label']}』を保存しました。", icon="💾")

    backups = list_state_backups()
    if backups:
        options = {
            f"{entry['label']} — {entry['created_at']}": entry["id"] for entry in backups
        }
        selected_label = st.selectbox(
            "バックアップを選択",
            list(options.keys()),
            key="header_selected_backup",
        )
        selected_id = options[selected_label]
        action_cols = st.columns(2)
        if action_cols[0].button("復元", key="header_restore_backup", use_container_width=True):
            if restore_state_backup(selected_id):
                st.toast("バックアップから復元しました。", icon="↩️")
                st.experimental_rerun()
        if action_cols[1].button("削除", key="header_delete_backup", use_container_width=True):
            if delete_state_backup(selected_id):
                st.toast("バックアップを削除しました。", icon="🗑️")
                st.experimental_rerun()
    else:
        st.caption("まだバックアップはありません。保存してから復元できます。")


def _render_reset_controls(*, on_reset: Callable[[], None] | None) -> None:
    st.markdown("#### ♻️ リセット")
    options = {
        "入力データのみ初期化": "inputs",
        "分析パラメータのみ初期化": "analysis",
        "全体を既定値で再初期化": "all",
    }
    if "header_reset_scope" not in st.session_state:
        st.session_state["header_reset_scope"] = "inputs"
    scope_label = st.radio(
        "初期化する範囲",
        list(options.keys()),
        key="header_reset_scope",
    )
    if st.button("初期化を実行", key="header_apply_reset", use_container_width=True):
        scope = options.get(scope_label, "inputs")
        if scope == "inputs":
            reset_input_data()
            st.toast("入力データを初期化しました。", icon="🧹")
        elif scope == "analysis":
            reset_analysis_parameters()
            st.toast("分析パラメータを初期化しました。", icon="🧠")
        else:
            reset_app_state(preserve={"state_backups"})
            if on_reset is not None:
                on_reset()
            st.toast("アプリ全体を既定値に戻しました。", icon="🔄")
        st.experimental_rerun()


def render_usage_guide_panel(help_key: str = "show_usage_guide") -> None:
    """Display the collapsible usage guide when the toggle is active."""

    placeholder = st.container()
    if st.session_state.get(help_key):
        with placeholder.expander("3ステップ活用ガイド", expanded=True):
            st.markdown(USAGE_GUIDE_TEXT)


def render_app_footer(
    caption: str = "© 経営計画策定WEBアプリ（Streamlit版） | 表示単位と計算単位を分離し、丸めの影響を最小化しています。",
) -> None:
    """Render the global footer."""

    st.divider()
    st.caption(caption)


__all__ = [
    "apply_app_chrome",
    "HeaderActions",
    "render_app_footer",
    "render_app_header",
    "render_usage_guide_panel",
]
