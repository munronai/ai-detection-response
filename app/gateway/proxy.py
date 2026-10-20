"""FastAPI Reverse Proxy & Prompt Interception Gateway."""

import json
import re
import time
import uuid
from typing import Any, Dict, List, Literal, Optional
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.domain.models import (
    ASTAnalysisResult,
    ClientIdentity,
    ClientType,
    DataClassification,
    FleetTelemetrySummary,
    InterventionAction,
    JevEvaluation,
    PromptInspectionRecord,
)
from app.domain.presets import AIDR_PRESETS, TrafficScenarioPreset
from app.engine.ast_parser import parse_and_audit_code
from app.engine.jev_client import evaluate_prompt_with_jev
from app.gateway.fingerprint import identify_client
from app.mcp.server import mcp, MCP_TRANSPORT_SECURITY

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory telemetry and incident storage
INCIDENTS: List[PromptInspectionRecord] = []
TELEMETRY = FleetTelemetrySummary()


class PolicyUpdateRequest(BaseModel):
    jev_mode: Optional[Literal["simulated", "live"]] = None
    allow_threshold: Optional[float] = None
    silent_log_threshold: Optional[float] = None
    nudge_threshold: Optional[float] = None
    redact_threshold: Optional[float] = None
    block_threshold: Optional[float] = None
    ambiguity_margin: Optional[float] = None


class InjectPresetRequest(BaseModel):
    preset_id: str
    custom_prompt: Optional[str] = None
    target_client: Optional[str] = None


def extract_prompt_text(payload: Dict[str, Any]) -> str:
    """Extracts raw prompt text across OpenAI, Anthropic, and Gemini payload shapes."""
    if not isinstance(payload, dict):
        return str(payload)

    # 1. OpenAI Chat format: {"messages": [{"role": "user", "content": "..."}]}
    if "messages" in payload and isinstance(payload["messages"], list):
        parts = []
        for msg in payload["messages"]:
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        parts.append(block["text"])
        return "\n".join(parts)

    # 2. Anthropic Messages format: {"messages": [...], "system": "..."}
    if "system" in payload and isinstance(payload["system"], str):
        sys_text = payload["system"]
        msg_text = extract_prompt_text({"messages": payload.get("messages", [])})
        return f"{sys_text}\n{msg_text}".strip()

    # 3. Gemini format: {"contents": [{"parts": [{"text": "..."}]}]}
    if "contents" in payload and isinstance(payload["contents"], list):
        parts = []
        for item in payload["contents"]:
            for part in item.get("parts", []):
                if "text" in part:
                    parts.append(part["text"])
        return "\n".join(parts)

    # 4. Standard completion format: {"prompt": "..."}
    if "prompt" in payload and isinstance(payload["prompt"], str):
        return payload["prompt"]

    return json.dumps(payload)


def update_telemetry(record: PromptInspectionRecord):
    """Updates fleet-wide metrics and unit-economics cost counters."""
    TELEMETRY.total_scans += 1
    if record.applied_action == InterventionAction.ALLOW:
        TELEMETRY.passed_count += 1
    elif record.applied_action == InterventionAction.SILENT_LOG:
        TELEMETRY.logged_count += 1
    elif record.applied_action == InterventionAction.NUDGE:
        TELEMETRY.nudged_count += 1
    elif record.applied_action == InterventionAction.REDACT:
        TELEMETRY.redacted_count += 1
    elif record.applied_action == InterventionAction.BLOCK:
        TELEMETRY.blocked_count += 1

    if record.ast_analysis.is_synthetic_test_fixture and record.applied_action == InterventionAction.ALLOW:
        TELEMETRY.ast_false_positives_eliminated += 1

    client_key = record.client_identity.client_name
    TELEMETRY.active_developer_clients[client_key] = (
        TELEMETRY.active_developer_clients.get(client_key, 0) + 1
    )

    # Cost tracking: Jev System 1 ($0.00001) vs. traditional SLM GPU ensemble ($0.0005 per check)
    TELEMETRY.actual_system1_cost_usd = round(TELEMETRY.total_scans * 0.00001, 5)
    TELEMETRY.projected_slm_gpu_cost_usd = round(TELEMETRY.total_scans * 0.0005, 5)
    TELEMETRY.estimated_cost_savings_usd = round(
        max(0.0, TELEMETRY.projected_slm_gpu_cost_usd - TELEMETRY.actual_system1_cost_usd), 5
    )

    # Latency tracking
    n = TELEMETRY.total_scans
    prev_mean = TELEMETRY.mean_jev_latency_ms
    current_latency = record.jev_evaluation.eval_time_ms + record.ast_analysis.analysis_time_ms
    TELEMETRY.mean_jev_latency_ms = round(((prev_mean * (n - 1)) + current_latency) / n, 2)


