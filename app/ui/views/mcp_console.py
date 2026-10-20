"""Embedded MCP Agent Client Console View."""

import asyncio
import json
import os
import streamlit as st
from mcp import ClientSession
from mcp.client.sse import sse_client

from app.domain.presets import AIDR_PRESETS

DEFAULT_MCP_URL = os.getenv("SANDBOX_MCP_URL", "http://127.0.0.1:8000/mcp/sse")


def render_mcp_console_view():
    """Renders the interactive MCP console running live JSON-RPC calls over SSE."""
    st.title("🤖 FastMCP Agent Interactive Console (Option 2)")
    st.caption("Demonstrating real-time AIDR tool-calling and resource subscriptions over Model Context Protocol.")

    st.info(f"**Connected MCP SSE Endpoint:** `{DEFAULT_MCP_URL}`")

    # =========================================================================
    # 3-STEP MCP DEMO PLAYBOOK & GUIDE (Matches Claude/Cursor Script)
    # =========================================================================
    with st.expander("🎬 3-Step Guided MCP Agent Demo Script", expanded=True):
        st.markdown(
            "Follow this 3-step sequence to see how an autonomous AI agent or IDE extension uses the MCP tools "
            "to inspect code, simulate security incidents, and evaluate fleet posture:"
        )

        col_d1, col_d2, col_d3 = st.columns(3, gap="medium")

        with col_d1:
            with st.container(border=True):
                st.markdown("##### 1️⃣ Step 1: Inspect Synthetic Code")
                st.caption("Verifies AST detects mock fixtures and drops false alarms.")
                p1_sample = "def test_stripe_mock(): mock_key = 'sk_test_fake991283'; mock_ssn = '000-12-3456'"
                st.code(p1_sample, language="python")
                if st.button("▶️ Run Step 1", key="btn_run_step1", use_container_width=True, type="primary"):
                    st.session_state["mcp_selected_tool"] = "scan_source_code_snippet"
                    st.session_state["mcp_input_text"] = p1_sample
                    st.session_state["mcp_auto_execute"] = True
                    st.rerun()

        with col_d2:
            with st.container(border=True):
                st.markdown("##### 2️⃣ Step 2: Leak AWS Secret")
                st.caption("Simulates an engineer inadvertently pasting AWS credentials.")
                p2_sample = "4_production_secret_leak"
                st.code("Preset: 4_production_secret_leak\nAction: BLOCK (HTTP 403)", language="yaml")
                if st.button("▶️ Run Step 2", key="btn_run_step2", use_container_width=True, type="primary"):
                    st.session_state["mcp_selected_tool"] = "simulate_traffic_scenario"
                    st.session_state["mcp_selected_preset"] = p2_sample
                    st.session_state["mcp_auto_execute"] = True
                    st.rerun()

        with col_d3:
            with st.container(border=True):
                st.markdown("##### 3️⃣ Step 3: Check Fleet Posture")
                st.caption("Fetches real-time telemetry, false positive drops, and ROI.")
                st.code("Tool: get_fleet_security_posture\nParams: None", language="yaml")
                if st.button("▶️ Run Step 3", key="btn_run_step3", use_container_width=True, type="primary"):
                    st.session_state["mcp_selected_tool"] = "get_fleet_security_posture"
                    st.session_state["mcp_auto_execute"] = True
                    st.rerun()

    st.divider()

    # =========================================================================
    # TOOL EXECUTION & CAPABILITY DISCOVERY
    # =========================================================================
    col1, col2 = st.columns([1, 1], gap="medium")

    with col1:
        st.subheader("1. Discover MCP Capabilities")
        st.caption("Handshake with the server, list registered tools, schemas, and resource URIs.")
        if st.button("🔍 Run MCP Handshake & List Tools", use_container_width=True, type="primary"):
            async def _discover():
                async with sse_client(DEFAULT_MCP_URL) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        resources = await session.list_resources()
                        return tools, resources

            with st.spinner("Connecting to FastMCP SSE stream..."):
                try:
                    tools_res, res_res = asyncio.run(_discover())
                    st.success("✅ MCP Handshake Successful!")

                    st.markdown("##### 🛠️ Registered Tools:")
                    for t in tools_res.tools:
                        st.markdown(f"- **`{t.name}`**: _{t.description}_")

                    st.markdown("##### 📑 Registered Resources:")
                    for r in res_res.resources:
                        st.markdown(f"- **`{r.uri}`**: {r.name}")
                except Exception as exc:
                    st.error(f"MCP Connection failed: {exc}")

    with col2:
        st.subheader("2. Execute AIDR Tool Call")
        st.caption("Invoke tools dynamically via JSON-RPC 2.0 with full argument preview.")

        tool_options = [
            "inspect_prompt_payload",
            "scan_source_code_snippet",
            "simulate_traffic_scenario",
            "get_fleet_security_posture",
            "approve_policy_override",
        ]
        default_tool_idx = 0
        if "mcp_selected_tool" in st.session_state and st.session_state["mcp_selected_tool"] in tool_options:
            default_tool_idx = tool_options.index(st.session_state["mcp_selected_tool"])

        selected_tool = st.selectbox(
            "Select MCP Tool",
            tool_options,
            index=default_tool_idx,
            key="mcp_tool_selector",
        )

        preset_keys = list(AIDR_PRESETS.keys())
        default_preset_idx = 0
        if "mcp_selected_preset" in st.session_state and st.session_state["mcp_selected_preset"] in preset_keys:
            default_preset_idx = preset_keys.index(st.session_state["mcp_selected_preset"])

        default_text = st.session_state.get(
            "mcp_input_text",
            "def test_mock_token():\n    mock_key = 'sk_test_fake991283'\n    assert mock_key is not None",
        )

        # Tool parameters & rich preview
        if selected_tool == "simulate_traffic_scenario":
            selected_pid = st.selectbox(
                "Choose Scenario Preset to Simulate",
                options=preset_keys,
                index=default_preset_idx,
                format_func=lambda pid: AIDR_PRESETS[pid].title,
            )
            curr_preset = AIDR_PRESETS[selected_pid]
            with st.expander("👁️ Preview Scenario Prompt & Expected Outcome", expanded=True):
                st.markdown(f"**Category:** `{curr_preset.category}` | **Target Client:** `{curr_preset.target_client}`")
                st.markdown(f"**Expected Action:** `{curr_preset.expected_action}` | **Classification:** `{curr_preset.expected_classification}`")
                st.markdown(f"**What It Tests:** {curr_preset.what_it_tests}")
                st.markdown("**Prompt Payload:**")
                st.code(
                    curr_preset.prompt_text,
                    language="python" if "```python" in curr_preset.prompt_text or "def " in curr_preset.prompt_text else "markdown",
                )
            param_input = selected_pid

        elif selected_tool == "get_fleet_security_posture":
            param_input = None
            st.info("ℹ️ `get_fleet_security_posture` queries aggregated fleet telemetry (no parameters needed).")

        elif selected_tool == "approve_policy_override":
            param_input = st.text_input("Incident ID to Override", value="inc_demo_01")
            st.caption("Approves an intervention and whitelists similar prompts.")

        else:
            param_input = st.text_area("Input Prompt / Source Code", default_text, height=120)
            if selected_tool == "scan_source_code_snippet":
                st.caption("💡 Evaluates code syntax via Python AST before running Jev System 1.")
            else:
                st.caption("💡 Full 4-stage pipeline inspection including client identification.")

        # Trigger tool call
        auto_run = st.session_state.pop("mcp_auto_execute", False)
        execute_clicked = st.button("🚀 Execute Tool via JSON-RPC", use_container_width=True, type="primary")

        if execute_clicked or auto_run:
            async def _execute():
                async with sse_client(DEFAULT_MCP_URL) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        if selected_tool == "simulate_traffic_scenario":
                            return await session.call_tool("simulate_traffic_scenario", arguments={"preset_id": param_input})
                        elif selected_tool == "get_fleet_security_posture":
                            return await session.call_tool("get_fleet_security_posture", arguments={})
                        elif selected_tool == "approve_policy_override":
                            return await session.call_tool("approve_policy_override", arguments={"incident_id": param_input, "approved_by": "SecurityAdmin"})
                        elif selected_tool == "scan_source_code_snippet":
                            return await session.call_tool("scan_source_code_snippet", arguments={"code_text": param_input})
                        else:
                            return await session.call_tool("inspect_prompt_payload", arguments={"prompt_text": param_input, "client_name": "MCP Console"})

            with st.spinner("Dispatching JSON-RPC 2.0 tool invocation over SSE..."):
                try:
                    result = asyncio.run(_execute())
                    st.success("✅ JSON-RPC Response Received:")
                    parsed = []
                    for c in getattr(result, "content", []):
                        if hasattr(c, "text"):
                            try:
                                parsed.append(json.loads(c.text))
                            except Exception:
                                parsed.append(c.text)
                    st.json(parsed if parsed else str(result))
                except Exception as exc:
                    st.error(f"Execution error: {exc}")

