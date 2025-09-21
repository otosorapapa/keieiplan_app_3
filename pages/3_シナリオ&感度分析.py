from __future__ import annotations

import streamlit as st

from core import charts, finance


def main() -> None:
    st.title("シナリオ & 感度分析")
    st.caption("複数シナリオと感度分析の結果を比較します。")

    scenarios = finance.generate_scenarios()
    scenario_frame = finance.scenarios_as_dataframe(scenarios)
    st.subheader("シナリオ一覧")
    st.dataframe(scenario_frame, use_container_width=True)

    sensitivity_matrix = finance.generate_sensitivity_matrix()
    charts.render_sensitivity_table(sensitivity_matrix)

    st.info("売上・費用の仮定を変更するためのUIコンポーネントを追加してください。")


if __name__ == "__main__":
    main()
