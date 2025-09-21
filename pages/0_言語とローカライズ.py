from __future__ import annotations

from decimal import Decimal
from typing import Dict

import streamlit as st

from localization import (
    apply_tax_profile,
    get_current_language,
    get_language_label,
    get_language_status,
    get_tax_profile_details,
    get_tax_profile_label,
    list_language_codes,
    list_tax_profile_codes,
    render_language_status_alert,
    translate,
    translate_list,
    translation,
    update_language,
)
from localization.languages import get_language_definition


def _render_usage_guide(section_key: str, base_key: str) -> None:
    """Render a contextual usage guide using popovers or expanders."""

    button_label = translate("guides.button_label")
    container = st.popover if hasattr(st, "popover") else st.expander
    with container(button_label, key=f"usage_guide_{section_key}"):
        for line in translate_list(f"{base_key}.overview"):
            st.markdown(f"- {line}")
        video_url = translate(f"{base_key}.video_url")
        if video_url:
            st.markdown(f"**{translate('common.video_label')}**")
            st.video(video_url)
        faq_entries = translate_list(f"{base_key}.faq")
        if faq_entries:
            st.markdown(f"**{translate('common.faq_label')}**")
            for entry in faq_entries:
                st.markdown(entry)


def _format_percent(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.1'))}%"


def main() -> None:
    st.title(translate("pages.localization.title"))
    st.caption(translate("pages.localization.caption"))
    render_language_status_alert()

    finance_settings: Dict[str, object] = dict(st.session_state.get("finance_settings", {}))
    current_language = get_current_language()
    current_tax_profile = str(finance_settings.get("tax_profile", ""))

    language_codes = list_language_codes()
    profile_codes = list_tax_profile_codes()

    with st.form("localization_settings_form"):
        st.subheader(translate("pages.localization.language_section_title"))
        st.caption(translate("pages.localization.language_section_caption"))
        _render_usage_guide("language", "guides.language")

        language_index = (
            language_codes.index(current_language)
            if current_language in language_codes
            else 0
        )
        selected_language = st.selectbox(
            translate("common.language"),
            options=language_codes,
            index=language_index,
            format_func=lambda code: get_language_label(code),
        )

        language_definition = get_language_definition(selected_language)
        recommended_profile = language_definition.default_tax_profile

        st.subheader(translate("pages.localization.tax_section_title"))
        st.caption(translate("pages.localization.tax_section_caption"))
        _render_usage_guide("tax", "guides.tax")

        default_profile_code = current_tax_profile or recommended_profile
        profile_index = (
            profile_codes.index(default_profile_code)
            if default_profile_code in profile_codes
            else profile_codes.index(recommended_profile)
        )
        selected_profile = st.selectbox(
            translate("common.tax_profile"),
            options=profile_codes,
            index=profile_index,
            format_func=lambda code: get_tax_profile_label(code),
        )
        st.caption(
            translate(
                "pages.localization.recommended_tax_profile",
                profile=get_tax_profile_label(recommended_profile),
            )
        )

        submitted = st.form_submit_button(translate("pages.localization.submit_label"))

    if submitted:
        update_language(selected_language, tax_profile=selected_profile)
        apply_tax_profile(selected_profile)
        st.success(translate("pages.localization.success_message"))

    st.subheader(translate("pages.localization.tax_profile_details"))
    st.caption(translate("pages.localization.sync_hint"))

    active_profile = selected_profile
    profile_details = get_tax_profile_details(active_profile)
    detail_headers = translation("pages.localization.tax_detail_headers") or {}

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        detail_headers.get("corporate_tax", "Corporate tax"),
        _format_percent(profile_details["corporate_tax_rate"]),
    )
    metric_columns[1].metric(
        detail_headers.get("consumption_tax", "Indirect tax"),
        _format_percent(profile_details["consumption_tax_rate"]),
    )
    metric_columns[2].metric(
        detail_headers.get("social_insurance", "Social insurance"),
        _format_percent(profile_details["social_insurance_rate"]),
    )
    metric_columns[3].metric(
        detail_headers.get("depreciation", "Depreciation"),
        profile_details["depreciation"],
    )

    for bullet in profile_details.get("description", []):
        st.markdown(f"- {bullet}")

    st.subheader(translate("pages.localization.status_overview_title"))
    st.caption(translate("pages.localization.status_overview_caption"))
    st.markdown(f"**{translate('pages.localization.beta_panel_title')}**")

    language_status = get_language_status()
    if language_status.status != "stable":
        st.info(
            f"**{get_language_label(language_status.code)}** — "
            f"{translate(f'languages.status_labels.{language_status.status}')}"
        )

    for code in language_codes:
        definition = get_language_definition(code)
        status_label = translate(f"languages.status_labels.{definition.status}")
        st.markdown(f"**{get_language_label(code)}** — {status_label}")
        for detail in translate_list(f"languages.{code}.description"):
            st.markdown(f"- {detail}")

    st.markdown(translate("pages.localization.feedback_prompt"))


if __name__ == "__main__":
    main()
