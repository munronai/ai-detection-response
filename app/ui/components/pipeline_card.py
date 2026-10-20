"""4-Stage Visual Pipeline Walkthrough Inspector Card."""

from typing import Any, Dict
import streamlit as st


ACTION_BANNERS = {
    "ALLOW": (
        "✅ ALLOWED → Direct Forward to Upstream LLM Target",
        "success",
        "Payload satisfies enterprise acceptable-use policy. Clean code or chat passed without latency impact.",
    ),
    "SILENT_LOG": (
        "📝 SILENT LOG → Allowed & Appended to Audit Stream",
        "info",
        "Low-risk internal terminology or non-sensitive source code logged for compliance without alerting the user.",
    ),
    "NUDGE": (
        "⚠️ POLICY WARNING → Interactive Policy Warning Surface",
        "warning",
        "Detected unmasked customer PII or sensitive project reference. Allowed with inline compliance warning dialog.",
    ),
    "REDACT": (
        "✂️ REDACTED → Sensitive Tokens Masked Before LLM Forwarding",
        "warning",
        "High-entropy credentials or proprietary strings redacted from prompt payload prior to upstream dispatch.",
    ),
    "BLOCK": (
        "🛑 BLOCKED → Traffic Terminated with HTTP 403 Forbidden",
        "error",
        "Critical security violation detected: Production secret, unmasked credential, or adversarial exfiltration.",
    ),
}


