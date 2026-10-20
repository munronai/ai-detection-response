"""UI views export."""

from app.ui.views.landing_page import render_landing_page
from app.ui.views.mcp_console import render_mcp_console_view
from app.ui.views.mcp_guides import render_claude_cursor_guide, render_mcp_inspector_guide
from app.ui.views.product_insights import render_product_insights_view
from app.ui.views.sandbox_dashboard import render_sandbox_dashboard_page

__all__ = [
    "render_claude_cursor_guide",
    "render_landing_page",
    "render_mcp_console_view",
    "render_mcp_inspector_guide",
    "render_product_insights_view",
    "render_sandbox_dashboard_page",
]
