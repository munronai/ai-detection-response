"""Landing Page & Guided Walkthrough Overview."""

import streamlit as st


def render_landing_page(
    page_dashboard,
    page_insights,
    page_mcp,
    page_guides,
    page_inspector,
):
    """Renders the executive summary, problem framing, and guided walkthrough."""
    st.title("🛡️ Jev Gatekeeper & AST Context Parser for Enterprise AIDR")
    st.subheader(
        "Challenging Traditional Multi-Model SLM Pipelines with System 1 Calibration & AST False-Positive Elimination"
    )

    st.markdown("""
        Welcome to the **AI Detection & Response (AIDR) Simulation Sandbox**.
        This interactive platform demonstrates how enterprises can protect against AI prompt data loss,
        credential leakage, and intellectual property exfiltration—**without** the latency penalties,
        false-positive friction, and GPU infrastructure costs of traditional Small Language Model (SLM) ensembles.
    """)

    # Top CTA Cards
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### 🎛️ Launch the Live AIDR Control Deck")
            st.write(
                "Test the 5 Golden Presets, inject custom code snippets, toggle between Simulated Jev "
                "and Live TypeSafe AI API, and inspect the 4-stage pipeline in real time."
            )
            st.page_link(page_dashboard, label="Open Live AIDR Dashboard →", icon="🚀", use_container_width=True)

    with col2:
        with st.container(border=True):
            st.markdown("### 📐 Research, Product Decisions & Unit Economics")
            st.write(
                "Read the step-by-step research on enterprise AIDR friction, our core product decisions, "
                "and explore the transparent unit economics calculator with adjustable cloud compute assumptions."
            )
            st.page_link(page_insights, label="Explore Product Insights & Economics →", icon="📐", use_container_width=True)

    st.divider()

    # The 4-Stage Pipeline Walkthrough
    st.markdown("## ⚙️ How the 4-Stage Gatekeeper Pipeline Works")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        with st.container(border=True):
            st.markdown("#### 1️⃣ Intake & Fingerprint")
            st.caption("Omnichannel Coverage")
            st.write(
                "Attributes originating traffic across Cursor, GitHub Copilot, Claude Desktop, "
                "Antigravity CLI, or raw terminal curl using JA4, User-Agent, and virtual route profiles "
                "(and connects seamlessly to Chrome/Edge browser extensions & SWG taps for Copilot 365 / ChatGPT Web)."
            )
    with s2:
        with st.container(border=True):
            st.markdown("#### 2️⃣ AST Context Parser")
            st.caption("False-Positive Elimination")
            st.write(
                "Inspects syntax trees for unit test functions, mock imports (`unittest.mock`, `pytest`), "
                "and synthetic variable patterns, applying a 95% risk discount."
            )
    with s3:
        with st.container(border=True):
            st.markdown("#### 3️⃣ Jev System 1 Core")
            st.caption("TypeSafe AI (<25ms local, $0.00001)")
            st.write(
                "Evaluates raw representations in a single feedforward pass using calibrated "
                "`Noul` (mock prob), `Choice` (data class), and `Score` (urgency)."
            )
    with s4:
        with st.container(border=True):
            st.markdown("#### 4️⃣ Policy Enforcement")
            st.caption("Deterministic Action Matrix")
            st.write(
                "Applies deterministic policy actions: `ALLOW`, `SILENT_LOG`, `WARNING` (soft gate), `REDACT`, "
                "or `BLOCK` with `HTTP 403 Forbidden`."
            )

    st.divider()

    # 5 Presets Guide
    st.markdown("## 🧪 5 Golden Presets Quick Reference")
    st.markdown("""
1. **1️⃣ Synthetic Test Fixture**: Demonstrates AST eliminating a false positive on mock billing code in Cursor IDE.
2. **2️⃣ Routine Developer Query**: Clean sorting query passed with sub-25ms latency in VS Code Copilot.
3. **3️⃣ Ambiguous Customer PII**: Unmasked DOB/address in Copilot 365 surfacing an inline policy warning dialog.
4. **4️⃣ Production AWS Cloud Secret**: Live cloud credential terminated with HTTP 403 at perimeter.
5. **5️⃣ Base64 Private Key Exfiltration**: Obfuscated payload caught by Jev exfiltration scoring in CLI agent.
""")

    st.page_link(page_dashboard, label="Test These Presets in the Dashboard →", icon="🎛️", use_container_width=True)

    st.divider()

    # External MCP Integrations Section (Placed at the bottom of the overview page)
    st.markdown("## 🤖 External Model Context Protocol (MCP) Integrations")
    st.caption("Interact with the live AIDR Gatekeeper using your preferred client or developer visualizer:")

    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        with st.container(border=True):
            st.markdown("#### 🖥️ Claude & Cursor (Option 1)")
            st.write(
                "Configure Claude Desktop (via `mcp-remote`) or Cursor IDE to query live prompt risk "
                "and approve policy overrides over `/mcp/sse`."
            )
            st.page_link(page_guides, label="Open Claude & Cursor Guide →", icon="🖥️", use_container_width=True)

    with m_col2:
        with st.container(border=True):
            st.markdown("#### 🤖 In-Browser MCP Console (Option 2)")
            st.write(
                "Test live SSE handshakes, execute JSON-RPC 2.0 tool calls, and read resources directly "
                "inside Streamlit without external software."
            )
            st.page_link(page_mcp, label="Open Browser MCP Console →", icon="🤖", use_container_width=True)

    with m_col3:
        with st.container(border=True):
            st.markdown("#### 🔬 Official MCP Inspector (Option 3)")
            st.write(
                "Run the official zero-install `npx` developer visualizer to debug parameter schemas, "
                "ping SSE connection health, and view raw payloads."
            )
            st.page_link(page_inspector, label="Open MCP Inspector Guide →", icon="🔬", use_container_width=True)
