from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from core import strategy
from localization import render_language_status_alert, translate
from state import load_finance_bundle


def _current_display_settings() -> tuple[str, str]:
    settings: Dict[str, object] = dict(st.session_state.get("finance_settings", {}))
    unit = str(settings.get("unit", "百万円"))
    currency = str(settings.get("currency", "JPY"))
    return unit, currency


def _render_bsc_tab() -> None:
    st.markdown(
        "財務・顧客・内部プロセス・学習成長の4視点で、目標・指標・ターゲットを整理します。"
        "ここで保存した内容はダッシュボードとレポート出力に反映されます。"
    )

    current_state = strategy.normalize_bsc_state(st.session_state.get("strategy_bsc", {}))
    updated_state: Dict[str, list[dict[str, str]]] = {}
    with st.form("strategy_bsc_form"):
        for key, label in strategy.BSC_PERSPECTIVES:
            st.markdown(f"#### {label}視点")
            rows = [
                {
                    "目標": entry.get("objective", ""),
                    "指標": entry.get("metric", ""),
                    "ターゲット": entry.get("target", ""),
                }
                for entry in current_state.get(key, [])
            ]
            if not rows:
                rows = [{"目標": "", "指標": "", "ターゲット": ""}]
            edited = st.data_editor(
                pd.DataFrame(rows),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key=f"strategy_bsc_editor_{key}",
            )
            if isinstance(edited, pd.DataFrame):
                records = edited.to_dict(orient="records")
            else:
                records = list(edited)
            cleaned: list[dict[str, str]] = []
            for row in records:
                objective = str(row.get("目標", "")).strip()
                metric = str(row.get("指標", "")).strip()
                target = str(row.get("ターゲット", "")).strip()
                if not any([objective, metric, target]):
                    continue
                cleaned.append({
                    "objective": objective,
                    "metric": metric,
                    "target": target,
                })
            updated_state[key] = cleaned
        submitted = st.form_submit_button("BSC設定を保存")

    if submitted:
        st.session_state["strategy_bsc"] = updated_state
        st.success("BSC設定を保存しました。")

    preview = strategy.build_bsc_display_frame(st.session_state.get("strategy_bsc", {}))
    if not preview.empty:
        st.markdown("#### 登録済みBSCサマリー")
        st.dataframe(preview, use_container_width=True, hide_index=True)
    else:
        st.info("各視点の行を追加するとダッシュボードにカードが表示されます。")


def _render_pest_tab() -> None:
    st.markdown(
        "政治・経済・社会・技術の外部環境を整理し、リスクと機会の仮説を明確化します。"
        "入力した内容はSWOT分析やレポートのリスク評価で参照されます。"
    )
    current_state = strategy.normalize_pest_state(st.session_state.get("strategy_pest", {}))
    inputs: Dict[str, str] = {}
    with st.form("strategy_pest_form"):
        for key, label, hint in strategy.PEST_DIMENSIONS:
            default_text = "\n".join(current_state.get(key, []))
            inputs[key] = st.text_area(
                f"{label}要因 ({hint})",
                value=default_text,
                height=120,
                placeholder="箇条書きで入力してください",
                key=f"strategy_pest_input_{key}",
            )
        submitted = st.form_submit_button("外部環境分析を保存")

    if submitted:
        updated = {
            key: [line.strip() for line in inputs.get(key, "").splitlines() if line.strip()]
            for key in current_state.keys()
        }
        st.session_state["strategy_pest"] = updated
        st.success("PEST分析を保存しました。")

    display_map = strategy.build_pest_display(st.session_state.get("strategy_pest", {}))
    st.markdown("#### 登録済み外部環境要因")
    for label, entries in display_map.items():
        st.markdown(f"**{label}**")
        if entries:
            for entry in entries:
                st.markdown(f"- {entry}")
        else:
            st.caption("未入力です。")


def _render_swot_tab(unit: str, currency: str) -> None:
    st.markdown(
        "内部資源と外部要因を組み合わせ、強み・弱み・機会・脅威を整理します。"
        "入力値に応じてAIが財務データやPESTの内容をもとに提案を表示します。"
    )

    current_state = strategy.normalize_swot_state(st.session_state.get("strategy_swot", {}))
    inputs: Dict[str, str] = {}
    with st.form("strategy_swot_form"):
        for key, label in strategy.SWOT_CATEGORIES:
            default_text = "\n".join(current_state.get(key, []))
            inputs[key] = st.text_area(
                f"{label}",
                value=default_text,
                height=140,
                placeholder=f"{label}に該当する要素を箇条書きで入力",
                key=f"strategy_swot_input_{key}",
            )
        submitted = st.form_submit_button("SWOT分析を保存")

    if submitted:
        updated = {
            key: [line.strip() for line in inputs.get(key, "").splitlines() if line.strip()]
            for key in current_state.keys()
        }
        st.session_state["strategy_swot"] = updated
        st.success("SWOT分析を保存しました。")

    swot_display = strategy.build_swot_display(st.session_state.get("strategy_swot", {}))
    cols = st.columns(2)
    for index, (label, entries) in enumerate(swot_display.items()):
        column = cols[index % 2]
        with column:
            st.markdown(f"#### {label}")
            if entries:
                for entry in entries:
                    st.markdown(f"- {entry}")
            else:
                st.caption("未入力です。")

    bundle, _ = load_finance_bundle()
    finance_summary = strategy.summarize_financial_context(bundle)
    suggestions = strategy.generate_swot_suggestions(
        st.session_state.get("strategy_swot", {}),
        st.session_state.get("strategy_pest", {}),
        finance_summary,
        unit=unit,
        currency=currency,
        bsc_state=st.session_state.get("strategy_bsc", {}),
    )

    st.markdown("#### AIサポートコメント")
    if suggestions:
        for suggestion in suggestions:
            st.markdown(f"- {suggestion}")
    else:
        st.info("PESTや財務データを入力するとサポートコメントが表示されます。")


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.strategy.title"))
    st.caption(translate("pages.strategy.caption"))

    unit, currency = _current_display_settings()

    bsc_tab, pest_tab, swot_tab = st.tabs(["BSC設定", "外部環境分析", "SWOT分析"])

    with bsc_tab:
        _render_bsc_tab()
    with pest_tab:
        _render_pest_tab()
    with swot_tab:
        _render_swot_tab(unit, currency)


if __name__ == "__main__":
    main()
