"""Technical Architecture, Research Rationale & Estimated Unit Economics View."""

from typing import Any, Optional
import streamlit as st


def render_product_insights_view(
    page_dashboard: Optional[Any] = None,
    page_home: Optional[Any] = None,
    page_mcp: Optional[Any] = None,
):
    """
    Renders the step-by-step research rationale, product design decisions,
    and transparently estimated unit economics cost calculator.
    """
    st.title("📐 Product Insights: Research, Architecture & Modeled Economics")
    st.subheader("A Step-by-Step Rationale: Why We Built This Sandbox and How AST + Jev Solves Enterprise AIDR Friction")

    # =========================================================================
    # METHODOLOGICAL NOTICE & ESTIMATION SCOPE DISCLAIMER
    # =========================================================================
    st.info(
        "ℹ️ **Methodological Context & Estimation Scope:**  \n"
        "The infrastructure figures, cost comparisons, and latency benchmarks presented on this page are "
        "**engineering estimations based on standard public cloud compute benchmarks** (e.g. AWS EC2 on-demand pricing for "
        "dedicated GPU instances vs. general-purpose ARM vCPU sidecars).  \n\n"
        "**They do NOT represent actual internal compute costs, proprietary production telemetry, or commercial contract pricing "
        "of specific commercial vendors.** Rather, this model demonstrates the structural architectural "
        "trade-offs between hosting multi-model Small Language Model (SLM) ensembles versus single-pass System 1 matrix evaluation."
    )

    st.divider()

    # =========================================================================
    # STEP 1: THE RESEARCH — OBSERVED OPERATIONAL FRICTION IN ENTERPRISE AIDR
    # =========================================================================
    st.markdown("## 🔍 Step 1: The Research — Observed Friction in Enterprise AIDR")
    st.markdown(
        "Organizations deploying first-generation data-in-motion AI Detection and Response (AIDR / AISPM) platforms "
        "frequently report four architectural and operational friction points:"
    )

    f1, f2 = st.columns(2, gap="medium")

    with f1:
        with st.container(border=True):
            st.markdown("#### 1. Endpoint & Browser Extension Coverage Gaps")
            st.markdown(
                "Most enterprise data-loss prevention solutions rely heavily on managed browser extensions (Chrome/Edge via Intune/Jamf) "
                "to inspect prompts on web interfaces like ChatGPT Web or Microsoft 365 Copilot. While managed browser extensions are a vital "
                "channel for non-technical knowledge workers, traditional architectures create two major operational gaps:\n"
                "- **Developer & Backend Blind Spots**: Local browser extensions cannot intercept terminal CLI agents (e.g. Google Antigravity CLI, aider), "
                "IDE autocompletions (Cursor, VS Code Copilot), headless CI/CD test runners, or microservices making direct LLM API calls.\n"
                "- **Inline Latency Penalties in Web Browsers**: When extensions route web prompts to traditional multi-model SLM backends (taking 1.5s–2.5s), "
                "knowledge workers experience typing lag or submission freezing in Copilot 365, prompting employees to seek unmonitored workarounds."
            )

        with st.container(border=True):
            st.markdown("#### 2. The Context Boundary Trap in Engineering Code")
            st.markdown(
                "While language models excel at natural language intent, they struggle with specialized, high-entropy enterprise source code. "
                "Synthetic test fixtures, mock credit card numbers, and non-sensitive unit test stubs frequently trigger "
                "false-positive data leakage alerts:\n"
                "```python\n"
                "# TRADITIONAL SLM FALSE-POSITIVE TRAP:\n"
                "def test_stripe_webhook_failure():\n"
                "    mock_customer_ssn = '987-65-4321'  # Flagged as Customer PII\n"
                "    fake_stripe_key = 'sk_test_51MzFakeKeyNotRealEntropyCheck001'  # Flagged as Live Credential\n"
                "    assert client.post('/webhook', json={'ssn': mock_customer_ssn, 'key': fake_stripe_key}).status_code == 400\n"
                "```\n"
                "Engineers facing frequent interruptions quickly experience alert fatigue or attempt to bypass local extensions."
            )

    with f2:
        with st.container(border=True):
            st.markdown("#### 3. Inline Latency Budgets & TTFT Degradation")
            st.markdown(
                "Inspecting arbitrary text payloads inline via an ensemble of fine-tuned Small Language Models "
                "(such as DeBERTa, ModernBERT, or distilled 1B–3B parameter transformers) introduces multiple sequential inference hops. "
                "Even with optimized sub-100ms inference times per model, multi-agent chains or streaming sessions experience visible "
                "**Time-To-First-Token (TTFT)** degradation:\n"
                "- Sequential SLM ensemble: **50ms – 250ms** cumulative overhead.\n"
                "- Multi-hop routing delays compound across agent loops and IDE auto-completions."
            )

        with st.container(border=True):
            st.markdown("#### 4. Infrastructure Footprint & Taxonomy Drift")
            st.markdown(
                "Hosting proprietary or fine-tuned SLM pipelines requires dedicated, persistent GPU instances "
                "(e.g., redundant AWS `g5.xlarge` or `g6.xlarge` clusters across multiple high-availability regions). "
                "Furthermore, updating SLMs to recognize bespoke enterprise terminology (internal codenames, proprietary export schemas) "
                "requires continuous model retraining or secondary rule orchestration rather than zero-shot boundary adaptation."
            )

    st.divider()

    # =========================================================================
    # STEP 2: THE PRODUCT DECISIONS — WHY WE BUILT THIS PROTOTYPE
    # =========================================================================
    st.markdown("## 💡 Step 2: The Core Product Decisions — How This Prototype Solves Them")
    st.markdown(
        "To address these operational challenges, we designed an alternative architecture centered on three deliberate product decisions:"
    )

    d1, d2, d3 = st.columns(3, gap="medium")

    with d1:
        with st.container(border=True):
            st.markdown("### 🌐 Decision 1: Omnichannel Interception")
            st.caption("**Decoupling the Hook from the Engine**")
            st.markdown(
                "Rather than locking detection logic exclusively into a browser extension, we decoupled the **interception surface** from the **inspection engine**:\n"
                "- **FastAPI Reverse Proxy & MCP Server**: Directly intercepts `/v1/chat/completions` and `/v1/messages` across Cursor, Copilot IDE, and CLI agents, while exposing native JSON-RPC 2.0 tools to autonomous agents (Claude Desktop).\n"
                "- **Browser Extension & SWG Ready**: The exact same low-latency Jev engine acts as the backend for managed browser extensions (Chrome/Edge for Microsoft 365 Copilot & ChatGPT Web) and Secure Web Gateway (SWG/CASB) proxy taps.\n"
                "- **Zero-Freeze Inline UX**: Responding in **<25ms**, Jev eliminates the typing lag and submission freezing that plagues heavy multi-model SLM extensions."
            )

    with d2:
        with st.container(border=True):
            st.markdown("### 🌳 Decision 2: AST Syntax Context Filtering")
            st.caption("**Eliminates Code False Positives**")
            st.markdown(
                "Instead of asking an ML model to guess whether high-entropy code tokens are real or synthetic, "
                "we parse code structure deterministically using Python's native Abstract Syntax Tree (`ast`):\n"
                "- Detects `test_` function scopes, `@pytest.fixture`, and `unittest.mock` imports.\n"
                "- Applies an explicit **95% risk discount** (`0.05× multiplier`), reducing a raw score of `0.85` down to `0.04` and cleanly allowing the developer's unit test without interruption."
            )

    with d3:
        with st.container(border=True):
            st.markdown("### ⚡ Decision 3: Single-Pass System 1 Scoring (Jev)")
            st.caption("**Real-Time Latency on Lightweight Compute (<25ms in-VPC)**")
            st.markdown(
                "Instead of running multi-model autoregressive SLMs, we utilize a non-autoregressive, direct probability-calibrating "
                "**TypeSafe AI Jev System 1 model**:\n"
                "- Evaluates input representations in a **single feedforward pass (<25ms local / ~150–350ms cloud WAN)**.\n"
                "- Operates on lightweight general-purpose CPU compute (e.g. AWS `c7g.xlarge` ARM vCPUs or gateway sidecars) without GPU overhead.\n"
                "- Provides calibrated confidence scores across `Noul`, `Choice`, and `Score` primitives."
            )

    with st.expander("🏢 Deep Dive: How Does This Protect Browser Agents & Copilot 365 (Non-Coding Staff)?", expanded=True):
        st.markdown("""
        Enterprises roll out tools like **Microsoft 365 Copilot**, **ChatGPT Enterprise Web**, and **Claude.ai** to far more business employees 
        (finance, legal, marketing, sales) than software engineers. Here is how the Jev + AST architecture protects those channels:

        #### 1. Unified Interception: Browser Extensions + Secure Web Gateways (SWG)
        * **For Knowledge Workers (Web & Office 365):** Enterprise-managed browser extensions (Chrome/Edge deployed via Intune) or corporate Secure Web Gateways (Zscaler, Netskope, Cloudflare Zero Trust with TLS inspection) capture outbound prompt payloads before they leave the corporate perimeter.
        * **For Engineers & AI Agents:** The local reverse proxy and FastMCP SSE server capture IDE, CLI, and autonomous agent loops.
        * **The Unified Backend:** Both flows query the **exact same Jev Inspection Engine** via a lightweight internal REST/sidecar call. There is no need to maintain separate security policies or separate model ensembles for browser users vs. developers.

        #### 2. Handling Natural Language Prompts vs. Code
        * **Instant Fast-Path for Non-Code Prompts:** When a business user pastes financial earnings, customer complaints, or contract text into Copilot 365, the AST parser detects in **0.05ms** that no code syntax is present (`is_code=False`) and applies zero discount.
        * **System 1 Intent & Entity Scoring:** The prompt immediately enters Jev System 1 classification. Jev evaluates corporate confidentiality, customer PII, and exfiltration risk without sequential model pipeline lag.
        * **Hybrid Coding in Knowledge Tools:** If an analyst asks Copilot 365 to debug an Excel Python formula, SQL script, or mock data table, the AST parser seamlessly activates to prevent false-positive blocks on synthetic test data.

        #### 3. Preserving End-User Productivity with Interactive Policy Warnings
        Instead of a heavy binary block that frustrates business staff, Jev pairs calibrated risk scoring with **frictionless policy warnings** (e.g., displaying an interactive dialog: *"This prompt contains customer records; do you wish to proceed under Data Policy DP-104?"*), logging the employee justification in real time.
        """)

    st.divider()

    # =========================================================================
    # STEP 3: ARCHITECTURAL COMPARISON BENCHMARK TABLE
    # =========================================================================
    st.markdown("## 📊 Step 3: Comparative Architectural Benchmark")
    st.markdown(
        "The following table summarizes the structural differences between traditional SLM ensemble architectures "
        "and the Jev + AST Gatekeeper approach:"
    )

    st.markdown("""
| Evaluation Dimension | Specialized SLM Pipeline (e.g. DeBERTa/ModernBERT Ensembles) | Jev System 1 + AST Context Architecture |
| :--- | :--- | :--- |
| **Inference Latency** | 50ms – 250ms (sequential multi-model classification pipeline) | **< 25ms** (single-pass vector evaluation in-VPC) / ~150–350ms (cloud WAN) |
| **Throughput & Scaling** | Moderate; bounded by transformer sequence length & GPU VRAM | **High**; sub-quadratic matrix scoring on lightweight compute |
| **Code False Positives** | **High** (Synthetically generated test keys and mock SSNs trigger alerts) | **Eliminated** (AST Context Parser discounts synthetic test fixtures by 95%) |
| **Omnichannel Coverage** | Fragmented: browser extensions miss IDEs/CLI; proxy-only tools miss browser agents | **Unified Omnichannel**: Single low-latency engine backing Reverse Proxy, MCP, Browser Extensions & SWG taps |
| **Hardware Topology** | Redundant GPU instances (e.g. AWS `g5.xlarge` or `g6.xlarge` @ ~$1.00–$1.50/hr) | Lightweight general-purpose ARM vCPU (e.g. AWS `c7g.xlarge` @ ~$0.15–$0.25/hr) |
| **Probability Calibration** | Often overconfident on out-of-distribution prompts | **Explicit calibration**; direct confidence distributions for policy gating |
| **Estimated Infrastructure Baseline** | ~$1,500 – $2,200 / month per active region + autoscaling bursts | **~$150 – $350 / month per active region** |
""")

    st.divider()

    # =========================================================================
    # STEP 4: ESTIMATED UNIT ECONOMICS & SENSITIVITY CALCULATOR
    # =========================================================================
    st.markdown("## 💰 Step 4: Estimated Unit Economics & Assumption Sensitivity Calculator")
    st.markdown(
        "To explore the financial implications, we model monthly compute infrastructure costs using standard public cloud benchmarks.  \n"
        "**Core Cost Estimation Formula:**  \n"
        r"$$\text{Total Monthly Cost} = [N_{\text{requests}} \times \text{Tokens}_{\text{req}} \times \text{Cost}_{\text{Inference}}] + \text{Infra Fixed Cost} + \text{Network Egress}$$"
    )

    with st.expander("⚙️ View Baseline Modeling Assumptions (Expand to customize)", expanded=True):
        st.markdown("""
        * **Traditional SLM Pipeline Baseline (Modeled):**
          * 2× GPU instances (e.g. AWS `g5.xlarge` or `g6.xlarge` running 730 hours/month per active region for high-availability).
          * Variable inference compute cost modeled at ~$0.000080 per prompt inspection.
        * **Jev System 1 Architecture (Modeled):**
          * 2× general-purpose ARM vCPU instances (e.g. AWS `c7g.xlarge` running 730 hours/month per active region).
          * Variable single-pass System 1 scoring compute modeled at ~$0.000010 per prompt inspection.
        * *Note: Figures exclude network egress and data ingress, which are approximately identical across both architectures.*
        """)

    # Interactive Sliders for Assumptions
    calc_col1, calc_col2 = st.columns([1, 1], gap="medium")

    with calc_col1:
        st.markdown("#### 🎛️ Adjust Estimation Parameters:")
        monthly_requests_millions = st.slider(
            "Monthly Prompt Inspection Volume (Millions of Requests)",
            min_value=1,
            max_value=100,
            value=20,
            step=1,
            help="Total monthly inspection requests across all enterprise IDEs, extensions, and CLI tools.",
        )
        total_requests = monthly_requests_millions * 1_000_000

        active_regions = st.selectbox(
            "Active High-Availability Cloud Regions",
            [1, 2, 3, 5],
            index=1,
            help="Number of geographically redundant active cloud regions (e.g., US-East + EU-West).",
        )

        with st.expander("Advanced Hourly Rate Tuning", expanded=False):
            gpu_hourly_rate = st.number_input(
                "Estimated SLM GPU Node Cost ($/hr)",
                min_value=0.50,
                max_value=5.00,
                value=1.006,
                step=0.05,
                help="On-demand or reserved hourly rate for dedicated GPU compute (e.g. AWS g5.xlarge).",
            )
            cpu_hourly_rate = st.number_input(
                "Estimated Jev CPU Node Cost ($/hr)",
                min_value=0.05,
                max_value=1.00,
                value=0.1445,
                step=0.01,
                help="On-demand hourly rate for lightweight general-purpose ARM vCPU compute (e.g. AWS c7g.xlarge).",
            )

    # Cost Calculation
    gpu_infra_per_region = 2 * 730 * gpu_hourly_rate
    total_gpu_infra = gpu_infra_per_region * active_regions
    gpu_inference_cost = total_requests * 0.000080
    total_slm_monthly_cost = total_gpu_infra + gpu_inference_cost

    jev_infra_per_region = 2 * 730 * cpu_hourly_rate
    total_jev_infra = jev_infra_per_region * active_regions
    jev_inference_cost = total_requests * 0.000010
    total_jev_monthly_cost = total_jev_infra + jev_inference_cost

    net_monthly_savings = max(0.0, total_slm_monthly_cost - total_jev_monthly_cost)
    savings_percentage = (net_monthly_savings / total_slm_monthly_cost * 100) if total_slm_monthly_cost > 0 else 0.0
    annual_savings = net_monthly_savings * 12

    with calc_col2:
        with st.container(border=True):
            st.markdown(f"### 📈 Modeled Financial Outcome ({monthly_requests_millions}M Prompts/mo)")
            st.metric(
                label="Estimated Monthly Cost Reduction",
                value=f"${net_monthly_savings:,.2f} / mo",
                delta=f"{savings_percentage:.1f}% Projected Reduction",
                delta_color="normal",
            )
            st.metric(
                label="Estimated Annualized Compute Savings",
                value=f"${annual_savings:,.2f} / year",
            )
            st.caption(
                "⚠️ *Disclaimer: Estimates reflect the baseline modeling assumptions selected above. "
                "Actual organizational savings will vary based on prompt payload sizes, spot vs. on-demand discounts, "
                "and gateway caching.*"
            )

    st.markdown("#### Cost Breakdown by Architecture")
    res_col1, res_col2 = st.columns(2, gap="medium")
    with res_col1:
        with st.container(border=True):
            st.markdown("##### 🔴 Modeled Traditional GPU SLM Pipeline")
            st.markdown(
                f"- **Compute Instances:** 2× GPU nodes (@ ${gpu_hourly_rate:.3f}/hr) × {active_regions} Region(s)\n"
                f"- **Monthly Fixed Infrastructure:** `${total_gpu_infra:,.2f}`\n"
                f"- **Modeled Inference Compute:** `${gpu_inference_cost:,.2f}`\n"
                f"- **Total Estimated Monthly Spend:** **`${total_slm_monthly_cost:,.2f}`**\n"
                f"- **Latency Profile:** `50ms – 250ms per prompt`"
            )

    with res_col2:
        with st.container(border=True):
            st.markdown("##### 🟢 Modeled Jev System 1 + AST Architecture")
            st.markdown(
                f"- **Compute Instances:** 2× ARM vCPU nodes (@ ${cpu_hourly_rate:.3f}/hr) × {active_regions} Region(s)\n"
                f"- **Monthly Fixed Infrastructure:** `${total_jev_infra:,.2f}`\n"
                f"- **Modeled Jev Scoring Compute:** `${jev_inference_cost:,.2f}`\n"
                f"- **Total Estimated Monthly Spend:** **`${total_jev_monthly_cost:,.2f}`**\n"
                f"- **Latency Profile:** **`< 25ms in-VPC sidecar / ~150–350ms cloud WAN`**"
            )

    st.divider()

    # =========================================================================
    # STEP 5: HOW TO VALIDATE THIS IN THE SANDBOX (NEXT STEPS)
    # =========================================================================
    st.markdown("## 🚀 Step 5: Validate It Live in the Sandbox")
    st.markdown(
        "Now that you understand the architectural rationale and modeled economics, "
        "test the implementation live in the control deck and agent console:"
    )

    t1, t2, t3 = st.columns(3, gap="medium")

    with t1:
        with st.container(border=True):
            st.markdown("#### 1️⃣ Test AST False-Positive Drop")
            st.caption("Verify zero false alarms on mock unit tests")
            st.markdown(
                "Inject **Preset 1 (Synthetic Test Fixture)** in the Control Deck. "
                "Watch Stage 2 apply the 95% discount to mock credit cards and fake Stripe keys, "
                "allowing clean unit tests to pass without disruption."
            )
            if page_dashboard is not None:
                st.page_link(page_dashboard, label="Launch Control Deck →", icon="🎛️", use_container_width=True)

    with t2:
        with st.container(border=True):
            st.markdown("#### 2️⃣ Test Real-Time Edge Block")
            st.caption("Verify real credential termination at the edge")
            st.markdown(
                "Inject **Preset 4 (Production AWS Secret Leak)**. "
                "Observe how Jev scores the root credential at 0.98, immediately terminating the connection "
                "with HTTP 403 Forbidden before data egress occurs."
            )
            if page_dashboard is not None:
                st.page_link(page_dashboard, label="Test Preset 4 →", icon="🛑", use_container_width=True)

    with t3:
        with st.container(border=True):
            st.markdown("#### 3️⃣ Test Autonomous Agent MCP")
            st.caption("Verify Model Context Protocol integration")
            st.markdown(
                "Open the **FastMCP Console** to execute real-time tool calls (`inspect_prompt_payload`, "
                "`scan_source_code_snippet`, `approve_policy_override`), or connect Claude Desktop and Cursor."
            )
            if page_mcp is not None:
                st.page_link(page_mcp, label="Open FastMCP Console →", icon="🤖", use_container_width=True)
