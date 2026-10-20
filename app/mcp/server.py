"""FastMCP Server exposing AIDR Inspection Tools and Telemetry Resources."""

import json
import logging
import os
import fnmatch
from typing import Any, Dict, List, Literal, Optional
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecurityMiddleware, TransportSecuritySettings

logger = logging.getLogger(__name__)

from app.domain.models import (
    ClientIdentity,
    ClientType,
    InterventionAction,
    PromptInspectionRecord,
)
from app.domain.presets import AIDR_PRESETS
from app.engine.ast_parser import parse_and_audit_code
from app.engine.jev_client import evaluate_prompt_with_jev

# Modal & Local Transport Security Settings
MODAL_HOST = os.getenv("MODAL_APP_HOST", "*.modal.run")
EXTRA_HOSTS = [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]

ALLOWED_HOSTS = [
    "127.0.0.1",
    "127.0.0.1:*",
    "localhost",
    "localhost:*",
    "[::1]",
    "[::1]:*",
    "*.modal.run",
    "*.modal.run:*",
    "*.modal.direct",
    "*.modal.direct:*",
]
if MODAL_HOST:
    ALLOWED_HOSTS.extend([MODAL_HOST, f"{MODAL_HOST}:*"])
ALLOWED_HOSTS.extend(EXTRA_HOSTS)

ALLOWED_ORIGINS = [
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
    "https://*.modal.run",
    "https://*.modal.direct",
]
if MODAL_HOST:
    ALLOWED_ORIGINS.extend([f"https://{MODAL_HOST}", f"https://{MODAL_HOST}:*"])

MCP_TRANSPORT_SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=ALLOWED_HOSTS,
    allowed_origins=ALLOWED_ORIGINS,
)


# ---------------------------------------------------------------------
# Enhance MCP TransportSecurityMiddleware to support wildcard host/origin
# matching (e.g. *.modal.run or *.modal.direct for cloud deployments)
# ---------------------------------------------------------------------
def _enhanced_validate_host(self, host: str | None) -> bool:
    if not host:
        logger.warning("Missing Host header in request")
        return False

    # 1. Exact match
    if host in self.settings.allowed_hosts:
        return True

    # 2. Port and wildcard hostname matching (e.g. *.modal.run)
    host_without_port = host.split(":")[0] if ":" in host and not host.startswith("[") else host
    for allowed in self.settings.allowed_hosts:
        if allowed.endswith(":*"):
            base_host = allowed[:-2]
            if host.startswith(base_host + ":") or fnmatch.fnmatch(host_without_port, base_host):
                return True
        if fnmatch.fnmatch(host, allowed) or fnmatch.fnmatch(host_without_port, allowed):
            return True

    logger.warning(f"Invalid Host header: {host}")
    return False


def _enhanced_validate_origin(self, origin: str | None) -> bool:
    if not origin:
        return True

    if origin in self.settings.allowed_origins:
        return True

    for allowed in self.settings.allowed_origins:
        if allowed.endswith(":*"):
            base_origin = allowed[:-2]
            if origin.startswith(base_origin + ":") or fnmatch.fnmatch(origin, base_origin):
                return True
        if fnmatch.fnmatch(origin, allowed):
            return True

    logger.warning(f"Invalid Origin header: {origin}")
    return False


TransportSecurityMiddleware._validate_host = _enhanced_validate_host
TransportSecurityMiddleware._validate_origin = _enhanced_validate_origin

mcp = MCPServer("Jev-AIDR-Gatekeeper")


# =====================================================================
# MODEL-CONTROLLED TOOLS
# =====================================================================


@mcp.tool()
async def inspect_prompt_payload(
    prompt_text: str,
    client_name: str = "Claude Desktop",
) -> Dict[str, Any]:
    """
    Evaluates a candidate prompt or code payload through the Jev Gatekeeper and AST Context Parser.
    Returns the complete 4-stage security inspection result, risk distribution, and policy action.
    """
    from app.gateway.proxy import INCIDENTS, update_telemetry

    # Stage 1: Client Attribution
    client_id = ClientIdentity(
        client_type=ClientType.CLAUDE_DESKTOP if "claude" in client_name.lower() else ClientType.UNKNOWN,
        client_name=f"MCP Client: {client_name}",
        detected_via="MCP_HANDSHAKE",
    )

    # Stage 2: AST Context Parser
    ast_res = parse_and_audit_code(prompt_text)

    # Stage 3: Jev System 1 Core
    jev_eval = await evaluate_prompt_with_jev(
        prompt_text=prompt_text,
        ast_res=ast_res,
        client_name=client_name,
    )

    # Stage 4: Enforcement Record
    record = PromptInspectionRecord(
        client_identity=client_id,
        endpoint_path="/mcp/inspect_prompt_payload",
        target_provider="SIMULATED_LOCAL",
        extracted_prompt_text=prompt_text[:1000],
        token_count=len(prompt_text.split()),
        ast_analysis=ast_res,
        jev_evaluation=jev_eval,
        applied_action=jev_eval.action_taken,
        total_pipeline_latency_ms=jev_eval.eval_time_ms + ast_res.analysis_time_ms,
    )

    INCIDENTS.append(record)
    update_telemetry(record)
    return record.model_dump()


