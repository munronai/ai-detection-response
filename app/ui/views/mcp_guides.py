"""MCP Integration Setup Guides for External AI Clients and Official MCP Inspector."""

import os
from typing import Any
import streamlit as st

DEFAULT_MCP_URL = os.getenv("SANDBOX_MCP_URL", "http://127.0.0.1:8000/mcp/sse")


def render_claude_cursor_guide(
    session_id: str = "default",
    page_dashboard: Any = None,
    page_mcp: Any = None,
    page_inspector: Any = None,
):
    """Option 1: Connecting Claude Desktop or Cursor IDE to the live MCP endpoint."""
    st.title("🖥️ Connect Claude Desktop & Cursor IDE (Option 1)")
    st.caption(
        "Allow autonomous AI agents to query the Jev Gatekeeper and inspect code over MCP."
    )

    st.info(f"**Target FastMCP SSE URL:** `{DEFAULT_MCP_URL}`")

    top_c1, top_c2 = st.columns([0.70, 0.30])
    with top_c2:
        if page_mcp is not None:
            st.page_link(
                page_mcp,
                label="Open Browser MCP Console (Option 2) →",
                icon="🤖",
                use_container_width=True,
            )
        if page_inspector is not None:
            st.page_link(
                page_inspector,
                label="Open Official MCP Inspector (Option 3) →",
                icon="🔬",
                use_container_width=True,
            )

    tab1, tab2, tab3 = st.tabs(
        ["💬 Claude Desktop Setup", "💻 Cursor IDE Setup", "🧪 3-Step Demo Prompts"]
    )

    with tab1:
        st.markdown("### Claude Desktop Setup (via `mcp-remote` Bridge)")
        st.markdown("""
        Claude Desktop requires an active `stdio` bridge process to connect to Server-Sent Events (SSE).
        Use the official `mcp-remote` bridge with the mandatory `--transport sse-only` flag to avoid HTTP 405 errors.

        #### Step 1: Open `claude_desktop_config.json`
        * **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
        * **Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`

        #### Step 2: Paste the Server Block
        """)

        claude_config = f"""{{
  "mcpServers": {{
    "jev-aidr-gatekeeper": {{
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "{DEFAULT_MCP_URL}",
        "--transport",
        "sse-only"
      ]
    }}
  }}
}}"""
        st.code(claude_config, language="json")

        st.markdown("""
        #### Step 3: Restart Claude Desktop
        Quit and reopen Claude. The 🔨 hammer icon will display:
        * `inspect_prompt_payload`: Runs full 4-stage AIDR inspection.
        * `scan_source_code_snippet`: Code-specific AST + Jev evaluation.
        * `simulate_traffic_scenario`: Injects any of the 5 Golden Presets.
        * `approve_policy_override`: Approves or whitelists flagged incidents.
        * `get_fleet_security_posture`: Returns fleet scan metrics and cost savings.
        """)

    with tab2:
        st.markdown("### Cursor IDE Setup")
        st.markdown("""
        Cursor connects natively to remote or local SSE endpoints without requiring a Node.js bridge.

        #### Step 1: Open Cursor Settings
        Go to **Settings** → **Features** → **MCP** → **Add New MCP Server**.

        #### Step 2: Add Configuration
        """)

        cursor_config = f"""{{
  "mcpServers": {{
    "jev-aidr-gatekeeper": {{
      "url": "{DEFAULT_MCP_URL}"
    }}
  }}
}}"""
        st.code(cursor_config, language="json")
        st.markdown(
            "Click **Refresh** in Cursor to see the status indicator turn green."
        )

    with tab3:
        st.markdown("### 🎬 3-Step Autonomous Agent Demo Script")
        st.markdown(
            "Run the following prompts in Claude Desktop or Cursor to showcase the closed-loop workflow:"
        )

        with st.container(border=True):
            st.markdown("#### Step 1: Inspect a Synthetic Test Fixture")
            p1 = "Can you use your inspect_prompt_payload tool to check if this billing test contains real secrets: def test_stripe(): mock_card = '4111-2222-3333-4444'; fake_key = 'sk_test_fake9912'?"
            st.code(p1, language="markdown")
            st.caption(
                "Agent calls `inspect_prompt_payload`, confirms AST identified a synthetic test fixture, and notes the 95% risk discount."
            )

        with st.container(border=True):
            st.markdown("#### Step 2: Simulate a Production Secret Leak")
            p2 = "Simulate what happens if an engineer leaks AWS root credentials using simulate_traffic_scenario with preset_id='4_production_secret_leak'."
            st.code(p2, language="markdown")
            st.caption(
                "Agent calls `simulate_traffic_scenario`, inspects Jev's 0.98 score, and explains why traffic was blocked with HTTP 403."
            )

        with st.container(border=True):
            st.markdown("#### Step 3: Check Fleet Security Posture")
            p3 = "Check our fleet security posture with get_fleet_security_posture and tell me how many false alarms were dropped by AST and our total dollar savings."
            st.code(p3, language="markdown")
            st.caption(
                "Agent reads live telemetry and reports aggregate scans, false positives dropped, and cost ROI."
            )


