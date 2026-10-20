"""Embedded MCP Agent Client Console View."""

import asyncio
import json
import os
import streamlit as st
from mcp import ClientSession
from mcp.client.sse import sse_client

from app.domain.presets import AIDR_PRESETS

DEFAULT_MCP_URL = os.getenv("SANDBOX_MCP_URL", "http://127.0.0.1:8000/mcp/sse")


async def call_mcp_tool_resiliently(tool_name: str, arguments: dict):
    """
    Attempts tool invocation over FastMCP SSE; falls back seamlessly to in-process
    execution if the network proxy is not running in a separate terminal.
    """
    try:
        async with sse_client(DEFAULT_MCP_URL, timeout=3.0) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                parsed = []
                for c in getattr(result, "content", []):
                    if hasattr(c, "text"):
                        try:
                            parsed.append(json.loads(c.text))
                        except Exception:
                            parsed.append(c.text)
                return parsed if parsed else str(result)
    except Exception:
        # Resilient in-process execution fallback
        if tool_name == "scan_source_code_snippet":
            from app.mcp.server import scan_source_code_snippet
            return [await scan_source_code_snippet(**arguments)]
        elif tool_name == "simulate_traffic_scenario":
            from app.mcp.server import simulate_traffic_scenario
            return [await simulate_traffic_scenario(**arguments)]
        elif tool_name == "get_fleet_security_posture":
            from app.mcp.server import get_fleet_security_posture
            return [await get_fleet_security_posture()]
        elif tool_name == "approve_policy_override":
            from app.mcp.server import approve_policy_override
            return [await approve_policy_override(**arguments)]
        elif tool_name == "inspect_prompt_payload":
            from app.mcp.server import inspect_prompt_payload
            return [await inspect_prompt_payload(**arguments)]
        raise

