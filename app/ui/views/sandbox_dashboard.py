"""Main Live AIDR Control Deck View."""

import json
import re
import uuid
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from app.domain.presets import AIDR_PRESETS
from app.ui.api_client import api_client
from app.ui.components.kpi_header import render_error_banner, render_kpi_header
from app.ui.components.pipeline_card import render_pipeline_walkthrough_card


def render_sandbox_dashboard_page():
    """Renders the Unified AIDR Control Deck."""
    session_id = st.session_state.get("aidr_session_id", "default")

    # Fetch latest telemetry, policy state, and audit stream
    telemetry = api_client.get_telemetry()
    policy_state = api_client.get_policy()
    incidents = api_client.get_incidents(limit=30)

    # Active inspected incident
    active_incident = st.session_state.get("active_inspected_incident")
    if not active_incident and incidents:
        active_incident = incidents[-1]
        st.session_state["active_inspected_incident"] = active_incident

    # Engine status details
    current_engine_mode = policy_state.get("jev_mode", st.session_state.get("ui_jev_mode", "simulated"))
    has_typesafe_key = policy_state.get("has_typesafe_api_key", False)
    block_threshold = policy_state.get("block_threshold", 0.92)
    nudge_threshold = policy_state.get("nudge_threshold", 0.80)
    allow_threshold = policy_state.get("allow_threshold", 0.30)

    # =====================================================================
    # SIDEBAR: WORKSPACE SESSION, 5 PRESETS WITH PREVIEWS, CUSTOM BUILDER, SLIDERS
    # =====================================================================
    with st.sidebar:
        st.title("🎛️ AIDR Control Deck")

        # 0. Multi-User Workspace Session Card
        with st.container(border=True):
            st.markdown(f"**👤 Session Workspace:** `{session_id}`")
            st.caption("All simulations and policy adjustments are isolated to your workspace.")
            with st.expander("Switch or Name Workspace", expanded=False):
                custom_session = st.text_input(
                    "Workspace Key",
                    value=session_id,
                    max_chars=16,
                    help="Alphanumeric, dash, or underscore (e.g. 'alice', 'demo1').",
                    key="custom_session_input",
                )
                if st.button("Switch Workspace", use_container_width=True, key="btn_switch_ws"):
                    clean_s = re.sub(r"[^a-zA-Z0-9_-]", "", custom_session).strip().lower()[:16]
                    if clean_s and clean_s != session_id:
                        st.query_params["session"] = clean_s
                        st.session_state["aidr_session_id"] = clean_s
                        st.session_state.pop("active_inspected_incident", None)
                        st.toast(f"Switched workspace to {clean_s}!", icon="👤")
                        st.rerun()

        st.divider()

        # 1. Five Guided AIDR Presets with Example Prompt Preview
        st.subheader("⚡ 1. Test Guided Presets")
        with st.expander("🎯 Scenario Selector & Prompt Preview", expanded=True):
            preset_keys = list(AIDR_PRESETS.keys())
            selected_scenario_id = st.selectbox(
                "Choose Scenario to Inspect",
                options=preset_keys,
                format_func=lambda pid: AIDR_PRESETS[pid].title,
                key="sidebar_preset_selector",
            )
            selected_preset_data = AIDR_PRESETS[selected_scenario_id]

            st.markdown(f"**Target Client:** `{selected_preset_data.target_client}`")
            st.markdown(f"**Expected Action:** `{selected_preset_data.expected_action}` | **Classification:** `{selected_preset_data.expected_classification}`")
            st.caption(f"**What It Tests:** {selected_preset_data.what_it_tests}")

            st.markdown("**Example Prompt Payload:**")
            st.code(
                selected_preset_data.prompt_text,
                language="python" if "```python" in selected_preset_data.prompt_text or "def " in selected_preset_data.prompt_text else "markdown",
            )

            if st.button(
                "🚀 Inject Selected Scenario",
                key="btn_inject_selected_scenario",
                use_container_width=True,
                type="primary",
            ):
                with st.spinner(f"Evaluating {selected_preset_data.title} via Jev & AST..."):
                    res = api_client.inject_preset(preset_id=selected_scenario_id)
                if res and "record" in res:
                    st.session_state["active_inspected_incident"] = res["record"]
                    act = res["record"].get("applied_action", "ALLOW")
                    st.session_state["last_ui_feedback"] = (
                        f"✅ **Injected Preset:** *{selected_preset_data.title}* → Result: **`{act}`**"
                    )
                    st.toast(f"Injected {selected_preset_data.title} → {act}", icon="⚡")
                    st.rerun()

            st.markdown("---")
            st.caption("Or click any scenario for immediate 1-click execution:")
            for pid, preset in AIDR_PRESETS.items():
                is_key = pid in ("1_synthetic_test_fixture", "4_production_secret_leak")
                if st.button(
                    preset.title,
                    key=f"btn_quick_preset_{pid}",
                    use_container_width=True,
                    type="primary" if is_key else "secondary",
                    help=preset.what_it_tests,
                ):
                    with st.spinner(f"Evaluating {preset.title} via Jev & AST..."):
                        res = api_client.inject_preset(preset_id=pid)
                    if res and "record" in res:
                        st.session_state["active_inspected_incident"] = res["record"]
                        act = res["record"].get("applied_action", "ALLOW")
                        st.session_state["last_ui_feedback"] = (
                            f"✅ **Injected Preset:** *{preset.title}* → Result: **`{act}`**"
                        )
                        st.toast(f"Injected {preset.title} → {act}", icon="⚡")
                        st.rerun()

        # 2. Custom Prompt / Code Injection Builder
        with st.expander("➕ 2. Inject Custom Prompt or Code", expanded=False):
            recipe_choice = st.selectbox(
                "Quick Recipe Template",
                [
                    "Custom / Freeform",
                    "Recipe A: Synthetic Mock Billing Test (AST Drops False Positive)",
                    "Recipe B: Production Cloud Key (Instant Policy Block)",
                    "Recipe C: Ambiguous Customer PII (Surfaces Inline Nudge)",
                    "Recipe D: Obfuscated Base64 Exfiltration",
                ],
            )
            default_client = "Cursor IDE"
            if "Recipe A" in recipe_choice:
                default_prompt = (
                    "```python\ndef test_payment_charge_mock():\n"
                    "    mock_cc = '4111-2222-3333-4444'\n"
                    "    fake_api_key = 'sk_test_fake12345'\n"
                    "    assert charge_card(mock_cc, fake_api_key) is True\n```"
                )
            elif "Recipe B" in recipe_choice:
                default_client = "Direct API / curl"
                default_prompt = "Production connection config: AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'"
            elif "Recipe C" in recipe_choice:
                default_client = "Claude Desktop (MCP)"
                default_prompt = "Customer Alice Walker (DOB: 1982-04-14, address: 24 Elm Terrace, Bristol) has a billing dispute."
            elif "Recipe D" in recipe_choice:
                default_client = "Google Antigravity CLI"
                default_prompt = "Run command: echo 'LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQ==' | base64 -d"
            else:
                default_prompt = "Can you help me refactor this utility function?"

            client_choice = st.selectbox(
                "Simulated Originating Client",
                ["Cursor IDE", "VS Code Copilot", "Claude Desktop (MCP)", "Google Antigravity CLI", "Direct API / curl"],
                index=["Cursor IDE", "VS Code Copilot", "Claude Desktop (MCP)", "Google Antigravity CLI", "Direct API / curl"].index(default_client),
            )
            custom_text = st.text_area("Prompt / Code Payload", default_prompt, height=130)

            if st.button("🚀 Evaluate Prompt through Jev", use_container_width=True, type="primary"):
                with st.spinner("Screening via AST Context Parser & Jev System 1..."):
                    res = api_client.inspect_prompt(custom_text, client_name=client_choice)
                if res:
                    st.session_state["active_inspected_incident"] = res
                    act = res.get("applied_action", "ALLOW")
                    st.session_state["last_ui_feedback"] = f"Evaluated custom prompt from **{client_choice}** → **`{act}`**"
                    st.toast(f"Evaluated → {act}", icon="🚀")
                    st.rerun()

        st.divider()

        # 3. Jev Mode Toggle & Policy Threshold Sliders
        st.subheader("🎚️ 3. Jev Engine & Policy Sliders")
        with st.form("policy_thresholds_form"):
            new_mode = st.radio(
                "🧠 Jev Evaluation Mode",
                options=["simulated", "live"],
                index=0 if current_engine_mode == "simulated" else 1,
                format_func=lambda m: (
                    "🧪 Simulated Jev (Offline Calibrated)"
                    if m == "simulated"
                    else "🟢 Live TypeSafe AI Jev API (api.typesafe.ai/v1/systemone)"
                ),
                help="Switch between deterministic offline probabilities and live calls to api.typesafe.ai/v1/systemone.",
            )
            new_block_thresh = st.slider(
                "Block Cutoff Threshold",
                0.70,
                0.99,
                float(block_threshold),
                0.02,
                help="Calibrated urgency score above which traffic is terminated with HTTP 403.",
            )
            new_nudge_thresh = st.slider(
                "Inline Nudge Threshold",
                0.50,
                0.90,
                float(nudge_threshold),
                0.05,
                help="Calibrated urgency score above which an inline warning nudge is displayed.",
            )
            new_allow_thresh = st.slider(
                "Nominal Allow Threshold",
                0.10,
                0.50,
                float(allow_threshold),
                0.05,
                help="Calibrated score below which traffic is passed with zero logging.",
            )

            if st.form_submit_button("Save Policy Thresholds", use_container_width=True):
                st.session_state["ui_jev_mode"] = new_mode
                api_client.update_policy(
                    {
                        "jev_mode": new_mode,
                        "block_threshold": new_block_thresh,
                        "nudge_threshold": new_nudge_thresh,
                        "allow_threshold": new_allow_thresh,
                    }
                )
                st.session_state["last_ui_feedback"] = (
                    f"🎚️ **Policy Updated:** Mode `{new_mode}` | Block $\\ge {new_block_thresh:.2f}$, "
                    f"Nudge $\\ge {new_nudge_thresh:.2f}$, Allow $\\le {new_allow_thresh:.2f}$."
                )
                st.toast("Policy updated!", icon="✅")
                st.rerun()

        st.divider()

        # 4. System Reset
        if st.button("🔄 Reset Sandbox State", use_container_width=True):
            api_client.reset_sandbox()
            st.session_state.pop("active_inspected_incident", None)
            st.session_state["last_ui_feedback"] = "Sandbox reset to clean nominal baseline."
            st.toast("Sandbox reset completed!", icon="🔄")
            st.rerun()

    # =====================================================================
    # MAIN STAGE: HEADER, KPI BAR, 4-STAGE WALKTHROUGH & AUDIT FEED
    # =====================================================================
    render_error_banner()

    if st.session_state.get("last_ui_feedback"):
        f_col, c_col = st.columns([0.92, 0.08])
        with f_col:
            st.info(st.session_state["last_ui_feedback"])
        with c_col:
            if st.button("✖️", key="dismiss_ui_fb", help="Dismiss"):
                st.session_state["last_ui_feedback"] = None
                st.rerun()

    head1, head2 = st.columns([0.70, 0.30])
    with head1:
        st.title("🛡️ Enterprise AIDR & Jev Gatekeeper Control Deck")
        st.markdown(
            "**Data-in-Motion AI Detection & Response** • **Sub-15ms Latency** • "
            "**AST False-Positive Elimination** • **Dual-Mode Jev System 1**"
        )
    with head2:
        st.metric(
            label="Active Gatekeeper Engine",
            value="🟢 LIVE API" if current_engine_mode == "live" else "🧪 SIMULATED",
            delta="Single-Pass Matrix Scoring (<15ms)",
            delta_color="normal" if current_engine_mode == "live" else "off",
        )

    # =====================================================================
    # EXPLICIT ENGINE STATUS INDICATOR & QUICK-TOGGLE PANEL
    # =====================================================================
    with st.container(border=True):
        c_ind1, c_ind2, c_ind3 = st.columns([0.48, 0.32, 0.20], gap="medium")
        with c_ind1:
            if current_engine_mode == "live":
                st.markdown("##### 🟢 Gatekeeper State: **LIVE TYPESAFE AI API**")
                st.caption(f"Endpoint: `{policy_state.get('typesafe_api_url', 'https://api.typesafe.ai/v1/systemone')}`")
            else:
                st.markdown("##### 🧪 Gatekeeper State: **TEST / SIMULATED JEV**")
                st.caption("Offline calibrated probability model (deterministic evaluation in <15ms)")
        with c_ind2:
            key_text = "🔑 TYPESAFE_API_KEY Configured" if has_typesafe_key else "🔒 No Key (Simulated Fallback)"
            st.markdown(f"**API Auth:** `{key_text}`")
            st.markdown(f"**Cutoffs:** 🛑 Block $\\ge {block_threshold:.2f}$ | ⚠️ Nudge $\\ge {nudge_threshold:.2f}$ | 🟢 Allow $\\le {allow_threshold:.2f}$")
        with c_ind3:
            toggle_target = "live" if current_engine_mode == "simulated" else "simulated"
            toggle_label = "Switch to 🟢 Live API" if current_engine_mode == "simulated" else "Switch to 🧪 Simulated"
            if st.button(toggle_label, key="main_deck_toggle_engine", use_container_width=True, type="secondary"):
                api_client.update_policy({"jev_mode": toggle_target})
                st.session_state["ui_jev_mode"] = toggle_target
                st.session_state["last_ui_feedback"] = f"🎚️ Switched Gatekeeper Engine to **{toggle_target.upper()}** mode."
                st.toast(f"Engine switched to {toggle_target.upper()}", icon="🎚️")
                st.rerun()

    # =====================================================================
    # COMPREHENSIVE CONTROL DECK HELP & ARCHITECTURE GUIDANCE
    # =====================================================================
    with st.expander("📖 Control Deck Guide: Understanding AIDR Data-in-Motion & The 4 Stages", expanded=False):
        st.markdown("""
        ### Why Data-in-Motion AI Detection & Response (AIDR)?
        Traditional enterprise AI security relies heavily on browser extensions and local agents.
        However, extensions create massive blind spots for unmanaged devices (BYOD), headless CI/CD pipelines,
        developer IDEs (Cursor, Copilot), autonomous terminal CLI agents (Antigravity), and backend microservices invoking LLMs directly.

        This **Jev Gatekeeper** intercepts data-in-motion at the proxy and Model Context Protocol (MCP) layers through a 4-stage pipeline:

        1. **Stage 1 — Client Intake & Fingerprinting**: Intercepts prompts, detects originating client morphology (Cursor, Copilot, Claude Desktop, Antigravity CLI, or direct API / curl), and measures token density.
        2. **Stage 2 — AST Context Parser**: Inspects code syntax via Python's Abstract Syntax Tree. When unit tests, mock frameworks (`unittest.mock`, `pytest`), or synthetic fixtures (`mock_key`, `fake_customer_ssn`) are detected, a **95% risk discount** (`0.05× multiplier`) is applied to eliminate developer-disrupting false alarms on test code.
        3. **Stage 3 — Jev System 1 Core**: Evaluates raw inputs in a single feedforward matrix pass (<15ms) on lightweight compute without the multi-hop latency or GPU costs of SLM pipelines.
        4. **Stage 4 — Enforcement & Telemetry**: Applies deterministic policy routing (**`ALLOW`**, **`NUDGE`**, **`REDACT`**, or **`BLOCK`** with HTTP 403) and logs real-time economic cost savings.
        """)

    st.divider()
    render_kpi_header(telemetry)
    st.divider()

    # SECTION 1: 4-STAGE PIPELINE WALKTHROUGH CARD
    if active_incident:
        st.subheader(f"🔬 Active Incident Walkthrough — Incident `{active_incident.get('incident_id')}`")
        render_pipeline_walkthrough_card(active_incident, key_prefix="main_stage_walkthrough")

        # =====================================================================
        # DEDICATED PER-SIMULATION UNIT ECONOMICS & COST BREAKDOWN
        # =====================================================================
        st.markdown("#### 💰 Per-Simulation Unit Economics & Cost Efficiency")
        with st.container(border=True):
            ue_col1, ue_col2, ue_col3, ue_col4 = st.columns(4)
            tok_count = active_incident.get("token_count", 120)
            jev_cost_val = 0.000010
            slm_cost_val = 0.000500
            run_savings_val = slm_cost_val - jev_cost_val
            pct_savings = (run_savings_val / slm_cost_val) * 100

            ue_col1.metric("Evaluated Prompt Size", f"{tok_count} tokens", help="Number of input prompt tokens evaluated in this incident")
            ue_col2.metric("Jev System 1 Compute", f"${jev_cost_val:.6f}", delta="ARM/x86 vCPU (<15ms)", delta_color="normal")
            ue_col3.metric("Traditional SLM Ensemble", f"${slm_cost_val:.6f}", delta="2-4 GPU Instances (150-250ms)", delta_color="inverse")
            ue_col4.metric("Net Run Savings", f"${run_savings_val:.6f}", delta=f"{pct_savings:.1f}% Saved", delta_color="normal")

            with st.expander("📊 Unit Economics Cost Model & Fleet Extrapolation", expanded=False):
                st.markdown("""
                **Monthly Compute Cost Estimation Formula:**
                $$\\text{Total Monthly Cost} = [N_{\\text{requests}} \\times \\text{Tokens}_{\\text{req}} \\times \\text{Cost}_{\\text{Inference}}] + \\text{Infra Fixed Cost} + \\text{Network Egress}$$

                * **Traditional SLM Pipeline Baseline:**
                  * Typically requires 2–4 specialized models running across redundant GPU instances (e.g. 2× AWS `g5.xlarge` @ ~$1.00–$1.50/hr each per region for high availability).
                  * Baseline: **$1,500 – $2,200/month** per active region, plus autoscaling bursts during peak traffic hours.
                * **Jev System 1 Model:**
                  * Runs on lightweight general-purpose compute (e.g. AWS `c7g.xlarge` ARM vCPU @ ~$0.15–$0.25/hr) or edge-evaluated directly in API gateway sidecars (Envoy / Cloudflare Workers).
                  * Baseline: **$150 – $350/month**.
                * **Fleet ROI (Example: 20M Monthly Inspection Requests):**
                  * SLM Ensemble GPU Footprint: **~$10,000 / month** ($120,000 / yr).
                  * Jev System 1 Footprint: **~$200 / month** ($2,400 / yr).
                  * **Projected Savings: 75% to 85%+ compute reduction ($117,600 / yr net savings)** alongside sub-15ms latency that protects developer Time-To-First-Token (TTFT).
                """)

    else:
        st.info("No inspection events recorded yet. Click any preset in the left sidebar to begin!")

    st.divider()

    # SECTION 2: SHADOW AI DISCOVERY & CHRONOLOGICAL AUDIT STREAM
    st.subheader("📊 Live Shadow AI Discovery Feed & Intervention Log")
    st.caption("Chronological stream of prompt requests across IDEs, terminal CLI agents, and backend services.")

    if not incidents:
        st.info("Audit stream is empty. Test a preset or inject a custom prompt from the sidebar.")
    else:
        # Display newest events on top
        for inc in reversed(incidents):
            inc_id = inc.get("incident_id")
            client_tag = inc.get("client_identity", {}).get("client_name", "Unknown")
            applied = inc.get("applied_action", "ALLOW")
            ast_info = inc.get("ast_analysis", {})
            jev_info = inc.get("jev_evaluation", {})
            score = jev_info.get("calibrated_urgency_score", 0.0)
            raw_prompt = inc.get("extracted_prompt_text", "")

            icon_map = {
                "ALLOW": "🟢",
                "SILENT_LOG": "📝",
                "NUDGE": "⚠️",
                "REDACT": "✂️",
                "BLOCK": "🛑",
            }
            action_icon = icon_map.get(applied, "ℹ️")

            with st.expander(
                f"{action_icon} [{applied}] {client_tag} — Score: {score:.2f} | Incident `{inc_id}`",
                expanded=False,
            ):
                st.markdown(f"**Prompt Snippet:**  \n_{raw_prompt[:250]}..._")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Originating Client", client_tag)
                m2.metric("AST Synthetic Fixture?", "Yes (Discounted)" if ast_info.get("is_synthetic_test_fixture") else "No")
                m3.metric("Data Classification", jev_info.get("data_classification", "Clean"))
                m4.metric("Calibrated Score", f"{score:.2f}")

                st.caption(f"Reasoning: {jev_info.get('reasoning_summary', 'N/A')}")