def render_mcp_inspector_guide(
    session_id: str = "default",
    page_mcp: Any = None,
    page_claude: Any = None,
):
    """Option 3: Official MCP Inspector CLI Visualizer."""
    st.title("🔬 Guide: Official MCP Inspector Visualizer (Option 3)")
    st.caption(
        "Zero-code developer visualizer to debug SSE connection health, test tool schemas, and read resources."
    )

    st.markdown("""
    The **[MCP Inspector](https://github.com/modelcontextprotocol/inspector)** is the reference developer tool
    maintained by the Model Context Protocol project. It lets anyone inspect JSON-RPC payloads, validate tool schemas,
    and test live endpoints in a web browser without setting up Claude Desktop.
    """)

    st.info(f"**Target FastMCP SSE URL:** `{DEFAULT_MCP_URL}`")

    top_c1, top_c2 = st.columns([0.70, 0.30])
    with top_c2:
        if page_mcp is not None:
            st.page_link(
                page_mcp,
                label="Open Browser MCP Console (Option 2) →",
                icon="🤖",
                use_container_width=True,
            )
        if page_claude is not None:
            st.page_link(
                page_claude,
                label="Open Claude & Cursor Guide (Option 1) →",
                icon="🖥️",
                use_container_width=True,
            )

    st.divider()

    st.markdown("### Step 1: Launch the Official Inspector via npx")
    st.markdown(
        "Ensure the FastAPI server is running on port `8000`, then execute in your terminal:"
    )

    st.code(
        f"npx @modelcontextprotocol/inspector@latest {DEFAULT_MCP_URL}", language="bash"
    )

    st.caption(
        f"Tip: When the Inspector launches, verify **Transport Type** is set to **SSE** and "
        f"**URL** is set to `{DEFAULT_MCP_URL}`, then click **Connect**."
    )

    st.markdown("### Step 2: Diagnostic Panels Available in the Inspector Web UI")
    st.markdown(
        "Open the URL printed in your terminal (typically `http://localhost:5173` or `http://localhost:6274`):"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 📡 1. Connection Ping")
            st.write(
                "Verifies active SSE streaming from `/mcp/sse` and displays protocol version handshakes."
            )
    with c2:
        with st.container(border=True):
            st.markdown("#### 🛠️ 2. Tool Form Testers")
            st.write(
                "Provides interactive form inputs pre-populated with exact Pydantic parameter schemas for "
                "`inspect_prompt_payload`, `simulate_traffic_scenario`, and `approve_policy_override`."
            )
    with c3:
        with st.container(border=True):
            st.markdown("#### 📑 3. Live Resource Reader")
            st.write(
                "Reads `aidr://telemetry/live-kpis`, `aidr://presets/catalog`, and `aidr://incidents/latest` JSON resources."
            )

    st.markdown("### Step 3: What to Test During an Evaluation")
    st.markdown("""
    1. Select **Tools** → `simulate_traffic_scenario`.
    2. Set `preset_id` to `1_synthetic_test_fixture` and click **Run Tool**.
    3. Notice that `applied_action` is **`ALLOW`** and `is_synthetic_test_fixture` is **`True`** because AST discounted the mock data.
    4. Switch to `4_production_secret_leak` and verify it immediately returns **`BLOCK`** with a risk score of `0.98`.
    5. Switch to **Resources** → read `aidr://telemetry/live-kpis` to observe the scan count and cost savings update.
    """)
