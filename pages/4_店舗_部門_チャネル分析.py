from __future__ import annotations

import streamlit as st

from core import charts, finance
from localization import render_language_status_alert, translate


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.segment.title"))
    st.caption(translate("pages.segment.caption"))

    segment_frame = finance.build_segment_performance()
    st.dataframe(segment_frame, use_container_width=True)

    charts.render_segment_chart(segment_frame)

    st.info(translate("pages.segment.todo"))


if __name__ == "__main__":
    main()
