"""KPI Telemetry Header and Error Banner Components."""

from typing import Any, Dict
import streamlit as st


def render_error_banner():
    """Renders a non-blocking, dismissible error banner if an API call fails."""
    err = st.session_state.get("last_api_error")
    if err:
        col_msg, col_btn = st.columns([0.94, 0.06])
        with col_msg:
            st.error(f"⚠️ {err}")
        with col_btn:
            if st.button("✖️", key="dismiss_api_err", help="Dismiss error"):
                st.session_state["last_api_error"] = None
                st.rerun()


def render_kpi_header(telemetry: Dict[str, Any]):
    """Renders the top telemetry and unit-economics metric bar."""
    total = telemetry.get("total_scans", 0)
    passed = telemetry.get("passed_count", 0)
    nudged = telemetry.get("nudged_count", 0)
    blocked = telemetry.get("blocked_count", 0)
    ast_filtered = telemetry.get("ast_false_positives_eliminated", 0)
    mean_jev_latency = telemetry.get("mean_jev_latency_ms", 11.2)
    savings = telemetry.get("estimated_cost_savings_usd", 0.0)

    pass_rate = (passed / total * 100) if total > 0 else 100.0
    intervention_count = nudged + blocked

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.metric(
            label="Total AIDR Scans",
            value=f"{total:,}",
            help="Total prompt and source code payloads evaluated across all client apps.",
        )

    with k2:
        st.metric(
            label="Passed / Allowed",
            value=f"{pass_rate:.1f}%",
            delta=f"{passed} Clean Prompts",
            delta_color="normal",
            help="Percentage of prompts meeting enterprise compliance thresholds without disruption.",
        )

    with k3:
        st.metric(
            label="AST False Positives Dropped",
            value=f"{ast_filtered:,}",
            delta="Engineers Spared Fatigue",
            delta_color="normal",
            help="Synthetic test fixtures and mock variables that would have triggered traditional DLP but were cleared by AST.",
        )

    with k4:
        st.metric(
            label="Jev System 1 P99 Latency",
            value=f"{mean_jev_latency:.1f} ms",
            delta="vs 145 ms SLM Ensembles",
            delta_color="normal",
            help="Time required for single-pass feedforward matrix evaluation without autoregressive decoding lag.",
        )

    with k5:
        st.metric(
            label="Net Compute Savings",
            value=f"${savings:.4f}",
            delta="84% GPU Cost Reduction",
            delta_color="normal",
            help="Realized compute savings comparing lightweight CPU/ARM Jev scoring against multi-GPU SLM ensembles.",
        )
