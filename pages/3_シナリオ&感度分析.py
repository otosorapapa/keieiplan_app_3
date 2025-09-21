from __future__ import annotations

import streamlit as st

from core import charts, finance
from localization import render_language_status_alert, translate


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.scenario.title"))
    st.caption(translate("pages.scenario.caption"))

    scenarios = finance.generate_scenarios()
    scenario_frame = finance.scenarios_as_dataframe(scenarios)
    st.subheader(translate("pages.scenario.scenario_table"))
    st.dataframe(scenario_frame, use_container_width=True)

    sensitivity_matrix = finance.generate_sensitivity_matrix()
    charts.render_sensitivity_table(sensitivity_matrix)

    st.info(translate("pages.scenario.todo"))


if __name__ == "__main__":
    main()
