"""Main Streamlit Application Entrypoint with st.Page and st.navigation."""

import os
from pathlib import Path
import re
import sys
import uuid

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.ui.views.landing_page import render_landing_page
from app.ui.views.mcp_console import render_mcp_console_view
from app.ui.views.mcp_guides import render_claude_cursor_guide, render_mcp_inspector_guide
from app.ui.views.product_insights import render_product_insights_view
from app.ui.views.sandbox_dashboard import render_sandbox_dashboard_page


def sync_session_id():
    """Reads and writes ?session=<id> into URL query parameters for multi-user session isolation."""
    query_session = st.query_params.get("session")
    if query_session:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", str(query_session)).strip().lower()[:16]
        session_id = cleaned or uuid.uuid4().hex[:6]
    else:
        session_id = st.session_state.get("aidr_session_id") or uuid.uuid4().hex[:6]

    st.session_state["aidr_session_id"] = session_id
    if st.query_params.get("session") != session_id:
        st.query_params["session"] = session_id
    return session_id


def main():
    st.set_page_config(
        page_title="Jev Gatekeeper & AIDR Sandbox",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    session_id = sync_session_id()

    # Define page references with closures for circular page links
    page_refs = {}

    def _home():
        render_landing_page(
            page_dashboard=page_refs["dashboard"],
            page_insights=page_refs["insights"],
            page_mcp=page_refs["mcp"],
            page_guides=page_refs["guides"],
            page_inspector=page_refs["inspector"],
        )

    def _dashboard():
        render_sandbox_dashboard_page()

    def _insights():
        render_product_insights_view(
            page_dashboard=page_refs["dashboard"],
            page_home=page_refs["home"],
            page_mcp=page_refs["mcp"],
        )

    def _mcp_console():
        render_mcp_console_view()

    def _mcp_guides():
        render_claude_cursor_guide(
            session_id=session_id,
            page_dashboard=page_refs["dashboard"],
            page_mcp=page_refs["mcp"],
            page_inspector=page_refs["inspector"],
        )

    def _mcp_inspector():
        render_mcp_inspector_guide(
            session_id=session_id,
            page_mcp=page_refs["mcp"],
            page_claude=page_refs["guides"],
        )

    page_refs["home"] = st.Page(_home, title="Overview & Walkthrough", icon="🧭", default=True)
    page_refs["dashboard"] = st.Page(_dashboard, title="Live AIDR Control Deck", icon="🎛️")
    page_refs["insights"] = st.Page(_insights, title="Product Insights & Economics", icon="📐")
    page_refs["guides"] = st.Page(_mcp_guides, title="Guide: Claude & Cursor (Option 1)", icon="🖥️")
    page_refs["mcp"] = st.Page(_mcp_console, title="Console: FastMCP Agent (Option 2)", icon="🤖")
    page_refs["inspector"] = st.Page(_mcp_inspector, title="Guide: MCP Inspector (Option 3)", icon="🔬")

    nav = st.navigation(
        {
            "Sandbox Core": [page_refs["home"], page_refs["dashboard"], page_refs["insights"]],
            "MCP Integrations": [page_refs["guides"], page_refs["mcp"], page_refs["inspector"]],
        }
    )
    nav.run()


if __name__ == "__main__":
    main()
