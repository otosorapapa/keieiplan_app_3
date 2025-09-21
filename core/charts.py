"""Visualization helpers for Streamlit pages."""

from __future__ import annotations

from typing import Mapping

import pandas as pd
import streamlit as st


def display_metric_overview(metrics: Mapping[str, float] | None) -> None:
    """Render KPI metrics as Streamlit metric cards."""

    st.subheader("主要指標")
    if not metrics:
        st.info("財務データを取り込むとKPIがここに表示されます。")
        return

    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics.items(), strict=False):
        column.metric(label, f"{value:,.0f}")


def render_sensitivity_table(matrix: pd.DataFrame) -> None:
    """Render sensitivity analysis results."""

    st.subheader("感度分析")
    st.dataframe(matrix, use_container_width=True)


def render_segment_chart(frame: pd.DataFrame) -> None:
    """Display store / channel level KPIs as a bar chart."""

    st.subheader("セグメント別パフォーマンス")
    if frame.empty:
        st.info("セグメントデータを入力すると、棒グラフが表示されます。")
        return

    display_frame = frame.set_index("セグメント")[["売上高", "営業利益"]]
    st.bar_chart(display_frame)
