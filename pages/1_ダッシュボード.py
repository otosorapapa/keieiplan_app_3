from __future__ import annotations

import streamlit as st

from core import charts, finance
from localization import render_language_status_alert, translate


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.dashboard.title"))
    st.caption(translate("pages.dashboard.caption"))

    metrics = finance.calculate_key_metrics()
    charts.display_metric_overview(metrics)

    st.markdown(f"### {translate('pages.dashboard.todo_header')}")
    st.info(translate("pages.dashboard.todo_description"))


if __name__ == "__main__":
    main()