def create_demo_incident(
    incident_id: str,
    client_name: str,
    client_type: ClientType,
    prompt_text: str,
    action: InterventionAction,
    classification: DataClassification,
    raw_urgency: float,
    calibrated_urgency: float,
    is_mock: bool = False,
    mock_penalty: float = 1.0,
    reasoning: str = "",
) -> PromptInspectionRecord:
    """Constructs a deterministic demo incident record for testing and pre-seeding."""
    return PromptInspectionRecord(
        incident_id=incident_id,
        client_identity=ClientIdentity(
            client_type=client_type,
            client_name=client_name,
            detected_via="ROUTE_PROFILE",
        ),
        endpoint_path="/v1/chat/completions",
        target_provider="OPENAI",
        extracted_prompt_text=prompt_text,
        token_count=len(prompt_text.split()),
        ast_analysis=ASTAnalysisResult(
            has_code=True,
            language="python",
            ast_parsable=True,
            is_synthetic_test_fixture=is_mock,
            confidence_penalty=mock_penalty,
            reason="Synthetic test scope detected" if is_mock else "No mock fixture detected",
        ),
        jev_evaluation=JevEvaluation(
            engine_used="JEV_SIMULATED",
            is_synthetic_or_mock_prob=0.99 if is_mock else 0.05,
            data_classification=classification,
            classification_probabilities={
                classification.value: 0.88,
                "Clean_Code_Or_Chat": 0.08 if classification != DataClassification.CLEAN_CODE_OR_CHAT else 0.88,
                "Synthetic_Test_Fixture": 0.02 if classification != DataClassification.SYNTHETIC_TEST_FIXTURE else 0.88,
                "Customer_PII": 0.01 if classification != DataClassification.CUSTOMER_PII else 0.88,
                "Live_API_Secret": 0.01 if classification != DataClassification.LIVE_API_SECRET else 0.88,
            },
            raw_urgency_score=raw_urgency,
            calibrated_urgency_score=calibrated_urgency,
            eval_time_ms=11.5,
            action_taken=action,
            reasoning_summary=reasoning,
        ),
        applied_action=action,
        total_pipeline_latency_ms=14.2,
    )


def seed_demo_incidents() -> List[PromptInspectionRecord]:
    """Generates the baseline demo incidents including inc_demo_01."""
    return [
        create_demo_incident(
            incident_id="inc_demo_01",
            client_name="Direct API / curl",
            client_type=ClientType.DIRECT_CURL,
            prompt_text="Fix this S3 error: AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE' and AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
            action=InterventionAction.BLOCK,
            classification=DataClassification.LIVE_API_SECRET,
            raw_urgency=0.98,
            calibrated_urgency=0.98,
            is_mock=False,
            mock_penalty=1.0,
            reasoning="[JEV_SIMULATED] Critical policy violation (0.98 >= 0.92): Live_API_Secret",
        ),
        create_demo_incident(
            incident_id="inc_demo_02",
            client_name="Claude Desktop (MCP)",
            client_type=ClientType.CLAUDE_DESKTOP,
            prompt_text="Draft customer dispute response for Alice Walker (DOB: 1982-04-14, address: 24 Elm Terrace, Bristol BS8 1TH, account #9921-0021).",
            action=InterventionAction.NUDGE,
            classification=DataClassification.CUSTOMER_PII,
            raw_urgency=0.85,
            calibrated_urgency=0.85,
            is_mock=False,
            mock_penalty=1.0,
            reasoning="[JEV_SIMULATED] Moderate compliance alert (0.85 >= 0.80): Customer_PII",
        ),
        create_demo_incident(
            incident_id="inc_demo_03",
            client_name="Cursor IDE",
            client_type=ClientType.CURSOR,
            prompt_text="def test_stripe_webhook(): mock_ssn = '987-65-4321'; fake_stripe_key = 'sk_test_fake991283'; assert client.post('/webhook').status_code == 400",
            action=InterventionAction.ALLOW,
            classification=DataClassification.SYNTHETIC_TEST_FIXTURE,
            raw_urgency=0.85,
            calibrated_urgency=0.04,
            is_mock=True,
            mock_penalty=0.05,
            reasoning="[JEV_SIMULATED] AST eliminated false positive: synthetic fixture discounted from 0.85 to 0.04",
        ),
    ]


