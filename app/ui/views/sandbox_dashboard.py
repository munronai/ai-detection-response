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
            exp_action = "WARNING" if selected_preset_data.expected_action == "NUDGE" else selected_preset_data.expected_action
            st.markdown(f"**Actor / Persona:** `{selected_preset_data.persona_role or 'Enterprise Staff'}`")
            st.markdown(f"**Expected Action:** `{exp_action}` | **Classification:** `{selected_preset_data.expected_classification}`")
            if selected_preset_data.business_context:
                st.caption(f"**Context:** {selected_preset_data.business_context}")
            st.caption(f"**Interception Point:** {selected_preset_data.interception_trigger}")

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



        # 2. Custom Prompt / Code Injection Builder
        with st.expander("➕ 2. Inject Custom Prompt or Code", expanded=False):
            recipe_choice = st.selectbox(
                "Quick Recipe Template",
                [
                    "Custom / Freeform",
                    "Recipe A: Synthetic Mock Billing Test (AST Drops False Positive)",
                    "Recipe B: Production Cloud Key (Instant Policy Block)",
                    "Recipe C: Ambiguous Customer PII (Surfaces Policy Warning)",
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
                default_client = "Microsoft 365 Copilot (Edge Enterprise)"
                default_prompt = "Generate an executive account summary and revenue deck for customer Alice Walker (DOB: 1982-04-14, residential address: 24 Elm Terrace, Bristol BS8 1TH) regarding disputed credit card transaction £420.50 on account #9921-0021."
            elif "Recipe D" in recipe_choice:
                default_client = "Google Antigravity CLI"
                default_prompt = "Run command: echo 'LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQ==' | base64 -d"
            else:
                default_prompt = "Can you help me refactor this utility function?"

            client_options = [
                "Microsoft 365 Copilot (Edge Enterprise)",
                "Cursor IDE",
                "VS Code Copilot",
                "Claude Desktop (MCP)",
                "Google Antigravity CLI",
                "Direct API / curl",
            ]
            client_choice = st.selectbox(
                "Simulated Originating Client",
                client_options,
                index=client_options.index(default_client) if default_client in client_options else 0,
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
                "Inline Policy Warning Threshold (formerly Nudge)",
                0.50,
                0.90,
                float(nudge_threshold),
                0.05,
                help="Calibrated urgency score above which an inline warning dialog is presented to the user.",
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
            st.markdown(f"**Cutoffs:** 🛑 Block $\\ge {block_threshold:.2f}$ | ⚠️ Warning $\\ge {nudge_threshold:.2f}$ | 🟢 Allow $\\le {allow_threshold:.2f}$")
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
    # TABBED MAIN STAGE: 1) LIVE SIMULATION, 2) UNIT ECONOMICS, 3) OPERATIONAL GUIDE
    # =====================================================================
    tab_live, tab_economics, tab_guide = st.tabs([
        "🎛️ Live Pipeline & User Simulation",
        "💰 Unit Economics & Fleet Modeling",
        "📖 Help & Operational Guidance",
    ])

    # ---------------------------------------------------------------------
    # TAB 1: LIVE PIPELINE & FRONTLINE USER EXPERIENCE SIMULATION
    # ---------------------------------------------------------------------
    with tab_live:
        render_kpi_header(telemetry)
        st.markdown("---")

        if active_incident:
            # 1. Match active incident to preset or infer realistic enterprise persona
            raw_prompt = active_incident.get("extracted_prompt_text", "")
            matched_preset = None
            for p in AIDR_PRESETS.values():
                if p.prompt_text.strip() == raw_prompt.strip() or p.preset_id in active_incident.get("incident_id", ""):
                    matched_preset = p
                    break

            client_name = active_incident.get("client_identity", {}).get("client_name", "Unknown Client")
            applied_action = active_incident.get("applied_action", "ALLOW")
            ast_info = active_incident.get("ast_analysis", {})
            jev_info = active_incident.get("jev_evaluation", {})

            if matched_preset:
                persona_role = matched_preset.persona_role or "Enterprise Staff"
                business_context = matched_preset.business_context or "Enterprise AI interaction"
                interception_trigger = matched_preset.interception_trigger or "On Prompt Submission — Pre-flight boundary"
            else:
                if "Copilot" in client_name:
                    persona_role = "Regional Sales / Operations Manager"
                    business_context = "Requesting executive report generation and customer summary via Microsoft 365 Copilot"
                    interception_trigger = "On Prompt Submission ('Generate' clicked in Copilot) — Pre-flight boundary"
                elif "Cursor" in client_name or "VS Code" in client_name:
                    persona_role = "Senior Software Engineer"
                    business_context = "Refactoring application source code and writing unit test stubs"
                    interception_trigger = "On Prompt Submission in IDE chat — Pre-flight boundary"
                else:
                    persona_role = "Enterprise Staff"
                    business_context = "Interactive AI prompt dispatch"
                    interception_trigger = "On Prompt Dispatch — Pre-flight boundary"

            # 2. Enterprise Context & Interception Boundary Banner
            st.subheader(f"🏢 Frontline Enterprise Context — Incident `{active_incident.get('incident_id')}`")
            with st.container(border=True):
                ep1, ep2, ep3 = st.columns([0.30, 0.40, 0.30])
                with ep1:
                    st.markdown(f"**👤 Enterprise Actor:**  \n`{persona_role}`")
                    st.caption(f"Channel: `{client_name}`")
                with ep2:
                    st.markdown(f"**💼 Business Task:**  \n`{business_context}`")
                    st.caption("Prompt evaluated at corporate boundary")
                with ep3:
                    st.markdown(f"**⚡ Interception Boundary:**  \n`{interception_trigger}`")
                    st.caption("Single pre-flight verification")

                st.markdown("**📝 User Content Being Evaluated (Prompt / Code):**")
                st.code(
                    raw_prompt,
                    language="python" if "```python" in raw_prompt or "def " in raw_prompt or "import " in raw_prompt else "markdown",
                )

            # 3. Simulated Frontline Screen: What the Employee Actually Sees
            with st.container(border=True):
                st.markdown("#### 🖥️ Frontline User Screen: What the Employee Actually Sees")

                if applied_action == "NUDGE":
                    st.warning(
                        "### ⚠️ Corporate AI Policy Warning: Customer PII Detected\n\n"
                        f"**{client_name}** intercepted an outbound prompt containing unmasked customer records "
                        "*(e.g. unmasked Date of Birth and residential address)*.\n\n"
                        "**Corporate Policy:** `DP-104 (Customer PII Protection & Data Minimization)`  \n"
                        "**Required Action:** Please confirm this request complies with customer data governance before dispatching to external models."
                    )
                    sim_c1, sim_c2, sim_c3 = st.columns(3)
                    with sim_c1:
                        if st.button("✂️ Redact PII & Send", key="btn_sim_redact", use_container_width=True):
                            st.session_state["frontline_sim_feedback"] = "redact"
                    with sim_c2:
                        if st.button("⚠️ Acknowledge Policy & Submit", key="btn_sim_ack", use_container_width=True, type="primary"):
                            st.session_state["frontline_sim_feedback"] = "ack"
                    with sim_c3:
                        if st.button("🛑 Cancel Request", key="btn_sim_cancel", use_container_width=True):
                            st.session_state["frontline_sim_feedback"] = "cancel"

                    sim_fb = st.session_state.get("frontline_sim_feedback")
                    if sim_fb == "ack":
                        st.success(
                            "✅ **User Confirmed:** Sales Manager acknowledged Policy DP-104 with reason: "
                            "*'Authorized Q3 executive dispute review'*. Justification logged to SOC SIEM. Prompt dispatched to Copilot."
                        )
                    elif sim_fb == "redact":
                        st.info(
                            "✂️ **PII Masked:** Sensitive tokens sanitized: "
                            "`Alice Walker (DOB: [REDACTED], address: [REDACTED_BRISTOL])`. Cleaned prompt forwarded safely."
                        )
                    elif sim_fb == "cancel":
                        st.error("🛑 **User Cancelled:** Prompt aborted before egress. Zero data shared with external LLM.")

                elif applied_action == "BLOCK":
                    st.error(
                        "### 🚫 Outbound Request Terminated by AI Security Policy SEC-201\n\n"
                        "**Reason:** High-risk credentials detected (`Live AWS Root Key ID`).\n\n"
                        "**Enforcement:** HTTP 403 Forbidden. Outbound payload was dropped at the network boundary before reaching external models.\n\n"
                        f"**Security Telemetry:** Incident `{active_incident.get('incident_id')}` escalated to SOC incident response queue."
                    )
                elif applied_action == "ALLOW":
                    if ast_info.get("is_synthetic_test_fixture"):
                        st.success(
                            "### 🟢 Prompt Permitted (AST Verified Synthetic Fixture)\n\n"
                            "The AST Context Parser verified that mock payment keys are declared inside a `pytest` test fixture. "
                            "A **95% false-positive discount** was applied. The developer experienced **zero disruption or false alarms** "
                            "(evaluation completed in 12ms)."
                        )
                    else:
                        st.success(
                            "### 🟢 Clean Prompt Dispatched (<15ms)\n\n"
                            "Routine engineering query verified cleanly with zero policy violations. Upstream streaming initiated immediately."
                        )

            # 4. 4-Stage Visual Pipeline Walkthrough Card
            st.markdown("#### 🔬 Technical Inspection Pipeline")
            render_pipeline_walkthrough_card(active_incident, key_prefix="main_stage_walkthrough")

        else:
            st.info("No inspection events recorded yet. Click any preset in the left sidebar to begin!")

        st.markdown("---")

        # 5. Live Shadow AI Discovery Feed & Chronological Audit Log
        st.subheader("📊 Live Shadow AI Discovery Feed & Intervention Log")
        st.caption("Chronological stream of prompt requests across web interfaces, IDEs, terminal CLI agents, and backend services.")

        if not incidents:
            st.info("Audit stream is empty. Test a preset or inject a custom prompt from the sidebar.")
        else:
            for inc in reversed(incidents):
                inc_id = inc.get("incident_id")
                client_tag = inc.get("client_identity", {}).get("client_name", "Unknown")
                applied = inc.get("applied_action", "ALLOW")
                ast_i = inc.get("ast_analysis", {})
                jev_i = inc.get("jev_evaluation", {})
                score = jev_i.get("calibrated_urgency_score", 0.0)
                raw_p = inc.get("extracted_prompt_text", "")

                icon_map = {
                    "ALLOW": "🟢",
                    "SILENT_LOG": "📝",
                    "NUDGE": "⚠️",
                    "REDACT": "✂️",
                    "BLOCK": "🛑",
                }
                action_icon = icon_map.get(applied, "ℹ️")
                display_action = "WARNING" if applied == "NUDGE" else applied

                with st.expander(
                    f"{action_icon} [{display_action}] {client_tag} — Score: {score:.2f} | Incident `{inc_id}`",
                    expanded=False,
                ):
                    st.markdown(f"**Prompt Snippet:**  \n_{raw_p[:250]}..._")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Originating Client", client_tag)
                    m2.metric("AST Synthetic Fixture?", "Yes (Discounted)" if ast_i.get("is_synthetic_test_fixture") else "No")
                    m3.metric("Data Classification", jev_i.get("data_classification", "Clean"))
                    m4.metric("Calibrated Score", f"{score:.2f}")
                    st.caption(f"Reasoning: {jev_i.get('reasoning_summary', 'N/A')}")

    # ---------------------------------------------------------------------
    # TAB 2: DEDICATED UNIT ECONOMICS & FLEET MODELING
    # ---------------------------------------------------------------------
    with tab_economics:
        st.subheader("💰 Per-Simulation & Fleet Unit Economics Model")
        st.markdown(
            "Compare the compute infrastructure footprint of traditional multi-model Small Language Model (SLM) ensembles "
            "against lightweight single-pass **TypeSafe AI Jev System 1 scoring**."
        )

        tok_count = active_incident.get("token_count", 120) if active_incident else 120
        jev_cost_val = 0.000010
        slm_cost_val = 0.000500
        run_savings_val = slm_cost_val - jev_cost_val
        pct_savings = (run_savings_val / slm_cost_val) * 100

        ue_col1, ue_col2, ue_col3, ue_col4 = st.columns(4)
        ue_col1.metric("Active Prompt Size", f"{tok_count} tokens", help="Number of evaluated prompt tokens in active simulation")
        ue_col2.metric("Jev System 1 Compute", f"${jev_cost_val:.6f}", delta="ARM/x86 vCPU (<15ms)", delta_color="normal")
        ue_col3.metric("Traditional SLM Ensemble", f"${slm_cost_val:.6f}", delta="2-4 GPU Nodes (150-250ms)", delta_color="inverse")
        ue_col4.metric("Net Run Savings", f"${run_savings_val:.6f}", delta=f"{pct_savings:.1f}% Reduction", delta_color="normal")

        st.markdown("---")
        st.markdown("### 📈 Interactive Fleet Spend Extrapolation")

        monthly_reqs = st.slider(
            "Monthly Enterprise Prompt Inspections",
            min_value=1_000_000,
            max_value=50_000_000,
            value=20_000_000,
            step=1_000_000,
            format="%d requests",
            key="slider_monthly_requests",
        )

        monthly_slm_spend = (monthly_reqs * slm_cost_val) + 1800.0  # variable + multi-region GPU fixed
        monthly_jev_spend = (monthly_reqs * jev_cost_val) + 200.0   # variable + ARM vCPU fixed
        net_monthly_savings = monthly_slm_spend - monthly_jev_spend
        net_annual_savings = net_monthly_savings * 12
        fleet_pct_reduction = (net_monthly_savings / monthly_slm_spend) * 100

        fc1, fc2, fc3 = st.columns(3)
        fc1.metric(
            "Modeled Monthly SLM Spend",
            f"${monthly_slm_spend:,.0f} / mo",
            delta=f"${monthly_slm_spend * 12:,.0f} / yr (GPU Footprint)",
            delta_color="inverse",
        )
        fc2.metric(
            "Modeled Monthly Jev Spend",
            f"${monthly_jev_spend:,.0f} / mo",
            delta=f"${monthly_jev_spend * 12:,.0f} / yr (ARM Compute)",
            delta_color="normal",
        )
        fc3.metric(
            "Net Projected Savings",
            f"${net_annual_savings:,.0f} / yr",
            delta=f"{fleet_pct_reduction:.1f}% Cost Reduction",
            delta_color="normal",
        )

        with st.container(border=True):
            st.markdown("#### ⚙️ Modeling Methodology & Cloud Compute Assumptions")
            st.markdown("""
            **Cost Modeling Formula:**  
            $$\\text{Total Monthly Cost} = [N_{\\text{requests}} \\times \\text{Tokens}_{\\text{req}} \\times \\text{Cost}_{\\text{Inference}}] + \\text{Infra Fixed Cost} + \\text{Network Egress}$$

            * **Modeled SLM Pipeline Baseline (Estimation):**
              * Assumes 2–4 specialized models running across redundant GPU instances (e.g. 2× AWS `g5.xlarge` @ ~$1.00–$1.50/hr each per region for high availability).
              * Estimated fixed baseline: **$1,500 – $2,200/month** per active region, plus autoscaling bursts during peak hours.
            * **Modeled Jev System 1 Architecture (Estimation):**
              * Runs on lightweight general-purpose compute (e.g. AWS `c7g.xlarge` ARM vCPU @ ~$0.15–$0.25/hr) or edge-evaluated directly in API gateway sidecars (Envoy / Cloudflare Workers).
              * Estimated fixed baseline: **$150 – $350/month**.
            * **Latency ROI:**
              * Beyond compute costs, Jev System 1 executes in **<15ms**, preventing the 150ms–250ms latency penalties that degrade developer Time-To-First-Token (TTFT) in IDEs.

            *Note on Methodology: Figures represent engineering estimates based on public cloud compute benchmarks. They do not reflect confidential commercial pricing or proprietary infrastructure from specific commercial vendors.*
            """)

    # ---------------------------------------------------------------------
    # TAB 3: DEDICATED HELP & OPERATIONAL GUIDANCE
    # ---------------------------------------------------------------------
    with tab_guide:
        st.subheader("📖 Enterprise AIDR & Jev Gatekeeper Operational Guide")

        g_col1, g_col2 = st.columns(2, gap="medium")
        with g_col1:
            with st.container(border=True):
                st.markdown("#### 1. Why Data-in-Motion AI Detection & Response (AIDR)?")
                st.markdown("""
                Traditional enterprise AI security relies heavily on post-hoc SaaS audits or local browser extensions.
                However, extensions leave critical blind spots:
                * **Developer IDEs & CLI Agents**: Cursor, VS Code Copilot, and Google Antigravity CLI communicate directly over HTTP.
                * **Headless CI/CD & Microservices**: Automated test runners and backend microservices bypass browser agents entirely.
                * **Latency Frustration**: Routing prompts to multi-model SLM backends (1.5s–2.5s) causes visible input freeze.

                The **Jev Gatekeeper** intercepts data-in-motion at the network proxy, browser extension, and Model Context Protocol (MCP) boundaries.
                """)

            with st.container(border=True):
                st.markdown("#### 2. Interception Boundary: Pre-Flight vs Keystroke Autocomplete")
                st.markdown("""
                * **The Keystroke Trap**: Checking prompts on every keystroke during typing (like autocomplete) causes technical and financial bottlenecks:
                  * A single 100-word prompt generates 500+ API calls.
                  * Creates massive rate limiting, token parsing costs, and UI jitter.
                * **The Pre-Flight Boundary**: The gatekeeper is engaged **once when the user submits the prompt** (clicks 'Send', 'Generate', or hits Enter).
                * **Sub-15ms Speed**: Because Jev evaluates in under 15ms, the safety check is completed imperceptibly before the target LLM streams its first token.
                """)

        with g_col2:
            with st.container(border=True):
                st.markdown("#### 3. The 4-Stage Pipeline Walkthrough")
                st.markdown("""
                1. **Stage 1 — Client Intake & Fingerprinting**: Intercepts prompts, detects originating client morphology (Cursor, Copilot, Claude Desktop, Antigravity CLI, curl), and measures token density.
                2. **Stage 2 — AST Context Parser**: Analyzes syntax using Python's native `ast`. Test functions and synthetic mocks (`pytest.fixture`, `unittest.mock`) receive a **95% risk discount** to eliminate false alarms. Plain natural language exits in **<0.05ms** (`is_code=False`).
                3. **Stage 3 — Jev System 1 Core**: Single-pass feedforward matrix evaluation (<15ms) generating calibrated probability distributions across `Noul`, `Choice`, and `Score`.
                4. **Stage 4 — Enforcement & Telemetry**: Applies deterministic policy routing (**`ALLOW`**, **`WARNING`**, **`REDACT`**, **`BLOCK`** with HTTP 403) and logs real-time economic cost savings.
                """)

            with st.container(border=True):
                st.markdown("#### 4. Policy Thresholds & Enforcement Actions")
                st.markdown("""
                * **`ALLOW` (Score $\\le 0.30$)**: Clean code or routine query; forwarded immediately to upstream LLM.
                * **`SILENT_LOG` (0.30 < Score < 0.80)**: Low-risk terminology logged to audit feed without alerting the user.
                * **`WARNING` (Score $\\ge 0.80$)**: Soft-gating policy alert. Displays confirmation warning to user (e.g. customer PII review).
                * **`REDACT`**: Sensitive identifiers replaced with tokens prior to dispatch.
                * **`BLOCK` (Score $\\ge 0.92$)**: High-risk credential or exfiltration detected; connection terminated with HTTP 403 Forbidden.
                """)

