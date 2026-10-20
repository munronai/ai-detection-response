"""Serverless deployment specification for Modal (FastAPI + FastMCP + Streamlit)."""

import os
import subprocess
import modal

app = modal.App("jev-aidr-sandbox")

image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install(
        "fastapi",
        "uvicorn",
        "fastmcp",
        "mcp",
        "httpx",
        "pydantic",
        "pydantic-settings",
        "python-dotenv",
        "streamlit",
        "pandas",
    )
    .add_local_python_source("app")
)

# =====================================================================
# Secrets Configuration (Live TypeSafe AI API Key & Target Providers)
# =====================================================================
def configure_modal_secrets() -> list:
    """
    Resolves secrets for Modal deployment:
    1. If a local `.env` file exists, automatically loads it via modal.Secret.from_dotenv(".env").
       This allows testing with live Jev (TYPESAFE_API_KEY) without manual dashboard configuration.
    2. Injects any host environment keys (TYPESAFE_API_KEY, JEV_MODE, etc.) if .env is missing.
    3. Supports remote Modal Secret 'aidr-sandbox-secrets' or $MODAL_SECRET_NAME if defined.
    """
    secrets = []

    # 1. Automatic loading from local .env
    if os.path.exists(".env"):
        secrets.append(modal.Secret.from_dotenv(".env"))

    # 2. Host environment variables fallback
    host_keys = {
        k: os.environ[k]
        for k in [
            "TYPESAFE_API_KEY",
            "TYPESAFE_API_URL",
            "TYPESAFE_MODEL",
            "JEV_MODE",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "SANDBOX_ADMIN_KEY",
        ]
        if k in os.environ
    }
    if host_keys and not os.path.exists(".env"):
        secrets.append(modal.Secret.from_dict(host_keys))

    # 3. Optional remote Modal Secret by name
    remote_secret_name = os.getenv("MODAL_SECRET_NAME")
    if remote_secret_name:
        secrets.append(modal.Secret.from_name(remote_secret_name))
    elif not secrets:
        try:
            secrets.append(modal.Secret.from_name("aidr-sandbox-secrets"))
        except Exception:
            pass

    return secrets


SECRETS = configure_modal_secrets()


# 1. Public REST API (/docs, /api/v1/*) + FastMCP Server (/mcp/sse)
@app.function(image=image, secrets=SECRETS, scaledown_window=120)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def api():
    from app.gateway.proxy import app as fastapi_app

    return fastapi_app


# 2. Public Streamlit Dashboard UI (Dynamically discovers the `api` Modal URL)
@app.function(
    image=image,
    secrets=SECRETS,
    max_containers=1,  # Sticky session for Streamlit WebSockets
    scaledown_window=300,
)
@modal.concurrent(max_inputs=50)
@modal.web_server(8501)
def dashboard():
    api_root_url = api.get_web_url().rstrip("/")

    env = os.environ.copy()
    env["SANDBOX_API_BASE"] = f"{api_root_url}/api/v1"
    env["SANDBOX_MCP_URL"] = f"{api_root_url}/mcp/sse"
    env["SANDBOX_DOCS_URL"] = f"{api_root_url}/docs"

    subprocess.Popen(
        [
            "streamlit",
            "run",
            "app/ui/dashboard_app.py",
            "--server.port",
            "8501",
            "--server.address",
            "0.0.0.0",
            "--server.headless",
            "true",
            "--server.enableCORS",
            "false",
            "--server.enableXsrfProtection",
            "false",
        ],
        env=env,
    )