def ensure_demo_incidents() -> None:
    """Ensures inc_demo_01 and baseline incidents are present in INCIDENTS."""
    existing_ids = {inc.incident_id for inc in INCIDENTS}
    if "inc_demo_01" not in existing_ids:
        for demo in seed_demo_incidents():
            if demo.incident_id not in existing_ids:
                INCIDENTS.append(demo)
                update_telemetry(demo)
                existing_ids.add(demo.incident_id)


# Seed initial demo incidents on startup
for _demo in seed_demo_incidents():
    INCIDENTS.append(_demo)
    update_telemetry(_demo)


async def execute_prompt_inspection_pipeline(
    request: Request,
    raw_body: bytes,
    endpoint_path: str,
    target_provider: str = "OPENAI",
    client_name_override: Optional[str] = None,
) -> PromptInspectionRecord:
    """Core orchestration pipeline: Fingerprint -> AST Parse -> Jev Gatekeeper -> Enforcement."""
    pipeline_start = time.perf_counter()

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        payload = {}

    client_id = identify_client(request, payload)
    if client_name_override:
        from app.gateway.fingerprint import ROUTE_PROFILE_MAP
        matched = False
        for k, (c_type, c_name) in ROUTE_PROFILE_MAP.items():
            if k == client_name_override.lower():
                client_id.client_type = c_type
                client_id.client_name = c_name
                client_id.detected_via = "ROUTE_PROFILE"
                matched = True
                break
        if not matched:
            client_id.client_name = client_name_override


    prompt_text = extract_prompt_text(payload)

    # 1. AST Syntax Context Analysis
    ast_result = parse_and_audit_code(prompt_text)

    # 2. Jev System 1 Evaluation (Simulated or Live TypeSafe AI API)
    jev_eval = await evaluate_prompt_with_jev(
        prompt_text=prompt_text,
        ast_res=ast_result,
        client_name=client_id.client_name,
    )

    record = PromptInspectionRecord(
        client_identity=client_id,
        endpoint_path=endpoint_path,
        target_provider=target_provider,
        extracted_prompt_text=prompt_text[:1000],
        token_count=len(prompt_text.split()),
        ast_analysis=ast_result,
        jev_evaluation=jev_eval,
        applied_action=jev_eval.action_taken,
        total_pipeline_latency_ms=round((time.perf_counter() - pipeline_start) * 1000, 2),
    )

    INCIDENTS.append(record)
    update_telemetry(record)
    return record


# =====================================================================
# PROXY & INSPECTION ENDPOINTS
# =====================================================================


