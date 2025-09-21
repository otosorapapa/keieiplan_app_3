from __future__ import annotations

import streamlit as st

from core import finance, validators
from localization import render_language_status_alert, translate


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.funding.title"))
    st.caption(translate("pages.funding.caption"))

    funding_summary = finance.estimate_funding_requirements()
    st.subheader(translate("pages.funding.summary_header"))
    st.json(funding_summary)

    st.markdown(f"### {translate('pages.funding.template_header')}")
    st.write(translate("pages.funding.template_placeholder"))

    validation_messages = validators.collect_validation_summary(
        validators.validate_input_payload({})
    )
    if validation_messages:
        st.warning(translate("pages.funding.checklist_title"))
        st.text(validation_messages)


if __name__ == "__main__":
    main()
