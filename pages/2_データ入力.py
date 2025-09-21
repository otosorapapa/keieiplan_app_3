from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import pandas as pd
import streamlit as st

from core import io
from core.templates import list_industry_templates
from formatting import format_amount_with_unit
from localization import render_language_status_alert, translate, translate_list
from models import CostPlan
from state import (
    delete_state_backup,
    list_state_backups,
    load_finance_bundle,
    restore_state_backup,
)

IMPORT_STATE_KEY = "data_entry_pending_import"
IMPORT_WARNINGS_KEY = "data_entry_pending_import_warnings"
IMPORT_FILENAME_KEY = "data_entry_pending_import_filename"
IMPORT_MESSAGE_KEY = "data_entry_last_import_message"


def _render_usage_guide() -> None:
    """Display contextual help for the data entry workflow."""

    button_label = translate("guides.button_label")
    container = st.popover if hasattr(st, "popover") else st.expander
    with container(button_label, key="data_entry_usage_guide"):
        for line in translate_list("pages.data_entry.guide"):
            st.markdown(f"- {line}")
        video_url = translate("pages.data_entry.guide_video")
        if video_url:
            st.markdown(f"**{translate('common.video_label')}**")
            st.video(video_url)
        faq_entries = translate_list("pages.data_entry.guide_faq")
        if faq_entries:
            st.markdown(f"**{translate('common.faq_label')}**")
            for entry in faq_entries:
                st.markdown(entry)


def _render_industry_template_section() -> None:
    st.subheader("🏭 業種別テンプレート")
    templates = list_industry_templates()
    if not templates:
        st.info("テンプレートがまだ登録されていません。管理者にお問い合わせください。")
        return

    template_map = {template.id: template for template in templates}
    template_ids = [template.id for template in templates]
    stored_state: Dict[str, Any] = st.session_state.get("industry_template_state", {})
    default_id = stored_state.get("active_id") if stored_state else None
    default_index = template_ids.index(default_id) if default_id in template_ids else 0

    selected_id = st.selectbox(
        "業種テンプレートを選択",
        template_ids,
        index=default_index,
        format_func=lambda template_id: template_map[template_id].name,
        key="industry_template_selector",
    )
    template = template_map[selected_id]
    st.caption(template.description)

    meta_cols = st.columns(2)
    meta_cols[0].metric("最終更新", template.last_updated.strftime("%Y-%m"))
    meta_cols[1].metric("情報ソース", template.source)
    st.info(template.notes)

    stored_for_template = stored_state if stored_state.get("active_id") == selected_id else {}
    gross_default = float(stored_for_template.get("gross_margin", template.gross_margin_ratio))
    fixed_default = float(stored_for_template.get("fixed_cost_ratio", template.fixed_cost_ratio))
    gross_percent_default = max(0, min(90, int(round(gross_default * 100))))
    fixed_percent_default = max(0, min(80, int(round(fixed_default * 100))))

    slider_cols = st.columns(2)
    gross_percent = slider_cols[0].slider(
        "売上総利益率", min_value=0, max_value=90, value=gross_percent_default, format="%d%%"
    )
    fixed_percent = slider_cols[1].slider(
        "固定費率", min_value=0, max_value=80, value=fixed_percent_default, format="%d%%"
    )

    gross_ratio = Decimal(gross_percent) / Decimal(100)
    fixed_ratio = Decimal(fixed_percent) / Decimal(100)

    bundle, _ = load_finance_bundle()
    annual_sales = bundle.sales.annual_total()
    settings_state: Dict[str, Any] = st.session_state.get("finance_settings", {})
    unit = settings_state.get("unit", "百万円")
    currency = settings_state.get("currency", "JPY")

    current_costs = st.session_state.get("finance_models", {}).get("costs")
    if isinstance(current_costs, CostPlan):
        base_plan = current_costs
    else:
        try:
            base_plan = CostPlan.from_dict(current_costs or {})  # type: ignore[arg-type]
        except Exception:
            base_plan = CostPlan()

    recommended_plan = template.build_cost_plan(
        annual_sales=annual_sales,
        gross_margin=gross_ratio,
        fixed_cost_ratio=fixed_ratio,
        base_plan=base_plan,
    )

    summary_cols = st.columns(3)
    summary_cols[0].metric(
        "年間売上", format_amount_with_unit(annual_sales, unit, currency=currency)
    )
    summary_cols[1].metric("設定粗利率", f"{gross_percent}%")
    summary_cols[2].metric("固定費率", f"{fixed_percent}%")

    variable_rows = [
        {
            "費目コード": code,
            "売上比率": f"{float(ratio) * 100:.1f}%",
        }
        for code, ratio in recommended_plan.variable_ratios.items()
    ]
    fixed_rows = [
        {
            "費目コード": code,
            "年間固定費": format_amount_with_unit(amount, unit, currency=currency),
        }
        for code, amount in recommended_plan.fixed_costs.items()
    ]

    st.markdown("**推奨される変動費率**")
    variable_df = pd.DataFrame(variable_rows)
    if variable_df.empty:
        variable_df = pd.DataFrame(columns=["費目コード", "売上比率"])
    st.dataframe(variable_df, use_container_width=True)

    st.markdown("**推奨される固定費水準**")
    if annual_sales == 0:
        st.warning("年間売上が0円のため固定費金額は0円として試算されています。先に売上データを入力してください。")
    fixed_df = pd.DataFrame(fixed_rows)
    if fixed_df.empty:
        fixed_df = pd.DataFrame(columns=["費目コード", "年間固定費"])
    st.dataframe(fixed_df, use_container_width=True)

    if st.button("テンプレートを適用", key="industry_template_apply", type="primary"):
        models_state = dict(st.session_state.get("finance_models", {}))
        models_state["costs"] = recommended_plan
        st.session_state["finance_models"] = models_state
        st.session_state["industry_template_state"] = {
            "active_id": template.id,
            "template_name": template.name,
            "gross_margin": float(gross_ratio),
            "fixed_cost_ratio": float(fixed_ratio),
            "last_applied": datetime.now().isoformat(timespec="seconds"),
            "source": template.source,
            "notes": template.notes,
        }
        st.toast(f"{template.name}のテンプレートを適用しました。", icon="🏭")
        st.experimental_rerun()


