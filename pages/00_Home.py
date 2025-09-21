"""Overview / tutorial page accessible from the sidebar."""
from __future__ import annotations

import streamlit as st

from ui.chrome import apply_app_chrome
from views import render_home_page

apply_app_chrome()

render_home_page()
