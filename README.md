# Jev Gatekeeper & AST Context Parser for Enterprise AIDR

**A High-Performance Tri-Pillar Alternative to Traditional Multi-Model SLM AI Detection & Response**

[![Tests](https://img.shields.io/badge/Tests-19%20Passed-brightgreen)](tests/)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP%20SSE-blue)](app/mcp/)
[![Python](https://img.shields.io/badge/Python-3.13%2B-blue)](pyproject.toml)

---

## 1. Executive Summary

This prototype and simulation sandbox demonstrates how enterprises can protect against AI prompt data loss, credential leakage, and IP exfiltration **without** the latency penalties, false-positive friction, and GPU infrastructure costs of traditional multi-model Small Language Model (SLM) ensembles:

* **AST Context Engine for False-Positive Elimination**: Uses Python `ast` syntax analysis to inspect test scopes, mock frameworks (`unittest.mock`, `pytest`), and synthetic identifiers (`mock_`, `fake_`, `test_`). Applies a **95% risk discount** to synthetic fixtures, stopping developer alert fatigue.
* **TypeSafe AI Jev System 1 Core**: Replaces slow, autoregressive SLMs (50ms–250ms latency) with a non-autoregressive, direct probability-calibrating System 1 model (<15ms latency) using calibrated `Noul` (binary), `Choice` (classification), and `Score` (urgency) primitives.
* **Unified Tri-Pillar Architecture**:
  * **Pillar 1**: High-Performance FastAPI Reverse Proxy (`/v1/chat/completions`, `/v1/messages`) with heuristic client fingerprinting (Cursor, Copilot, Claude Desktop, Antigravity CLI, curl).
  * **Pillar 2**: FastMCP SSE Server (`/mcp/sse`) with transport security (DNS rebinding protection) and tools for autonomous AI agents.
  * **Pillar 3**: Enterprise AIDR Streamlit Control Deck featuring an intuitive **4-Stage Step-by-Step Walkthrough Card**, Shadow AI Discovery feed, and interactive Cost Savings Calculator.

---

## 2. Quickstart: Running Locally

### Step 1: Install Dependencies & Activate Environment
```bash
# Using the local virtualenv
source .venv/bin/activate
pip install -r requirements.txt  # Or use pre-installed .venv packages
```

### Step 2: Start the FastAPI Gateway & FastMCP Server (Terminal 1)
```bash
.venv/bin/uvicorn app.gateway.proxy:app --host 0.0.0.0 --port 8000 --reload
```
* **API Documentation**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **MCP SSE Endpoint**: [http://127.0.0.1:8000/mcp/sse](http://127.0.0.1:8000/mcp/sse)

### Step 3: Start the Streamlit AIDR Control Deck (Terminal 2)
```bash
.venv/bin/streamlit run app/ui/dashboard_app.py --server.port 8501
```
* **Dashboard URL**: Open [http://localhost:8501](http://localhost:8501)

---

## 3. Running Automated Tests

Run the full 19-test automated test suite:
```bash
.venv/bin/python -m pytest tests/ -v
```

Run the end-to-end FastMCP self-test (verifying Host header DNS rebinding and SSE tool calls):
```bash
.venv/bin/python test_mcp_client.py --self-test
```

---

## 4. Connecting External AI Agents via MCP

### Option A: Claude Desktop (macOS / Windows)
Add to your `claude_desktop_config.json`:
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

### Option B: Cursor IDE
In Cursor **Settings** → **Features** → **MCP** → **Add New MCP Server**:
* **Name**: `jev-aidr-gatekeeper`
* **Type**: `sse`
* **URL**: `http://127.0.0.1:8000/mcp/sse`

### Option C: Official MCP Inspector (Zero Install Developer Visualizer)
Run the reference visualizer from your terminal:
```bash
npx @modelcontextprotocol/inspector http://127.0.0.1:8000/mcp/sse
```
* In the web interface (`http://localhost:5173`), set **Transport Type** to **SSE**, URL to `http://127.0.0.1:8000/mcp/sse`, and click **Connect**.


---

## 5. Serverless Deployment to Modal

Deploy the unified FastAPI gateway, FastMCP server, and Streamlit dashboard to Modal in one command:
```bash
modal deploy modal_deploy.py
```