def render_pipeline_walkthrough_card(record: Dict[str, Any], key_prefix: str = "walkthrough"):
    """
    Renders the sequential 4-Stage visual card showing what happened at each step
    and why each stage exists in the AIDR pipeline.
    """
    incident_id = record.get("incident_id", "inc_unknown")
    client_id = record.get("client_identity", {})
    ast_res = record.get("ast_analysis", {})
    jev_eval = record.get("jev_evaluation", {})
    action = record.get("applied_action", "ALLOW")

    title_text, banner_style, desc_text = ACTION_BANNERS.get(
        action,
        (f"Verdict: {action}", "info", "Evaluated by Jev Gatekeeper."),
    )

    # 1. Top Outcome Banner
    if banner_style == "success":
        st.success(f"### {title_text}\n{desc_text}")
    elif banner_style == "warning":
        st.warning(f"### {title_text}\n{desc_text}")
    elif banner_style == "error":
        st.error(f"### {title_text}\n{desc_text}")
    else:
        st.info(f"### {title_text}\n{desc_text}")

    st.markdown("#### 🔄 Step-by-Step Pipeline Walkthrough (Sequence of Inspection)")

    c1, c2, c3, c4 = st.columns(4, gap="medium")

    # -------------------------------------------------------------
    # STAGE 1: INTAKE & CLIENT FINGERPRINT
    # -------------------------------------------------------------
    with c1:
        with st.container(border=True):
            st.markdown("##### 1️⃣ Stage 1: Intake & Client")
            st.caption("💡 **Why:** Coverage for BYOD, IDEs, and CLI agents beyond browser extensions.")

            c_name = client_id.get("client_name", "Unknown")
            c_type = client_id.get("client_type", "Generic")
            det_via = client_id.get("detected_via", "Schema")

            st.markdown(
                f"- **Client:** `{c_name}`\n"
                f"- **Detected Via:** `{det_via}`\n"
                f"- **Tokens:** `{record.get('token_count', 0)}` tokens\n"
                f"- **Target:** `{record.get('target_provider', 'OPENAI')}`"
            )

            prompt_snippet = record.get("extracted_prompt_text", "")
            if len(prompt_snippet) > 160:
                prompt_snippet = prompt_snippet[:160] + "..."
            st.markdown(f"> _{prompt_snippet}_")

    # -------------------------------------------------------------
    # STAGE 2: AST & SYNTAX CONTEXT PARSER
    # -------------------------------------------------------------
    with c2:
        with st.container(border=True):
            st.markdown("##### 2️⃣ Stage 2: AST Context Parser")
            st.caption("💡 **Why:** Eliminates false alarms on mock data, test fixtures & dummy tokens.")

            has_code = ast_res.get("has_code", False)
            is_mock = ast_res.get("is_synthetic_test_fixture", False)
            penalty = float(ast_res.get("confidence_penalty", 1.0))
            test_fns = ast_res.get("test_function_count", 0)
            frameworks = ast_res.get("mock_frameworks", [])

            if is_mock:
                st.success("🟢 **SYNTHETIC TEST FIXTURE**")
                st.markdown(
                    f"- **Scope:** `{test_fns}` unit test function(s)\n"
                    f"- **Frameworks:** `{', '.join(frameworks) or 'unittest/mock'}`\n"
                    f"- **AST Risk Multiplier:** **`0.05×` (95% Discount)**"
                )
                fixtures = ast_res.get("fixtures", [])
                if fixtures:
                    st.caption(f"Detected {len(fixtures)} synthetic variable(s):")
                    for f in fixtures[:2]:
                        st.code(f"{f.get('identifier')}: {f.get('value_snippet')}", language="python")
                st.info("📐 **AST Discount Formula:**  \n`Calibrated = Raw × 0.05`")
            elif has_code:
                st.info("💻 **Production / Application Code**")
                st.markdown(
                    f"- **Parsed:** Python AST (`ast_parsable=True`)\n"
                    f"- **Scope:** Non-test application logic\n"
                    f"- **AST Risk Discount:** `None (1.00×)`"
                )
            else:
                st.caption("📝 Conversational text (no code syntax detected).")
                st.markdown("- **Language:** Natural Language\n- **AST Discount:** `1.00×`")

    # -------------------------------------------------------------
    # STAGE 3: JEV SYSTEM 1 CORE EVALUATION
    # -------------------------------------------------------------
    with c3:
        with st.container(border=True):
            st.markdown("##### 3️⃣ Stage 3: Jev System 1 Core")
            st.caption("💡 **Why:** Single-pass feedforward matrix scoring in <15ms without SLM lag.")

            engine_tag = jev_eval.get("engine_used", "JEV_SIMULATED")
            mock_p = float(jev_eval.get("is_synthetic_or_mock_prob", 0.0))
            data_class = jev_eval.get("data_classification", "Clean_Code_Or_Chat")
            raw_urg = float(jev_eval.get("raw_urgency_score", 0.0))
            calib_urg = float(jev_eval.get("calibrated_urgency_score", 0.0))
            eval_time = float(jev_eval.get("eval_time_ms", 12.0))

            engine_badge = "🟢 LIVE API" if "LIVE" in engine_tag else "🧪 SIMULATED"
            st.markdown(f"**Engine:** `{engine_badge}` ({eval_time:.1f}ms)")

            st.markdown(
                f"- **Mock Prob (Noul):** `{mock_p:.0%}`\n"
                f"- **Data Class (Choice):** `{data_class}`\n"
                f"- **Raw Urgency (Score):** `{raw_urg:.2f}`\n"
                f"- **Calibrated Urgency:** **`{calib_urg:.2f}`**"
            )

            if is_mock and raw_urg > 0.5:
                st.success(
                    f"✅ **False Alarm Dropped!**  \n"
                    f"`{raw_urg:.2f} × 0.05 = {calib_urg:.2f}` $\\rightarrow$ **`ALLOW`**"
                )

    # -------------------------------------------------------------
    # STAGE 4: ENFORCEMENT & ACTION
    # -------------------------------------------------------------
    with c4:
        with st.container(border=True):
            st.markdown("##### 4️⃣ Stage 4: Enforcement & Action")
            st.caption("💡 **Why:** Deterministic policy routing with continuous economic tracking.")

            st.markdown(
                f"- **Policy Verdict:** **`{action}`**\n"
                f"- **Total Latency:** `{record.get('total_pipeline_latency_ms', 0):.1f}ms`\n"
                f"- **Jev CPU Cost:** `$0.000010`\n"
                f"- **SLM GPU Cost:** `$0.000500`\n"
                f"- **Net Run Savings:** **`98.0%` ($0.000490)**"
            )

            if action == "ALLOW":
                st.success("✅ **Forwarded to Target LLM**  \nTTFT latency unaffected.")
            elif action == "NUDGE":
                st.warning("⚠️ **Policy Warning Triggered**  \nUser alerted with compliance confirmation.")
            elif action == "BLOCK":
                st.error("🛑 **Egress Blocked!**  \nPayload terminated at edge.")
            elif action == "REDACT":
                st.warning("✂️ **Masked Credentials**  \nTokens replaced with placeholders.")

