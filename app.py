"""Local dashboard: current (2025+) analyst ratings from the top 10 Extel banks.

Run:  streamlit run app.py
"""
import streamlit as st

from ratings import pages, ui

st.set_page_config(page_title="Bank Analyst Ratings", page_icon="📈", layout="wide")
ui.inject_css()

nav = st.navigation([
    st.Page(pages.overview_page, title="Overview", icon=":material/dashboard:", url_path="overview"),
    st.Page(pages.bank_page, title="Bank ratings", icon=":material/account_balance:", url_path="banks",
            default=True),
    st.Page(pages.portfolio_page, title="Portfolio screener", icon=":material/work:", url_path="portfolio"),
])
pages.sidebar()
nav.run()
