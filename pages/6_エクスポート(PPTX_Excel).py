from __future__ import annotations

import streamlit as st

from core import exporters, io, validators


def main() -> None:
    st.title("エクスポート (PPTX / Excel)")
    st.caption("経営計画の成果物をエクスポートします。")

    state_snapshot = io.snapshot_session_state(st.session_state)
    ready_for_export = validators.is_ready_for_export(state_snapshot)

    st.write("エクスポート可能な状態:", "✅" if ready_for_export else "❌")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Excelをダウンロード",
            data=exporters.export_plan_to_excel(state_snapshot),
            file_name="keieiplan.xlsx",
            disabled=not ready_for_export,
        )
    with col2:
        st.download_button(
            "PPTXをダウンロード",
            data=exporters.export_plan_to_pptx(state_snapshot),
            file_name="keieiplan.pptx",
            disabled=not ready_for_export,
        )

    st.info("ダウンロード処理の実装は core/exporters.py に記述してください。")


if __name__ == "__main__":
    main()
