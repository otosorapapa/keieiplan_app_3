"""Streamlit Cloud entry point for the Keieiplan app."""
from __future__ import annotations

from ui.chrome import apply_app_chrome
from views import render_home_page

apply_app_chrome()

render_home_page()
