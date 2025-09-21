from __future__ import annotations

import streamlit as st

from core import io, validators
from localization import render_language_status_alert, translate, translate_list


def _render_usage_guide() -> None:
    """Display contextual help for the data entry workflow."""

    button_label = translate("guides.button_label")
    container = st.popover if hasattr(st, "popover") else st.expander
    with container(button_label, key="data_entry_usage_guide"):
        for line in translate_list("pages.data_entry.guide"):
            st.markdown(f"- {line}")
        video_url = translate("pages.data_entry.guide_video")
        if video_url:
            st.markdown(f"**{translate('common.video_label')}**")
            st.video(video_url)
        faq_entries = translate_list("pages.data_entry.guide_faq")
        if faq_entries:
            st.markdown(f"**{translate('common.faq_label')}**")
            for entry in faq_entries:
                st.markdown(entry)


def main() -> None:
    render_language_status_alert()
    st.title(translate("pages.data_entry.title"))
    st.caption(translate("pages.data_entry.caption"))
    _render_usage_guide()

    uploaded_file = st.file_uploader(
        translate("pages.data_entry.file_uploader_label"),
        type=("xlsx", "csv"),
    )
    dataset = None
    if uploaded_file:
        dataset = io.load_uploaded_dataset(uploaded_file)
        st.success(translate("pages.data_entry.file_loaded"))
        st.json(dataset)

    with st.expander(translate("pages.data_entry.manual_form_label"), expanded=False):
        st.write(translate("pages.data_entry.manual_form_placeholder"))

    validation_messages = validators.validate_input_payload(dataset or {})
    if validation_messages:
        st.warning(translate("pages.data_entry.validation_warning"))
        for message in validation_messages:
            st.write(f"- {message}")
    else:
        st.info(translate("pages.data_entry.validation_success"))


if __name__ == "__main__":
    main()
