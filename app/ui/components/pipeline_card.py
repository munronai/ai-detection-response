"""4-Stage Visual Pipeline Walkthrough Inspector Card."""

from typing import Any, Dict
import altair as alt
import pandas as pd
import streamlit as st

from app.ui.components.policy_helper import classify_incident_violation


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
        "Detected sensitive data exceeding corporate policy threshold. Allowed with inline compliance warning dialog.",
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

    violation = classify_incident_violation(record)

    if action == "NUDGE":
        title_text = f"⚠️ POLICY WARNING → {violation.risk_title}"
        banner_style = "warning"
        desc_text = violation.banner_nudge_desc
    elif action == "BLOCK":
        title_text = f"🛑 BLOCKED → {violation.risk_title} Terminated (HTTP 403)"
        banner_style = "error"
        desc_text = violation.banner_block_desc
    else:
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
            st.caption("💡 **Why:** Single-pass feedforward matrix scoring without multi-model SLM lag.")

            engine_tag = jev_eval.get("engine_used", "JEV_SIMULATED")
            mock_p = float(jev_eval.get("is_synthetic_or_mock_prob", 0.0))
            data_class = jev_eval.get("data_classification", "Clean_Code_Or_Chat")
            raw_urg = float(jev_eval.get("raw_urgency_score", 0.0))
            calib_urg = float(jev_eval.get("calibrated_urgency_score", 0.0))
            eval_time = float(jev_eval.get("eval_time_ms", 12.0))
            choice_probs = jev_eval.get("classification_probabilities", {})
            raw_api_resp = jev_eval.get("raw_api_response")
            applied_margin = float(jev_eval.get("ambiguity_margin_applied", 0.15))
            is_ambiguous = bool(jev_eval.get("is_ambiguous_decision", False))
            obs_margin = float(jev_eval.get("decision_margin", 1.0))

            engine_badge = "🟢 LIVE API" if "LIVE" in engine_tag else "🧪 SIMULATED"
            st.markdown(f"**Engine:** `{engine_badge}` ({eval_time:.1f}ms)")
            if eval_time > 100:
                st.caption("🌐 Cloud WAN (HTTPS transit + TLS)")
            else:
                st.caption("⚡ Co-located sidecar / in-VPC forward pass")

            st.markdown(
                f"- **Mock Prob (Noul):** `{mock_p:.0%}`",
                help=(
                    "**Question (`is_synthetic_or_mock` - Noul / Binary Probability):**\n\n"
                    "*\"Does candidate_payload contain exclusively synthetic test data, mock fixtures, "
                    "or dummy code within a unit testing scope?\"*\n\n"
                    "• **True criteria:** Content is mock data, synthetic fixtures, test assertions, or sample documentation code.\n\n"
                    "• **False criteria:** Content contains real production credentials, real customer PII, or proprietary business logic."
                ),
            )

            st.markdown(
                f"- **Data Class (Choice):** `{data_class}`",
                help=(
                    "**Question (`data_classification` - Choice / Categorization):**\n\n"
                    "*\"Which data classification best describes any sensitive content within candidate_payload?\"*\n\n"
                    "• **Clean_Code_Or_Chat:** Benign general chat, public algorithms, formatting requests\n"
                    "• **Synthetic_Test_Fixture:** Synthetic identifiers, mock credit cards, test fixtures\n"
                    "• **Customer_PII:** Real consumer PII such as SSN, personal phone, address, banking details\n"
                    "• **Live_API_Secret:** Production API keys, cloud root credentials, private SSH keys\n"
                    "• **Proprietary_Core_IP:** Core algorithmic proprietary IP, unreleased financial reports, jailbreaks"
                ),
            )

            raw_score_val = float(jev_eval.get("raw_score", 0.0))
            if raw_score_val == 0.0 and raw_urg > 0:
                raw_score_val = round(raw_urg * 4, 2)

            st.markdown(
                f"- **Raw Urgency (Score):** `{raw_score_val:.2f} / 4.0` *(Normalized: `{raw_urg:.2f}`)*",
                help=(
                    "**Question (`intervention_urgency` - Score 0 to 4):**\n\n"
                    "*\"How severe is the policy violation and how urgently should the gatekeeper intervene "
                    "given the data classification and AST context?\"*\n\n"
                    f"**Raw Score Returned by Jev:** `{raw_score_val:.2f}` out of 4.0\n"
                    f"**Normalized Score:** `{raw_urg:.2f}` (calculated as `raw_score ÷ 4.0` for policy threshold comparisons)\n\n"
                    "• **Level 0 (0.00):** Nominal risk → `ALLOW`\n"
                    "• **Level 1 (1.00):** Low-risk internal context → `SILENT_LOG`\n"
                    "• **Level 2 (2.00):** Ambiguous sensitive data → `WARNING (Inline Nudge)`\n"
                    "• **Level 3 (3.00):** Sensitive Customer PII / Confidential IP → `WARNING (Policy DP-104)`\n"
                    "• **Level 4 (4.00):** Critical production secret / exfiltration → `BLOCK (HTTP 403)`"
                ),
            )

            st.markdown(
                f"- **Calibrated Urgency:** **`{calib_urg:.2f}`**",
                help=(
                    "**Calibration Formula:**\n\n"
                    "`Calibrated Urgency = Raw Urgency × AST Confidence Penalty`\n\n"
                    "• **Synthetic Test Fixtures:** 0.05× multiplier (95% false-positive discount applied by AST)\n"
                    "• **Production Code / Natural Language:** 1.00× multiplier (no discount applied)"
                ),
            )

            if is_mock and raw_urg > 0.5:
                st.success(
                    f"✅ **False Alarm Dropped!**  \n"
                    f"`{raw_urg:.2f} × 0.05 = {calib_urg:.2f}` $\\rightarrow$ **`ALLOW`**"
                )

            st.markdown(
                "<div style='margin-top: 10px; padding: 6px 10px; background: rgba(59, 130, 246, 0.08); border-left: 3px solid #3b82f6; border-radius: 4px; font-size: 0.80rem;'>"
                "🔗 <strong>Connected to Stage 3 Deep-Dive Below:</strong> Detailed probabilities chart, audit questions & raw JSON ↓"
                "</div>",
                unsafe_allow_html=True,
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
                if is_ambiguous:
                    st.warning(f"⚠️ **Ambiguity Escalation ({obs_margin:.0%} $\\le$ {applied_margin:.0%})**  \nUser alerted: {violation.risk_title}")
                else:
                    st.warning(f"⚠️ **{violation.policy_code} Warning Triggered**  \nUser alerted: {violation.risk_title}")
            elif action == "BLOCK":
                st.error(f"🛑 **{violation.policy_code} Blocked!**  \nPayload terminated at edge.")
            elif action == "REDACT":
                st.warning("✂️ **Masked Credentials**  \nTokens replaced with placeholders.")

    # -------------------------------------------------------------
    # SEPARATE COLLAPSIBLE CARD (BELOW WALKTHROUGH): STAGE 3 DEEP-DIVE
    # -------------------------------------------------------------
    st.markdown("<div id='stage-3-deep-dive'></div>", unsafe_allow_html=True)
    with st.expander(
        "🔬 3️⃣ Stage 3 Deep-Dive: Probabilities Chart, Audit Questions & Raw Jev JSON",
        expanded=False,
    ):
        st.caption(
            "Connected to **Stage 3 (Jev System 1 Core)**: Inspect the complete multiclass probability distribution, "
            "the evaluation questions sent to Jev, and the raw JSON response payload."
        )

        tab_chart, tab_questions, tab_json = st.tabs([
            "📊 Classification Distribution Chart",
            "❓ Audit Questions Sent to Jev",
            "📄 Raw Jev JSON Response",
        ])

        # 1. Classification Distribution Chart & Ambiguity Analysis
        with tab_chart:
            if choice_probs:
                sorted_choices = sorted(choice_probs.items(), key=lambda x: x[1], reverse=True)

                # Highlight close decision margin (e.g. 52% vs 44%)
                if len(sorted_choices) >= 2:
                    top1_name, top1_prob = sorted_choices[0]
                    top2_name, top2_prob = sorted_choices[1]
                    margin = top1_prob - top2_prob
                    if margin <= applied_margin and top2_prob >= 0.15:
                        st.warning(
                            f"⚖️ **Close Decision Margin ({margin:.0%} $\\le$ {applied_margin:.0%} Slider Threshold):**  \n"
                            f"**`{top1_name}`** (`{top1_prob:.0%}`) vs **`{top2_name}`** (`{top2_prob:.0%}`)  \n"
                            f"The policy engine evaluated this split decision against your configured `{applied_margin:.0%}` margin slider. "
                            "Caution was elevated to prevent false negatives on boundary payloads."
                        )

                chart_data = pd.DataFrame(
                    [{"Classification": k.replace("_", " "), "Probability": v} for k, v in sorted_choices]
                )

                # Altair horizontal bar chart: pinned to x=0.0 with comfortable vertical height
                bars = (
                    alt.Chart(chart_data)
                    .mark_bar(cornerRadiusTopRight=5, cornerRadiusBottomRight=5, height=22)
                    .encode(
                        x=alt.X(
                            "Probability:Q",
                            scale=alt.Scale(domain=[0.0, 1.0]),
                            axis=alt.Axis(
                                format=".0%",
                                title="Probability (Scale 0% to 100%)",
                                tickCount=5,
                            ),
                        ),
                        y=alt.Y(
                            "Classification:N",
                            sort=None,
                            axis=alt.Axis(title=None, labelFontSize=11),
                        ),
                        color=alt.condition(
                            alt.datum.Probability == chart_data["Probability"].max(),
                            alt.value("#3b82f6"),
                            alt.value("#94a3b8"),
                        ),
                        tooltip=[
                            alt.Tooltip("Classification:N", title="Choice"),
                            alt.Tooltip("Probability:Q", format=".1%", title="Probability"),
                        ],
                    )
                )

                text = (
                    alt.Chart(chart_data)
                    .mark_text(align="left", dx=6, fontSize=11, fontWeight="bold")
                    .encode(
                        x="Probability:Q",
                        y="Classification:N",
                        text=alt.Text("Probability:Q", format=".1%"),
                    )
                )

                layered_chart = (bars + text).properties(height=260)
                st.altair_chart(layered_chart, use_container_width=True)

                st.caption("Exact calibrated distribution across options:")
                col_probs = st.columns(len(sorted_choices))
                for idx, (c_name, c_prob) in enumerate(sorted_choices):
                    with col_probs[idx % len(col_probs)]:
                        st.metric(label=c_name.replace("_", " "), value=f"{c_prob:.1%}")
            else:
                st.info("No multiclass probability distribution available for this evaluation.")

        # 2. Questions sent to Jev
        with tab_questions:
            st.markdown(
                "##### 1. `is_synthetic_or_mock` (Type: `noul`)\n"
                "*\"Does candidate_payload contain exclusively synthetic test data, mock fixtures, or dummy code within a unit testing scope?\"*\n\n"
                "**Criteria:**\n"
                "- **`true`:** Content is mock data, synthetic fixtures, test assertions, or sample documentation code (e.g. `...EXAMPLE`).\n"
                "- **`false`:** Content contains real production credentials, real customer PII, or proprietary business logic.\n\n"
                "##### 2. `data_classification` (Type: `choice`)\n"
                "*\"Which data classification best describes any sensitive content within candidate_payload?\"*\n\n"
                "**Candidate Categories:**\n"
                "- **`Clean_Code_Or_Chat`:** Benign general chat, public algorithms, formatting requests\n"
                "- **`Synthetic_Test_Fixture`:** Synthetic identifiers, mock credit cards, test fixtures\n"
                "- **`Customer_PII`:** Real consumer PII such as SSN, personal phone, address, banking details\n"
                "- **`Live_API_Secret`:** Production API keys, cloud root credentials, private SSH keys\n"
                "- **`Proprietary_Core_IP`:** Core algorithmic proprietary IP, unreleased financial reports, jailbreaks\n\n"
                "##### 3. `intervention_urgency` (Type: `score` 0 to 4)\n"
                "*\"How severe is the policy violation and how urgently should the gatekeeper intervene given the data classification and AST context?\"*\n\n"
                "**Scoring Rubric (Legend):**\n"
                "- **Level 0 (0.00):** Irrelevant prompt or synthetic test code; nominal risk requiring zero logging or action\n"
                "- **Level 1 (1.00):** Low-risk non-sensitive internal context; allow through and silently log in audit stream\n"
                "- **Level 2 (2.00):** Ambiguous sensitive data or internal documentation; surface inline user nudge\n"
                "- **Level 3 (3.00):** Sensitive customer PII or confidential IP; redact sensitive spans before forwarding\n"
                "- **Level 4 (4.00):** Critical production secret, live cloud credential, or malicious exfiltration attempt; immediately block traffic"
            )

        # 3. Raw Jev System 1 JSON Response
        with tab_json:
            if raw_api_resp:
                st.caption(f"Raw HTTP response payload directly from `{engine_tag}`:")
                st.json(raw_api_resp)
            else:
                st.caption(f"Evaluated response payload (`{engine_tag}`):")
                st.json({
                    "engine": engine_tag,
                    "answers": {
                        "is_synthetic_or_mock": {
                            "noul": mock_p,
                            "type": "noul",
                        },
                        "data_classification": {
                            "choice": data_class,
                            "probabilities": choice_probs,
                            "type": "choice",
                        },
                        "intervention_urgency": {
                            "score": round(raw_urg * 4, 2),
                            "normalized_score": raw_urg,
                            "type": "score",
                        },
                    },
                    "calibrated_urgency": calib_urg,
                    "action_taken": action,
                    "eval_time_ms": eval_time,
                })