@mcp.tool()
async def scan_source_code_snippet(
    code_text: str,
    language: str = "python",
) -> Dict[str, Any]:
    """
    Runs AST syntax parsing and Jev System 1 evaluation specifically on a source code snippet.
    Determines whether high-entropy strings reside within synthetic mock scopes or represent real credential leaks.
    """
    ast_res = parse_and_audit_code(code_text)
    jev_eval = await evaluate_prompt_with_jev(prompt_text=code_text, ast_res=ast_res, client_name="CodeScanner")

    return {
        "ast_analysis": ast_res.model_dump(),
        "jev_evaluation": jev_eval.model_dump(),
        "is_synthetic_fixture": ast_res.is_synthetic_test_fixture,
        "policy_action": jev_eval.action_taken.value,
        "discounted_risk_score": jev_eval.calibrated_urgency_score,
    }


@mcp.tool()
async def simulate_traffic_scenario(
    preset_id: Literal[
        "1_synthetic_test_fixture",
        "2_routine_admin_prompt",
        "3_ambiguous_customer_pii",
        "4_production_secret_leak",
        "5_base64_exfiltration",
    ] = "1_synthetic_test_fixture",
) -> Dict[str, Any]:
    """
    Injects one of the 5 Golden AIDR Presets into the sandbox and returns
    the step-by-step gatekeeper assessment and updated fleet telemetry.
    """
    if preset_id not in AIDR_PRESETS:
        return {"error": f"Unknown preset '{preset_id}'. Choose from: {list(AIDR_PRESETS.keys())}"}

    preset = AIDR_PRESETS[preset_id]
    result = await inspect_prompt_payload(
        prompt_text=preset.prompt_text,
        client_name=preset.target_client,
    )

    return {
        "preset_id": preset.preset_id,
        "title": preset.title,
        "what_it_tests": preset.what_it_tests,
        "inspection_result": result,
    }


@mcp.tool()
async def approve_policy_override(
    incident_id: str,
    reason: str = "Authorized security exception approved by compliance officer",
    approved_by: str = "SecurityAdmin",
) -> Dict[str, Any]:
    """
    Allows a compliance analyst or security engineer to approve or whitelist an incident
    flagged for review or blocked by policy.
    """
    from app.gateway.proxy import INCIDENTS, ensure_demo_incidents
    ensure_demo_incidents()

    for inc in INCIDENTS:
        if inc.incident_id == incident_id:
            prev_action = inc.applied_action.value
            inc.applied_action = InterventionAction.ALLOW
            inc.jev_evaluation.action_taken = InterventionAction.ALLOW
            inc.jev_evaluation.reasoning_summary += f" [MANUAL OVERRIDE: {reason} (approved by {approved_by})]"
            return {
                "status": "APPROVED",
                "incident_id": incident_id,
                "previous_action": prev_action,
                "new_action": "ALLOW",
                "approved_by": approved_by,
                "reason": reason,
                "note": f"Incident '{incident_id}' updated from {prev_action} to ALLOW by {approved_by}: {reason}",
            }

    available_ids = [i.incident_id for i in INCIDENTS[-5:]]
    return {
        "error": f"Incident ID '{incident_id}' not found in active audit stream.",
        "available_incident_ids": available_ids,
        "hint": "Try using 'inc_demo_01' which is pre-seeded with a blocked AWS credential leak.",
    }


@mcp.tool()
async def get_fleet_security_posture() -> Dict[str, Any]:
    """
    Returns live aggregated AIDR telemetry, active developer client distribution,
    latency benchmarks, and financial cost-savings.
    """
    from app.gateway.proxy import TELEMETRY

    return TELEMETRY.model_dump()


# =====================================================================
# STATIC & TEMPLATED MCP RESOURCES
# =====================================================================


@mcp.resource("aidr://telemetry/live-kpis")
async def mcp_get_live_kpis() -> str:
    """Returns the live AIDR telemetry stream in JSON format."""
    from app.gateway.proxy import TELEMETRY

    return TELEMETRY.model_dump_json(indent=2)


@mcp.resource("aidr://presets/catalog")
async def mcp_get_presets_catalog() -> str:
    """Returns the pre-configured catalog of test scenarios."""
    catalog = {k: v.model_dump() for k, v in AIDR_PRESETS.items()}
    return json.dumps(catalog, indent=2)


@mcp.resource("aidr://incidents/latest")
async def mcp_get_latest_incident() -> str:
    """Returns the most recent prompt evaluation incident."""
    from app.gateway.proxy import INCIDENTS

    if not INCIDENTS:
        return json.dumps({"status": "No incidents recorded yet."})
    return INCIDENTS[-1].model_dump_json(indent=2)