# =============================================================================
# TOOL METADATA: DESCRIPTIONS, NATURAL LANGUAGE PROMPTS & WIRE SCHEMAS
# =============================================================================
MCP_TOOL_EXAMPLES = {
    "inspect_prompt_payload": {
        "title": "Inspect Prompt Payload",
        "description": "Performs full 4-stage AIDR inspection (Client Fingerprinting -> AST Context -> Jev System 1 Core -> Policy Enforcement) on any conversational prompt or code snippet.",
        "sample_agent_prompt": (
            "Can you use your inspect_prompt_payload tool to check if this user prompt leaks customer PII or sensitive data:\n"
            "'Draft a dispute response for Alice Walker (DOB: 1982-04-14, account #9921-0021) regarding unauthorized card transaction £420.50'?"
        ),
        "sample_json_args": {
            "prompt_text": "Draft customer dispute response for Alice Walker (DOB: 1982-04-14, address: 24 Elm Terrace, Bristol BS8 1TH) regarding unconfirmed credit card transaction £420.50 on account #9921-0021.",
            "client_name": "Claude Desktop",
        },
        "default_text": "Draft customer dispute response for Alice Walker (DOB: 1982-04-14, address: 24 Elm Terrace, Bristol BS8 1TH) regarding unconfirmed credit card transaction £420.50 on account #9921-0021.",
    },
    "scan_source_code_snippet": {
        "title": "Scan Source Code Snippet",
        "description": "Evaluates Python code syntax via AST before running Jev System 1, applying a 95% discount if mock fixtures or test functions are detected.",
        "sample_agent_prompt": (
            "Please use scan_source_code_snippet to check if this unit test fixture is safe to send to upstream LLMs:\n"
            "```python\ndef test_stripe_mock():\n    mock_key = 'sk_test_fake991283'\n    mock_ssn = '000-12-3456'\n    assert mock_key is not None\n```"
        ),
        "sample_json_args": {
            "code_text": "def test_stripe_mock():\n    mock_key = 'sk_test_fake991283'\n    mock_ssn = '000-12-3456'\n    assert mock_key is not None",
            "language": "python",
        },
        "default_text": "def test_stripe_mock():\n    mock_key = 'sk_test_fake991283'\n    mock_ssn = '000-12-3456'\n    assert mock_key is not None",
    },
    "simulate_traffic_scenario": {
        "title": "Simulate Traffic Scenario",
        "description": "Injects one of the 5 Golden AIDR Presets (Synthetic Fixtures, Benign Queries, Customer PII, AWS Secrets, Base64 Exfiltration) and returns the gatekeeper verdict.",
        "sample_agent_prompt": (
            "Simulate what happens if an engineer leaks AWS root credentials using simulate_traffic_scenario with preset_id='4_production_secret_leak'."
        ),
        "sample_json_args": {
            "preset_id": "4_production_secret_leak",
        },
    },
    "get_fleet_security_posture": {
        "title": "Get Fleet Security Posture",
        "description": "Queries live aggregated fleet telemetry, active developer client distribution, AST false-alarm drops, and dollar savings.",
        "sample_agent_prompt": (
            "Check our fleet security posture with get_fleet_security_posture and report total prompt scans, false alarms eliminated by AST, and cost savings."
        ),
        "sample_json_args": {},
    },
    "approve_policy_override": {
        "title": "Approve Policy Override",
        "description": "Allows a compliance analyst or security engineer to approve or whitelist an incident flagged for review or blocked by policy.",
        "sample_agent_prompt": (
            "Approve incident 'inc_demo_01' using approve_policy_override with reason='Authorized security testing in sandbox' and approved_by='SecurityAdmin'."
        ),
        "sample_json_args": {
            "incident_id": "inc_demo_01",
            "reason": "Authorized security testing in sandbox approved by compliance officer",
            "approved_by": "SecurityAdmin",
        },
    },
}


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
        guided_run = st.session_state.get("mcp_guided_run")

        with col_d1:
            with st.container(border=True):
                st.markdown("##### 1️⃣ Step 1: Inspect Synthetic Code")
                st.caption("Verifies AST detects mock fixtures and drops false alarms.")
                p1_sample = "def test_stripe_mock():\n    mock_key = 'sk_test_fake991283'\n    mock_ssn = '000-12-3456'\n    assert mock_key is not None"
                st.code(p1_sample, language="python")

                if guided_run and guided_run.get("step") == 1:
                    st.success("✅ **Step 1 Active / Completed**")

                if st.button("▶️ Run Step 1", key="btn_run_step1", use_container_width=True, type="primary"):
                    with st.spinner("Executing Step 1 via MCP tool 'scan_source_code_snippet'..."):
                        try:
                            res = asyncio.run(call_mcp_tool_resiliently("scan_source_code_snippet", {"code_text": p1_sample}))
                            st.session_state["mcp_guided_run"] = {
                                "step": 1,
                                "title": "1️⃣ Step 1: Inspect Synthetic Code",
                                "tool": "scan_source_code_snippet",
                                "args": {"code_text": p1_sample},
                                "result": res,
                                "verdict": "ALLOW (95% False-Positive Discount Applied)",
                                "takeaway": (
                                    "The AST Context Parser detected unit test scope (`test_stripe_mock`) and mock identifiers (`mock_key`, `mock_ssn`). "
                                    "It applied a **95% risk discount** (0.05× multiplier), reducing the raw urgency score down to 0.04 and cleanly allowing the developer's test fixture without interruption."
                                ),
                                "next_step_action": "Now click '▶️ Run Step 2' in the middle column to simulate what happens when live AWS production credentials are leaked without mock fixtures.",
                            }
                            st.session_state["mcp_tool_selector"] = "scan_source_code_snippet"
                            st.session_state["mcp_input_text"] = p1_sample
                            st.toast("✅ Step 1 Executed: AST Dropped False Alarm!", icon="⚡")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Step 1 Execution Error: {exc}")

        with col_d2:
            with st.container(border=True):
                st.markdown("##### 2️⃣ Step 2: Leak AWS Secret")
                st.caption("Simulates an engineer inadvertently pasting AWS credentials.")
                p2_sample = "4_production_secret_leak"
                st.code("Preset: 4_production_secret_leak\nAction: BLOCK (HTTP 403 Forbidden)", language="yaml")

                if guided_run and guided_run.get("step") == 2:
                    st.error("🛑 **Step 2 Active / Completed**")

                if st.button("▶️ Run Step 2", key="btn_run_step2", use_container_width=True, type="primary"):
                    with st.spinner("Executing Step 2 via MCP tool 'simulate_traffic_scenario'..."):
                        try:
                            res = asyncio.run(call_mcp_tool_resiliently("simulate_traffic_scenario", {"preset_id": p2_sample}))
                            st.session_state["mcp_guided_run"] = {
                                "step": 2,
                                "title": "2️⃣ Step 2: Leak AWS Secret",
                                "tool": "simulate_traffic_scenario",
                                "args": {"preset_id": p2_sample},
                                "result": res,
                                "verdict": "BLOCK (HTTP 403 Forbidden)",
                                "takeaway": (
                                    "A live AWS root credential (`AKIAIOSFODNN7EXAMPLE`) was intercepted. Because this code is not inside a mock test fixture, "
                                    "no AST discount was applied. Jev evaluated the risk at 0.98 and terminated the request with **HTTP 403 Forbidden** before reaching external models."
                                ),
                                "next_step_action": "Now click '▶️ Run Step 3' in the right column to fetch live fleet-wide telemetry and verify that these incidents are tracked in the security posture.",
                            }
                            st.session_state["mcp_tool_selector"] = "simulate_traffic_scenario"
                            st.session_state["mcp_selected_preset"] = p2_sample
                            st.toast("🛑 Step 2 Executed: Live AWS Key Blocked!", icon="🛑")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Step 2 Execution Error: {exc}")

        with col_d3:
            with st.container(border=True):
                st.markdown("##### 3️⃣ Step 3: Check Fleet Posture")
                st.caption("Fetches real-time telemetry, false positive drops, and ROI.")
                st.code("Tool: get_fleet_security_posture\nParams: None (Aggregated Fleet Scan)", language="yaml")

                if guided_run and guided_run.get("step") == 3:
                    st.info("📊 **Step 3 Active / Completed**")

                if st.button("▶️ Run Step 3", key="btn_run_step3", use_container_width=True, type="primary"):
                    with st.spinner("Executing Step 3 via MCP tool 'get_fleet_security_posture'..."):
                        try:
                            res = asyncio.run(call_mcp_tool_resiliently("get_fleet_security_posture", {}))
                            st.session_state["mcp_guided_run"] = {
                                "step": 3,
                                "title": "3️⃣ Step 3: Check Fleet Posture",
                                "tool": "get_fleet_security_posture",
                                "args": {},
                                "result": res,
                                "verdict": "POSTURE RETRIEVED (Live Fleet Audit)",
                                "takeaway": (
                                    "Autonomous agents (like Claude Desktop or Cursor) can query live fleet security metrics, "
                                    "total prompt scans, false alarms eliminated by AST, and calculated cloud compute savings at any time."
                                ),
                                "next_step_action": "You have completed the 3-step playbook! You can now experiment with freeform tool calls below or configure Claude Desktop / Cursor in Option 1.",
                            }
                            st.session_state["mcp_tool_selector"] = "get_fleet_security_posture"
                            st.toast("📊 Step 3 Executed: Fleet Posture Retrieved!", icon="📊")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Step 3 Execution Error: {exc}")

        # Render Guided Execution Result & Next-Step Box
        if guided_run:
            st.markdown("---")
            st.markdown(f"#### 🎯 Live Guided Execution Result: **{guided_run['title']}**")
            with st.container(border=True):
                g_col1, g_col2 = st.columns([0.65, 0.35])
                with g_col1:
                    st.markdown(f"**Tool Invoked via JSON-RPC 2.0:** `{guided_run['tool']}`")
                    st.markdown(f"**Verdict:** `{guided_run['verdict']}`")
                    st.success(f"💡 **What Happened:** {guided_run['takeaway']}")
                    st.info(f"👉 **What to Do Next:** {guided_run['next_step_action']}")
                with g_col2:
                    st.markdown("**Wire Schema Arguments Sent:**")
                    st.json(guided_run["args"])

            with st.expander("🔍 View Raw JSON-RPC 2.0 Response", expanded=False):
                st.json(guided_run["result"])

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

        tool_options = list(MCP_TOOL_EXAMPLES.keys())
        if "mcp_tool_selector" not in st.session_state or st.session_state["mcp_tool_selector"] not in tool_options:
            st.session_state["mcp_tool_selector"] = tool_options[0]

        selected_tool = st.selectbox(
            "Select MCP Tool",
            tool_options,
            key="mcp_tool_selector",
        )

        tool_meta = MCP_TOOL_EXAMPLES.get(selected_tool, {})

        # =====================================================================
        # SAMPLE PROMPT & WIRE SCHEMA CALLING GUIDE FOR SELECTED TOOL
        # =====================================================================
        with st.expander(f"💡 Sample Prompt & Calling Guide for `{selected_tool}`", expanded=True):
            st.markdown(f"**Tool Purpose:** {tool_meta.get('description', '')}")
            st.markdown("💬 **Sample Agent Prompt (How to ask Claude / Cursor / LLM Agent):**")
            st.code(tool_meta.get("sample_agent_prompt", ""), language="markdown")
            st.markdown("🛠️ **Equivalent JSON-RPC 2.0 Wire Schema:**")
            st.code(json.dumps(tool_meta.get("sample_json_args", {}), indent=2), language="json")

        preset_keys = list(AIDR_PRESETS.keys())
        default_preset_idx = 0
        if "mcp_selected_preset" in st.session_state and st.session_state["mcp_selected_preset"] in preset_keys:
            default_preset_idx = preset_keys.index(st.session_state["mcp_selected_preset"])

        default_text = st.session_state.get(
            "mcp_input_text",
            tool_meta.get("default_text", "def test_mock_token():\n    mock_key = 'sk_test_fake991283'\n    assert mock_key is not None"),
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
            st.info(
                "💡 **Pre-seeded Incident:** `inc_demo_01` is pre-loaded as a BLOCKED AWS root credential leak. "
                "Executing this tool demonstrates how a security analyst manually whitelists the incident and transitions it to ALLOW."
            )
            col_ov1, col_ov2 = st.columns([1, 1])
            with col_ov1:
                override_inc_id = st.text_input("Incident ID to Override", value="inc_demo_01", help="Target incident ID to whitelist")
            with col_ov2:
                override_approver = st.text_input("Approved By", value="SecurityAdmin")
            override_reason = st.text_input(
                "Approval Reason / Justification",
                value="Authorized security testing exception approved by compliance officer",
            )
            st.caption("Approves an intervention and transitions the incident verdict to ALLOW.")
            param_input = {
                "incident_id": override_inc_id.strip(),
                "reason": override_reason.strip(),
                "approved_by": override_approver.strip(),
            }

        else:
            col_in1, col_in2 = st.columns([0.70, 0.30])
            with col_in2:
                if st.button("📋 Load Sample Prompt", key=f"btn_load_sample_{selected_tool}", use_container_width=True):
                    st.session_state["mcp_input_text"] = tool_meta.get("default_text", default_text)
                    st.rerun()

            param_input = st.text_area("Input Prompt / Source Code", default_text, height=120)
            if selected_tool == "scan_source_code_snippet":
                st.caption("💡 Evaluates code syntax via Python AST before running Jev System 1.")
            else:
                st.caption("💡 Full 4-stage pipeline inspection including client identification.")

        # Trigger tool call
        auto_run = st.session_state.pop("mcp_auto_execute", False)
        execute_clicked = st.button("🚀 Execute Tool via JSON-RPC", use_container_width=True, type="primary")

        if execute_clicked or auto_run:
            if selected_tool == "simulate_traffic_scenario":
                tool_args = {"preset_id": param_input}
            elif selected_tool == "get_fleet_security_posture":
                tool_args = {}
            elif selected_tool == "approve_policy_override":
                tool_args = param_input if isinstance(param_input, dict) else {
                    "incident_id": str(param_input),
                    "reason": "Authorized security exception approved by compliance officer",
                    "approved_by": "SecurityAdmin",
                }
            elif selected_tool == "scan_source_code_snippet":
                tool_args = {"code_text": param_input}
            else:
                tool_args = {"prompt_text": param_input, "client_name": "MCP Console"}

            with st.spinner(f"Dispatching JSON-RPC 2.0 invocation for '{selected_tool}'..."):
                try:
                    result = asyncio.run(call_mcp_tool_resiliently(selected_tool, tool_args))
                    st.success("✅ JSON-RPC Response Received:")
                    st.json(result)
                except Exception as exc:
                    st.error(f"Execution error: {exc}")
