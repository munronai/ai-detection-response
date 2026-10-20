"""Heuristic and deterministic client fingerprinting engine."""

import re
from typing import Any, Dict, Optional
from fastapi import Request
from app.domain.models import ClientIdentity, ClientType


USER_AGENT_PATTERNS = [
    (re.compile(r"cursor", re.IGNORECASE), ClientType.CURSOR, "Cursor IDE"),
    (re.compile(r"copilot|githubcopilot", re.IGNORECASE), ClientType.COPILOT, "VS Code Copilot"),
    (re.compile(r"claude|anthropic", re.IGNORECASE), ClientType.CLAUDE_DESKTOP, "Claude Desktop"),
    (re.compile(r"antigravity|agy", re.IGNORECASE), ClientType.ANTIGRAVITY_CLI, "Google Antigravity CLI"),
    (re.compile(r"curl", re.IGNORECASE), ClientType.DIRECT_CURL, "curl / Command-line"),
    (re.compile(r"python|httpx|requests", re.IGNORECASE), ClientType.PYTHON_SDK, "Python SDK Client"),
]

ROUTE_PROFILE_MAP = {
    "cursor": (ClientType.CURSOR, "Cursor IDE (Virtual Profile)"),
    "copilot": (ClientType.COPILOT, "VS Code Copilot (Virtual Profile)"),
    "claude": (ClientType.CLAUDE_DESKTOP, "Claude Desktop (Virtual Profile)"),
    "antigravity": (ClientType.ANTIGRAVITY_CLI, "Google Antigravity CLI (Virtual Profile)"),
    "gemini": (ClientType.ANTIGRAVITY_CLI, "Gemini CLI Agent (Virtual Profile)"),
    "cli": (ClientType.DIRECT_CURL, "Direct CLI (Virtual Profile)"),
}


def identify_client(request: Request, body_payload: Optional[Dict[str, Any]] = None) -> ClientIdentity:
    """
    Identifies the originating client application using a multi-layered heuristic:
    1. Virtual Route Profile (/proxy/{client_name}/...) -> 100% Deterministic
    2. HTTP User-Agent inspection
    3. Payload morphology & headers (Anthropic vs OpenAI vs Gemini)
    4. Client IP & TLS JA4 placeholder
    """
    path = request.url.path.lower()
    headers = request.headers
    user_agent = headers.get("user-agent", "")
    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Virtual Route Profile check (e.g., /proxy/cursor/v1/chat/completions)
    for profile_key, (c_type, c_name) in ROUTE_PROFILE_MAP.items():
        if f"/proxy/{profile_key}/" in path or path.startswith(f"/{profile_key}/"):
            return ClientIdentity(
                client_type=c_type,
                client_name=c_name,
                user_agent=user_agent or "Routed-Virtual-Profile",
                ip_address=client_ip,
                detected_via="ROUTE_PROFILE",
            )

    # 2. User-Agent Matching
    if user_agent:
        for pattern, c_type, c_name in USER_AGENT_PATTERNS:
            if pattern.search(user_agent):
                # Extract version if present (e.g. Cursor/0.42.1)
                version_match = re.search(rf"{pattern.pattern}/([0-9\.]+)", user_agent, re.IGNORECASE)
                version_str = version_match.group(1) if version_match else None

                return ClientIdentity(
                    client_type=c_type,
                    client_name=c_name,
                    client_version=version_str,
                    user_agent=user_agent,
                    ip_address=client_ip,
                    detected_via="USER_AGENT",
                )

    # 3. Schema & Endpoint Morphology
    if "anthropic-version" in headers or "/v1/messages" in path:
        return ClientIdentity(
            client_type=ClientType.CLAUDE_DESKTOP,
            client_name="Anthropic Client / Claude Desktop",
            user_agent=user_agent,
            ip_address=client_ip,
            detected_via="SCHEMA_MORPHOLOGY",
        )

    if body_payload and isinstance(body_payload, dict):
        if "contents" in body_payload:
            return ClientIdentity(
                client_type=ClientType.ANTIGRAVITY_CLI,
                client_name="Google Gemini SDK / CLI",
                user_agent=user_agent,
                ip_address=client_ip,
                detected_via="SCHEMA_MORPHOLOGY",
            )

    # Default fallback
    return ClientIdentity(
        client_type=ClientType.UNKNOWN,
        client_name="Generic API Caller",
        user_agent=user_agent or "None",
        ip_address=client_ip,
        detected_via="SCHEMA_MORPHOLOGY",
    )


def identify_from_mcp_handshake(client_name: str, client_version: Optional[str] = None) -> ClientIdentity:
    """Attributes an autonomous agent connecting directly via Model Context Protocol."""
    clean_name = client_name.lower()
    c_type = ClientType.UNKNOWN

    if "claude" in clean_name:
        c_type = ClientType.CLAUDE_DESKTOP
    elif "cursor" in clean_name:
        c_type = ClientType.CURSOR
    elif "antigravity" in clean_name or "gemini" in clean_name:
        c_type = ClientType.ANTIGRAVITY_CLI
    else:
        c_type = ClientType.UNKNOWN

    return ClientIdentity(
        client_type=c_type,
        client_name=f"MCP Client: {client_name}",
        client_version=client_version,
        detected_via="MCP_HANDSHAKE",
    )