def _render_backup_overview() -> None:
    st.subheader("🔐 バックアップ一覧")
    backups = list_state_backups()
    if not backups:
        st.info("まだバックアップがありません。ヘッダー右上の「既定値で再初期化」から作成できます。")
        return

    entries = {f"{entry['label']} — {entry['created_at']}": entry for entry in backups}
    selected_label = st.selectbox(
        "詳細を表示するバックアップ",
        list(entries.keys()),
        key="data_entry_backup_select",
    )
    entry = entries[selected_label]
    snapshot = entry.get("snapshot", {})
    st.caption(f"含まれるキー数: {len(snapshot)}")
    with st.expander("バックアップに含まれるセッションキー", expanded=False):
        st.write(sorted(snapshot.keys()))

    action_cols = st.columns(2)
    if action_cols[0].button("このバックアップを復元", key="data_entry_backup_restore"):
        if restore_state_backup(entry["id"]):
            st.toast("バックアップを適用しました。", icon="↩️")
            st.experimental_rerun()
    if action_cols[1].button("バックアップを削除", key="data_entry_backup_delete"):
        if delete_state_backup(entry["id"]):
            st.toast("バックアップを削除しました。", icon="🗑️")
            st.experimental_rerun()


def _render_export_import_panel() -> None:
    st.subheader("📤 エクスポート / 📥 インポート")

    last_message = st.session_state.pop(IMPORT_MESSAGE_KEY, None)
    if isinstance(last_message, dict):
        filename = last_message.get("filename", "imported_data")
        st.success(f"{filename} をインポートして適用しました。")
        for warning in last_message.get("warnings", []):
            st.warning(warning)

    bundle, _ = load_finance_bundle()
    settings_state: Dict[str, Any] = st.session_state.get("finance_settings", {})
    metadata = st.session_state.get("industry_template_state", {})
    payload = io.prepare_finance_export_payload(
        sales=bundle.sales,
        costs=bundle.costs,
        capex=bundle.capex,
        loans=bundle.loans,
        tax=bundle.tax,
        working_capital=bundle.working_capital,
        settings=settings_state,
        metadata=metadata,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_bytes = io.export_payload_to_excel(payload)
    zip_bytes = io.export_payload_to_csv_zip(payload)

    download_cols = st.columns(2)
    download_cols[0].download_button(
        "Excelでダウンロード (.xlsx)",
        data=excel_bytes,
        file_name=f"keieiplan_export_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="data_entry_export_excel",
    )
    download_cols[1].download_button(
        "CSV一括ダウンロード (.zip)",
        data=zip_bytes,
        file_name=f"keieiplan_export_{timestamp}.zip",
        mime="application/zip",
        use_container_width=True,
        key="data_entry_export_csv",
    )
    st.caption("CSVは複数シートをZIP形式でまとめています。ダウンロード後に編集して再インポートできます。")

    uploaded_file = st.file_uploader(
        "エクスポートしたファイルをインポート",
        type=("xlsx", "zip"),
        key="data_entry_import_uploader",
    )
    if uploaded_file is not None:
        payload, warnings = io.import_finance_payload(uploaded_file)
        if payload:
            st.session_state[IMPORT_STATE_KEY] = payload
            st.session_state[IMPORT_WARNINGS_KEY] = warnings
            st.session_state[IMPORT_FILENAME_KEY] = getattr(uploaded_file, "name", "imported_data")
            st.toast("インポートデータを読み込みました。下のボタンで適用できます。", icon="📥")
        else:
            st.warning("ファイルに適用可能なデータが含まれていません。")

    pending_payload = st.session_state.get(IMPORT_STATE_KEY)
    if pending_payload:
        filename = st.session_state.get(IMPORT_FILENAME_KEY, "imported_data")
        st.markdown(f"**インポートプレビュー: {filename}**")
        warnings = st.session_state.get(IMPORT_WARNINGS_KEY, [])
        if warnings:
            for warning in warnings:
                st.warning(warning)

        models = pending_payload.get("models", {})
        preview_cols = st.columns(3)
        sales_plan = models.get("sales")
        if hasattr(sales_plan, "items"):
            preview_cols[0].metric("売上アイテム数", len(getattr(sales_plan, "items", [])))
        costs_plan = models.get("costs")
        if isinstance(costs_plan, CostPlan):
            preview_cols[1].metric("固定費項目数", len(costs_plan.fixed_costs))
        loans_plan = models.get("loans")
        preview_cols[2].metric("借入件数", len(getattr(loans_plan, "loans", [])))

        action_cols = st.columns([1, 1])
        if action_cols[0].button("インポートを適用", key="data_entry_import_apply", type="primary"):
            models_state = dict(st.session_state.get("finance_models", {}))
            models_state.update(models)
            st.session_state["finance_models"] = models_state
            if pending_payload.get("settings"):
                settings_state = dict(st.session_state.get("finance_settings", {}))
                settings_state.update(pending_payload["settings"])
                st.session_state["finance_settings"] = settings_state
            if pending_payload.get("metadata"):
                st.session_state["industry_template_state"] = pending_payload["metadata"]
            st.session_state[IMPORT_MESSAGE_KEY] = {
                "filename": filename,
                "warnings": warnings,
            }
            for key in (IMPORT_STATE_KEY, IMPORT_WARNINGS_KEY, IMPORT_FILENAME_KEY):
                st.session_state.pop(key, None)
            st.toast("インポートデータを適用しました。", icon="📥")
            st.experimental_rerun()
        if action_cols[1].button("キャンセル", key="data_entry_import_cancel"):
            for key in (IMPORT_STATE_KEY, IMPORT_WARNINGS_KEY, IMPORT_FILENAME_KEY):
                st.session_state.pop(key, None)
            st.toast("インポートをキャンセルしました。", icon="🛑")

    st.caption("API連携（会計ソフト・POSシステムとの接続）は次期バージョンで提供予定です。")


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.data_entry.title"))
    st.caption(translate("pages.data_entry.caption"))
    _render_usage_guide()

    management_tab, manual_tab = st.tabs(["データ管理", "手動入力"])

    with management_tab:
        _render_industry_template_section()
        st.divider()
        _render_backup_overview()
        st.divider()
        _render_export_import_panel()

    with manual_tab:
        with st.expander(translate("pages.data_entry.manual_form_label"), expanded=False):
            st.write(translate("pages.data_entry.manual_form_placeholder"))


if __name__ == "__main__":
    main()