@app.post("/v1/chat/completions")
@app.post("/proxy/{client_name}/v1/chat/completions")
async def proxy_openai_chat(request: Request, client_name: Optional[str] = None):
    """OpenAI-compatible Chat Completion proxy endpoint."""
    body_bytes = await request.body()
    record = await execute_prompt_inspection_pipeline(
        request=request,
        raw_body=body_bytes,
        endpoint_path=request.url.path,
        target_provider="OPENAI",
        client_name_override=client_name,
    )

    if record.applied_action == InterventionAction.BLOCK:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "message": f"Blocked by Jev Gatekeeper: {record.jev_evaluation.reasoning_summary}",
                    "type": "policy_violation",
                    "code": "jev_aidr_policy_block",
                    "incident_id": record.incident_id,
                    "client": record.client_identity.client_name,
                    "calibrated_risk_score": record.jev_evaluation.calibrated_urgency_score,
                }
            },
        )

    if settings.openai_api_key:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                target_url = f"{settings.openai_base_url}/chat/completions"
                resp = await client.post(
                    target_url,
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    content=body_bytes,
                )
                record.upstream_status_code = resp.status_code
                return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception:
            pass

    nudge_prefix = ""
    if record.applied_action == InterventionAction.NUDGE:
        nudge_prefix = (
            "⚠️ [Security Notice: Jev Gatekeeper detected sensitive reference in your prompt. "
            "Proceeding in compliance with enterprise acceptable-use policy.]\n\n"
        )

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"{nudge_prefix}Processed successfully via Jev Gatekeeper (Client: {record.client_identity.client_name}, Action: {record.applied_action}).",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": record.token_count, "completion_tokens": 24, "total_tokens": record.token_count + 24},
        "x_jev_aidr": {
            "incident_id": record.incident_id,
            "action": record.applied_action,
            "risk_score": record.jev_evaluation.calibrated_urgency_score,
            "pipeline_time_ms": record.total_pipeline_latency_ms,
        },
    }


@app.post("/v1/messages")
@app.post("/proxy/{client_name}/v1/messages")
async def proxy_anthropic_messages(request: Request, client_name: Optional[str] = None):
    """Anthropic-compatible Messages proxy endpoint."""
    body_bytes = await request.body()
    record = await execute_prompt_inspection_pipeline(
        request=request,
        raw_body=body_bytes,
        endpoint_path=request.url.path,
        target_provider="ANTHROPIC",
        client_name_override=client_name,
    )

    if record.applied_action == InterventionAction.BLOCK:
        return JSONResponse(
            status_code=403,
            content={
                "type": "error",
                "error": {
                    "type": "permission_error",
                    "message": f"Blocked by Jev Gatekeeper: {record.jev_evaluation.reasoning_summary}",
                    "incident_id": record.incident_id,
                },
            },
        )

    nudge_prefix = ""
    if record.applied_action == InterventionAction.NUDGE:
        nudge_prefix = "⚠️ [Jev Security Notice: Prompt reviewed and allowed with inline compliance monitoring.]\n\n"

    return {
        "id": f"msg_{uuid.uuid4().hex[:16]}",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": f"{nudge_prefix}Anthropic response simulated via Jev Gatekeeper (Action: {record.applied_action}).",
            }
        ],
        "model": "claude-3-5-sonnet",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": record.token_count, "output_tokens": 20},
    }


@app.post("/api/v1/inspect", response_model=PromptInspectionRecord)
async def direct_inspect_prompt(request: Request):
    """Direct programmatic inspection endpoint for security auditing and testing."""
    body_bytes = await request.body()
    return await execute_prompt_inspection_pipeline(
        request=request,
        raw_body=body_bytes,
        endpoint_path="/api/v1/inspect",
    )


@app.post("/api/v1/sandbox/inject-preset")
async def inject_preset(req: InjectPresetRequest, request: Request):
    """Injects one of the 5 Golden Presets or a custom scenario into the pipeline."""
    if req.preset_id not in AIDR_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown preset_id '{req.preset_id}'. Valid presets: {list(AIDR_PRESETS.keys())}",
        )

    preset = AIDR_PRESETS[req.preset_id]
    prompt = req.custom_prompt or preset.prompt_text
    client_label = req.target_client or preset.target_client

    payload = {"messages": [{"role": "user", "content": prompt}]}
    raw_body = json.dumps(payload).encode("utf-8")

    record = await execute_prompt_inspection_pipeline(
        request=request,
        raw_body=raw_body,
        endpoint_path=f"/api/v1/sandbox/preset/{req.preset_id}",
        target_provider="SIMULATED_LOCAL",
        client_name_override=client_label,
    )

    return {
        "preset": preset,
        "record": record,
        "telemetry": TELEMETRY,
    }


