# Jev Gatekeeper & AST Context Parser for Enterprise AIDR

**An Alternative to Traditional Multi-Model SLM AI Detection & Response**

[![Tests](https://img.shields.io/badge/Tests-21%20Passed-brightgreen)](tests/)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP%20SSE-blue)](app/mcp/)
[![Python](https://img.shields.io/badge/Python-3.13%2B-blue)](pyproject.toml)
[![Deployment](https://img.shields.io/badge/Modal-Serverless%20Ready-purple)](modal_deploy.py)

---

## 1. Executive Summary

This prototype and simulation sandbox demonstrates how modern enterprises can prevent AI prompt data loss, credential leakage, and intellectual property exfiltration **without** the latency penalties, developer alert fatigue, and GPU infrastructure costs of traditional multi-model Small Language Model (SLM) ensembles:

* **AST Context Engine for False-Positive Elimination**: Uses Python's Abstract Syntax Tree (`ast`) to inspect function scopes, mock frameworks (`unittest.mock`, `pytest`), and synthetic identifiers (`mock_`, `fake_`, `test_`). When a synthetic test fixture is detected, it applies a **95% risk discount** (`0.05× multiplier`), eliminating false alarms on mock data and unit tests.
* **TypeSafe AI Jev System 1 Core**: Replaces slow, autoregressive SLMs (50ms–250ms latency) with a non-autoregressive, direct probability-calibrating System 1 model (<15ms latency) evaluated in a single feedforward pass using calibrated `Noul` (binary), `Choice` (classification), and `Score` (urgency) primitives.
* **Unified Tri-Pillar Architecture**:
  * **Pillar 1 — Reverse Gateway**: High-performance FastAPI proxy (`/v1/chat/completions`, `/v1/messages`) with heuristic client fingerprinting (Cursor, Copilot, Claude Desktop, Antigravity CLI, direct API / curl).
  * **Pillar 2 — FastMCP SSE Server**: Mounted at `/mcp` with transport security (DNS rebinding protection against HTTP 421) and tool endpoints for autonomous agents.
  * **Pillar 3 — Streamlit Control Deck**: Interactive UI featuring a **4-Stage Step-by-Step Walkthrough Card**, live engine status indicator (Live TypeSafe AI API vs Simulated), scenario prompt previews, and per-simulation unit economics tracking.

---

## 2. Directory Structure

```
ai-detection-response/
├── app/
│   ├── config.py                 # Application settings, .env loading & policy thresholds
│   ├── domain/
│   │   ├── models.py             # Domain models (ASTAnalysisResult, JevEvaluation, etc.)
│   │   └── presets.py            # 5 Golden AIDR test scenarios & payload metadata
│   ├── engine/
│   │   ├── ast_parser.py         # AST Context Parser (95% false-positive discount)
│   │   └── jev_client.py         # Dual-mode TypeSafe AI System 1 evaluator (live + simulated)
│   ├── gateway/
│   │   ├── fingerprint.py        # Client fingerprinting (Cursor, Copilot, Claude, CLI, curl)
│   │   └── proxy.py              # FastAPI Reverse Proxy, MCP mount & telemetry API
│   ├── mcp/
│   │   └── server.py             # FastMCP SSE server with TransportSecuritySettings
│   └── ui/
│       ├── api_client.py         # Resilient HTTP client connecting Streamlit to FastAPI
│       ├── dashboard_app.py      # Streamlit multi-page router with URL session sync
│       ├── components/
│       │   ├── kpi_header.py     # Fleet KPI telemetry banner
│       │   └── pipeline_card.py  # 4-Stage visual sequence walkthrough card with unit economics
│       └── views/
│           ├── landing_page.py        # Overview, 4-stage pipeline, presets reference
│           ├── sandbox_dashboard.py    # Main Control Deck (engine indicator, prompt previews, unit economics)
│           ├── product_insights.py     # AST false positive analysis, comparison table & ROI calculator
│           ├── mcp_console.py          # Browser FastMCP console with 3-step demo script
│           └── mcp_guides.py           # Setup guides for Claude Desktop, Cursor, and MCP Inspector
├── tests/
│   ├── test_sprint1.py           # AST parsing, client fingerprinting, proxy tests
│   ├── test_sprint2.py           # TypeSafe Jev schema conformance, 5 presets, FastMCP tests
│   └── test_sprint3.py           # UI components, policy endpoints, .env & .gitignore tests
├── modal_deploy.py               # Serverless Modal deployment spec with automated .env injection
├── test_mcp_client.py            # End-to-end FastMCP verification script
├── requirements.txt              # Production and development dependencies
├── .env.example                  # Template environment variables
├── .env                          # Local secrets (gitignored)
├── .gitignore                    # Git ignore rules for .env, .pyc, and caches
└── README.md                     # Project documentation
```

---

## 3. Quickstart: Running Locally

### Step 1: Clone Repository & Setup Environment
```bash
# Clone the repository from remote
git clone https://github.com/munronai/ai-detection-response.git
cd ai-detection-response

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy the template configuration to create your local `.env` file:
```bash
cp .env.example .env
```

Open `.env` and configure your credentials:
```bash
# Optional: Set your TypeSafe AI key to test against live System 1 API
TYPESAFE_API_KEY=your_typesafe_api_key_here
TYPESAFE_API_URL=https://api.typesafe.ai/v1/systemone
TYPESAFE_MODEL=jev-system1-aidr

# Gateway Mode: "live" (uses TYPESAFE_API_KEY) or "simulated" (offline calibrated math)
JEV_MODE=live
```

> [!NOTE]
> If `TYPESAFE_API_KEY` is not provided, the sandbox automatically runs in **Simulated Jev Mode**, providing realistic, mathematically calibrated risk distributions at zero cost.

### Step 3: Start the FastAPI Gateway & FastMCP Server (Terminal 1)
```bash
.venv/bin/uvicorn app.gateway.proxy:app --host 0.0.0.0 --port 8000 --reload
```
* **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **MCP SSE Endpoint**: [http://127.0.0.1:8000/mcp/sse](http://127.0.0.1:8000/mcp/sse)

### Step 4: Start the Streamlit AIDR Control Deck (Terminal 2)
```bash
.venv/bin/streamlit run app/ui/dashboard_app.py --server.port 8501
```
* **Visual Control Deck**: [http://localhost:8501](http://localhost:8501)

---

## 4. Control Deck Features & Walkthrough

The visual control deck provides enterprise security operators and developers with end-to-end visibility into prompt data-in-motion:

1. **Authoritative Engine Status Panel**:
   * Displays the active engine mode: `🧪 TEST / SIMULATED JEV` vs `🟢 LIVE TYPESAFE AI API`.
   * Shows API key authentication status and current policy cutoffs (`Block ≥ 0.92`, `Nudge ≥ 0.80`, `Allow ≤ 0.30`).
   * Provides an instant 1-click **"Switch Engine Mode"** toggle directly on the main deck.
2. **Scenario Selector with Full Prompt Previews**:
   * Inspect any of the **5 Golden Presets** before execution to preview the exact code payload, category, target client, and expected action.
3. **4-Stage Visual Walkthrough Card**:
   * **Stage 1 (Client Intake)**: Fingerprints originating client morphology and token density.
   * **Stage 2 (AST Context Parser)**: Detects test scopes and mock fixtures, displaying the discount formula:
     $$\text{Calibrated Urgency} = \text{Raw Urgency} \times 0.05$$
   * **Stage 3 (Jev System 1 Core)**: Evaluates raw representations in $<15\text{ms}$ via feedforward matrix scoring.
   * **Stage 4 (Enforcement & Routing)**: Enforces `ALLOW`, `NUDGE`, `REDACT`, or `BLOCK` with zero latency overhead.
4. **Per-Simulation Unit Economics Breakdown**:
   * Calculates token count, Jev System 1 compute cost ($0.000010 on ARM vCPU), traditional SLM ensemble cost ($0.000500 on multi-GPU nodes), and net run savings ($0.000490 / 98.0%).
   * Displays monthly fleet cost modeling demonstrating **$117,600/year net savings** (75% to 85%+ compute reduction) at 20M monthly requests.

---

## 5. Model Context Protocol (MCP) Integration

The sandbox exposes a FastMCP server at `/mcp/sse` supporting 3 integration options:

### Option 1: Claude Desktop & Cursor IDE
* **Claude Desktop**: Configure `claude_desktop_config.json` via the `mcp-remote` bridge:
  ```json
  {
    "mcpServers": {
      "jev-aidr-gatekeeper": {
        "command": "npx",
        "args": ["-y", "mcp-remote", "http://127.0.0.1:8000/mcp/sse", "--transport", "sse-only"]
      }
    }
  }
  ```
* **Cursor IDE**: Go to **Settings** → **Features** → **MCP** → **Add New MCP Server**:
  * Name: `jev-aidr-gatekeeper`
  * Type: `sse`
  * URL: `http://127.0.0.1:8000/mcp/sse`

### Option 2: Browser MCP Console (Built-In)
Navigate to the **🤖 MCP Agent Client Console** tab in the Streamlit UI to run live JSON-RPC tool invocations with a guided **3-Step Demo Playbook**:
* **Step 1**: Inspect Synthetic Code (`scan_source_code_snippet`)
* **Step 2**: Leak AWS Secret (`simulate_traffic_scenario` with `4_production_secret_leak`)
* **Step 3**: Check Fleet Posture (`get_fleet_security_posture`)

### Option 3: Official MCP Inspector
Run the reference developer tool from the Model Context Protocol team:
```bash
npx @modelcontextprotocol/inspector http://127.0.0.1:8000/mcp/sse
```

---

## 6. Automated Verification & Testing

Run the full pytest suite (21 unit and integration tests):
```bash
.venv/bin/python -m pytest tests/ -v
```

Run the end-to-end MCP client verification script (validates Host header DNS rebinding protection and SSE tool calling):
```bash
.venv/bin/python test_mcp_client.py --self-test
```

---

## 7. Serverless Deployment to Modal

Deploy the unified FastAPI gateway, FastMCP server, and Streamlit dashboard to Modal in one command:
```bash
modal deploy modal_deploy.py
```

`modal_deploy.py` automatically detects your local `.env` file via `modal.Secret.from_dotenv(".env")`, seamlessly packaging your `TYPESAFE_API_KEY` without requiring manual secrets setup in the Modal web console.
