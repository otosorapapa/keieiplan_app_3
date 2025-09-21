from __future__ import annotations

import streamlit as st

from core import charts, finance


def main() -> None:
    st.title("ダッシュボード")
    st.caption("経営指標の俯瞰ビューを提供します。")

    metrics = finance.calculate_key_metrics()
    charts.display_metric_overview(metrics)

    st.markdown("### TODO")
    st.info("主要なチャートやKPIカードを追加してください。")


if __name__ == "__main__":
    main()
