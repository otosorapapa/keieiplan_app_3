from __future__ import annotations

import streamlit as st

from core import charts, finance


def main() -> None:
    st.title("店舗 / 部門 / チャネル分析")
    st.caption("セグメント別の業績とKPIを可視化します。")

    segment_frame = finance.build_segment_performance()
    st.dataframe(segment_frame, use_container_width=True)

    charts.render_segment_chart(segment_frame)

    st.info("セグメント別の指標を編集するUIを追加してください。")


if __name__ == "__main__":
    main()
