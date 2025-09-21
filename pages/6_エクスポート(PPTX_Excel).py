from __future__ import annotations

import streamlit as st

from core import exporters, io, validators
from localization import render_language_status_alert, translate


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.export.title"))
    st.caption(translate("pages.export.caption"))

    state_snapshot = io.snapshot_session_state(st.session_state)
    ready_for_export = validators.is_ready_for_export(state_snapshot)

    st.write(
        translate("pages.export.ready_state"),
        "✅" if ready_for_export else "❌",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            translate("pages.export.download_excel"),
            data=exporters.export_plan_to_excel(state_snapshot),
            file_name="keieiplan.xlsx",
            disabled=not ready_for_export,
        )
    with col2:
        st.download_button(
            translate("pages.export.download_pptx"),
            data=exporters.export_plan_to_pptx(state_snapshot),
            file_name="keieiplan.pptx",
            disabled=not ready_for_export,
        )

    st.info(translate("pages.export.todo"))


if __name__ == "__main__":
    main()
