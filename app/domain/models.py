"""Domain models and schemas for the AIDR Gateway."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ClientType(str, Enum):
    CURSOR = "Cursor"
    COPILOT = "VS Code Copilot"
    CLAUDE_DESKTOP = "Claude Desktop"
    ANTIGRAVITY_CLI = "Google Antigravity CLI"
    DIRECT_CURL = "Direct API / curl"
    PYTHON_SDK = "Python SDK / Backend Service"
    UNKNOWN = "Unknown Client"


class DataClassification(str, Enum):
    CLEAN_CODE_OR_CHAT = "Clean_Code_Or_Chat"
    SYNTHETIC_TEST_FIXTURE = "Synthetic_Test_Fixture"
    CUSTOMER_PII = "Customer_PII"
    LIVE_API_SECRET = "Live_API_Secret"
    PROPRIETARY_CORE_IP = "Proprietary_Core_IP"


class InterventionAction(str, Enum):
    ALLOW = "ALLOW"
    SILENT_LOG = "SILENT_LOG"
    NUDGE = "NUDGE"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


class ClientIdentity(BaseModel):
    client_type: ClientType = ClientType.UNKNOWN
    client_name: str = "Unknown"
    client_version: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    tls_fingerprint_ja4: Optional[str] = None
    detected_via: Literal["ROUTE_PROFILE", "USER_AGENT", "SCHEMA_MORPHOLOGY", "MCP_HANDSHAKE"] = "SCHEMA_MORPHOLOGY"
    account_email: Optional[str] = None


class SyntheticFixtureDetail(BaseModel):
    identifier: str
    scope_type: Literal["test_function", "pytest_fixture", "mock_assignment", "synthetic_identifier"]
    value_snippet: str
    is_mock: bool = True


class ASTAnalysisResult(BaseModel):
    has_code: bool = False
    language: Optional[str] = None
    ast_parsable: bool = False
    is_synthetic_test_fixture: bool = False
    test_function_count: int = 0
    mock_frameworks: List[str] = Field(default_factory=list)
    fixtures: List[SyntheticFixtureDetail] = Field(default_factory=list)
    confidence_penalty: float = Field(
        1.0,
        description="Multiplier on risk score. Drops to 0.05 when AST confirms content is purely synthetic mock data.",
    )
    analysis_time_ms: float = 0.0
    reason: str = "No code detected"


class JevEvaluation(BaseModel):
    engine_used: Literal["JEV_SIMULATED", "JEV_LIVE_API"] = "JEV_SIMULATED"
    is_synthetic_or_mock_prob: float = Field(..., description="Calibrated Noul probability that payload is mock data")
    data_classification: DataClassification = DataClassification.CLEAN_CODE_OR_CHAT
    raw_urgency_score: float = Field(..., description="Raw Jev calibrated urgency score 0.0..1.0")
    calibrated_urgency_score: float = Field(
        ...,
        description="Discounted urgency score after applying AST synthetic context penalty",
    )
    eval_time_ms: float = 0.0
    action_taken: InterventionAction = InterventionAction.ALLOW
    reasoning_summary: str = ""
    estimated_inference_cost_usd: float = 0.00001


class PromptInspectionRecord(BaseModel):
    incident_id: str = Field(default_factory=lambda: f"inc_{uuid.uuid4().hex[:8]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    client_identity: ClientIdentity
    endpoint_path: str
    target_provider: Literal["OPENAI", "ANTHROPIC", "GEMINI", "SIMULATED_LOCAL"] = "OPENAI"
    extracted_prompt_text: str
    extracted_code_snippets: List[str] = Field(default_factory=list)
    token_count: int = 0
    ast_analysis: ASTAnalysisResult
    jev_evaluation: JevEvaluation
    applied_action: InterventionAction
    redacted_prompt: Optional[str] = None
    nudge_message: Optional[str] = None
    upstream_status_code: Optional[int] = None
    upstream_latency_ms: Optional[float] = None
    total_pipeline_latency_ms: float = 0.0


class FleetTelemetrySummary(BaseModel):
    total_scans: int = 0
    passed_count: int = 0
    logged_count: int = 0
    nudged_count: int = 0
    redacted_count: int = 0
    blocked_count: int = 0
    ast_false_positives_eliminated: int = 0
    active_developer_clients: Dict[str, int] = Field(default_factory=dict)
    mean_jev_latency_ms: float = 0.0
    mean_traditional_slm_latency_ms: float = 145.0
    actual_system1_cost_usd: float = 0.0
    projected_slm_gpu_cost_usd: float = 0.0
    estimated_cost_savings_usd: float = 0.0