@app.get("/api/v1/presets")
async def list_presets():
    """Lists available pre-configured test scenarios."""
    return AIDR_PRESETS


@app.get("/api/v1/sandbox/policy")
async def get_policy():
    """Returns current Jev Engine Mode, API key status, and Policy Thresholds."""
    return {
        "jev_mode": settings.jev_mode,
        "has_typesafe_api_key": bool(settings.typesafe_api_key),
        "typesafe_api_url": settings.typesafe_api_url,
        "allow_threshold": settings.allow_threshold,
        "silent_log_threshold": settings.silent_log_threshold,
        "nudge_threshold": settings.nudge_threshold,
        "redact_threshold": settings.redact_threshold,
        "block_threshold": settings.block_threshold,
        "ambiguity_margin": settings.ambiguity_margin,
    }


@app.put("/api/v1/sandbox/policy")
async def update_policy(req: PolicyUpdateRequest):
    """Dynamically updates Jev Engine Mode and Policy Thresholds."""
    if req.jev_mode is not None:
        settings.jev_mode = req.jev_mode
    if req.allow_threshold is not None:
        settings.allow_threshold = req.allow_threshold
    if req.silent_log_threshold is not None:
        settings.silent_log_threshold = req.silent_log_threshold
    if req.nudge_threshold is not None:
        settings.nudge_threshold = req.nudge_threshold
    if req.redact_threshold is not None:
        settings.redact_threshold = req.redact_threshold
    if req.block_threshold is not None:
        settings.block_threshold = req.block_threshold
    if req.ambiguity_margin is not None:
        settings.ambiguity_margin = req.ambiguity_margin

    return {
        "status": "Policy updated successfully",
        "current_policy": {
            "jev_mode": settings.jev_mode,
            "allow_threshold": settings.allow_threshold,
            "silent_log_threshold": settings.silent_log_threshold,
            "nudge_threshold": settings.nudge_threshold,
            "redact_threshold": settings.redact_threshold,
            "block_threshold": settings.block_threshold,
            "ambiguity_margin": settings.ambiguity_margin,
        },
    }


@app.get("/api/v1/telemetry", response_model=FleetTelemetrySummary)
async def get_telemetry():
    """Returns aggregated real-time AIDR telemetry and economic cost-saving metrics."""
    return TELEMETRY


@app.get("/api/v1/incidents", response_model=List[PromptInspectionRecord])
async def list_incidents(limit: int = 50):
    """Returns the most recent inspection incidents and AST analyses."""
    return INCIDENTS[-limit:]


@app.post("/api/v1/reset")
async def reset_telemetry(admin_key: Optional[str] = None):
    """Resets audit incidents and telemetry counters."""
    if admin_key != settings.admin_key:
        raise HTTPException(status_code=403, detail="Forbidden: Valid admin key required.")

    INCIDENTS.clear()
    global TELEMETRY
    TELEMETRY = FleetTelemetrySummary()
    for _demo in seed_demo_incidents():
        INCIDENTS.append(_demo)
        update_telemetry(_demo)
    return {"status": "Telemetry and incident audit stream reset to clean state with baseline demo incidents."}


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "jev_mode": settings.jev_mode,
        "incidents_logged": len(INCIDENTS),
    }


# =====================================================================
# FASTMCP SERVER PROCESS MOUNT & HTTP 405 SAFEGUARD
# =====================================================================


@app.post("/mcp/sse")
async def handle_mcp_sse_post():
    """Explicit dummy POST handler preventing HTTP 405 Method Not Allowed in mcp-remote bridge."""
    raise HTTPException(
        status_code=404,
        detail="The /mcp/sse endpoint is a Server-Sent Events (SSE) stream requiring HTTP GET. Pass '--transport sse-only' to mcp-remote.",
    )


# Mount the FastMCP SSE app directly at /mcp
app.mount("/mcp", mcp.sse_app(transport_security=MCP_TRANSPORT_SECURITY))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.gateway.proxy:app", host="0.0.0.0", port=8000, reload=True)
