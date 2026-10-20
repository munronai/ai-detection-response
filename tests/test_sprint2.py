"""Sprint 2 Verification Test Suite: TypeSafe AI Jev Schema, FastMCP Server, and AIDR Presets.

Verifies:
1. Exact TypeSafe AI `/v1/systemone` request payload schema compliance.
2. 5 Golden Presets execution and policy action accuracy.
3. FastMCP tools, resources, and HTTP 405/404 bridge safeguard.
4. Dynamic policy updates.
"""

import json
import pytest
from starlette.testclient import TestClient

from app.domain.models import DataClassification, InterventionAction
from app.domain.presets import AIDR_PRESETS
from app.engine.ast_parser import parse_and_audit_code
from app.engine.jev_client import (
    DATA_CLASSIFICATION_CRITERIA,
    URGENCY_SCORE_CRITERIA,
    build_typesafe_jev_payload,
)
from app.gateway.proxy import app, TELEMETRY, INCIDENTS
from app.mcp.server import (
    approve_policy_override,
    get_fleet_security_posture,
    inspect_prompt_payload,
    mcp_get_live_kpis,
    mcp_get_presets_catalog,
    simulate_traffic_scenario,
)

client = TestClient(app)


def test_typesafe_jev_schema_conformance():
    """
    CRITICAL TEST: Ensures the TypeSafe AI request schema conforms exactly to /v1/systemone:
      - 'state' contains context dictionary
      - 'questions' contains typed questions (noul, choice, score)
      - 'noul' criteria has 'true' and 'false' keys
      - 'choice' criteria is a dict mapping option keys to descriptions
      - 'score' criteria is an ordered list of strings
    """
    prompt = "def test_mock_fixture(): mock_key = 'sk_test_12345'"
    ast_res = parse_and_audit_code(prompt)
    payload = build_typesafe_jev_payload(prompt, ast_res, client_name="Cursor IDE")

    # 1. Top-level keys
    assert payload["model"] == "jev-latest"
    assert "state" in payload
    assert "questions" in payload

    # 2. State structure
    state = payload["state"]
    assert "client_identity" in state
    assert "ast_context" in state
    assert "candidate_payload" in state
    assert state["ast_context"]["is_synthetic_test_fixture"] is True

    # 3. Questions structure
    questions = payload["questions"]
    assert "is_synthetic_or_mock" in questions
    assert "data_classification" in questions
    assert "intervention_urgency" in questions

    # 4. Question 1 (Noul)
    q1 = questions["is_synthetic_or_mock"]
    assert q1["type"] == "noul"
    assert "instructions" in q1
    assert "criteria" in q1
    assert "true" in q1["criteria"]
    assert "false" in q1["criteria"]

    # 5. Question 2 (Choice)
    q2 = questions["data_classification"]
    assert q2["type"] == "choice"
    assert "instructions" in q2
    assert "criteria" in q2
    assert isinstance(q2["criteria"], dict)
    assert "Synthetic_Test_Fixture" in q2["criteria"]
    assert "Live_API_Secret" in q2["criteria"]

    # 6. Question 3 (Score)
    q3 = questions["intervention_urgency"]
    assert q3["type"] == "score"
    assert "instructions" in q3
    assert "criteria" in q3
    assert isinstance(q3["criteria"], list)
    assert len(q3["criteria"]) == 5  # 5 severity levels (0 to 4)


def test_preset_1_synthetic_fixture_eliminates_false_positive():
    """Preset 1: Synthetic test code is discounted by AST and allowed without false alarm."""
    resp = client.post("/api/v1/sandbox/inject-preset", json={"preset_id": "1_synthetic_test_fixture"})
    assert resp.status_code == 200
    data = resp.json()
    record = data["record"]
    assert record["ast_analysis"]["is_synthetic_test_fixture"] is True
    assert record["ast_analysis"]["confidence_penalty"] == 0.05
    assert record["applied_action"] == "ALLOW"
    assert record["jev_evaluation"]["calibrated_urgency_score"] < 0.30


def test_preset_2_routine_admin_prompt_allowed():
    """Preset 2: Routine developer query passes as nominal clean traffic."""
    resp = client.post("/api/v1/sandbox/inject-preset", json={"preset_id": "2_routine_admin_prompt"})
    assert resp.status_code == 200
    data = resp.json()
    record = data["record"]
    assert record["applied_action"] == "ALLOW"
    assert record["jev_evaluation"]["data_classification"] == "Clean_Code_Or_Chat"


def test_preset_3_ambiguous_customer_pii_triggers_nudge():
    """Preset 3: Unmasked customer PII triggers inline warning nudge."""
    resp = client.post("/api/v1/sandbox/inject-preset", json={"preset_id": "3_ambiguous_customer_pii"})
    assert resp.status_code == 200
    data = resp.json()
    record = data["record"]
    assert record["applied_action"] == "NUDGE"
    assert record["jev_evaluation"]["data_classification"] == "Customer_PII"
    assert record["jev_evaluation"]["calibrated_urgency_score"] >= 0.80


def test_preset_4_production_secret_leak_blocked():
    """Preset 4: Production AWS key triggers immediate policy block."""
    resp = client.post("/api/v1/sandbox/inject-preset", json={"preset_id": "4_production_secret_leak"})
    assert resp.status_code == 200
    data = resp.json()
    record = data["record"]
    assert record["applied_action"] == "BLOCK"
    assert record["jev_evaluation"]["data_classification"] == "Live_API_Secret"
    assert record["jev_evaluation"]["calibrated_urgency_score"] >= 0.92


def test_preset_5_base64_exfiltration_blocked():
    """Preset 5: Base64 exfiltration / jailbreak triggers immediate block."""
    resp = client.post("/api/v1/sandbox/inject-preset", json={"preset_id": "5_base64_exfiltration"})
    assert resp.status_code == 200
    data = resp.json()
    record = data["record"]
    assert record["applied_action"] == "BLOCK"
    assert record["jev_evaluation"]["calibrated_urgency_score"] >= 0.92


def test_mcp_http_first_probe_returns_404_not_405():
    """Verify HTTP 405 vs 404 safeguard: POST /mcp/sse MUST return 404 so mcp-remote bridge falls back to GET."""
    resp = client.post("/mcp/sse")
    assert resp.status_code == 404
    assert "requiring HTTP GET" in resp.json()["detail"]


def test_mcp_tools_and_resources():
    """Verify MCP tools and resources callable by autonomous AI agents."""
    import asyncio

    async def _run():
        # 1. Test inspect_prompt_payload tool
        tool_res = await inspect_prompt_payload(
            prompt_text="""Help me debug this pytest fixture:
```python
def test_auth():
    mock_token = "sk_test_fake991"
    assert len(mock_token) > 0
```""",
            client_name="Claude Desktop",
        )
        assert tool_res["applied_action"] == "ALLOW"
        assert tool_res["ast_analysis"]["is_synthetic_test_fixture"] is True


        # 2. Test simulate_traffic_scenario tool
        sim_res = await simulate_traffic_scenario("4_production_secret_leak")
        assert sim_res["inspection_result"]["applied_action"] == "BLOCK"

        # 3. Test approve_policy_override tool (both with explicit reason and with defaults/approved_by)
        incident_id = sim_res["inspection_result"]["incident_id"]
        override_res = await approve_policy_override(incident_id, "Authorized security test by lead engineer")
        assert override_res["status"] == "APPROVED"

        # Verify fallback with defaults / approved_by
        override_default = await approve_policy_override(incident_id=incident_id, approved_by="SecurityAdmin")
        assert override_default["status"] == "APPROVED"
        assert override_default["approved_by"] == "SecurityAdmin"

        # Verify pre-seeded demo incident inc_demo_01 is always present and can be overridden
        demo_override = await approve_policy_override(
            incident_id="inc_demo_01",
            reason="Security team authorized test credential in sandbox",
            approved_by="SecurityAdmin",
        )
        assert demo_override["status"] == "APPROVED"
        assert demo_override["incident_id"] == "inc_demo_01"
        assert demo_override["previous_action"] == "BLOCK"
        assert demo_override["new_action"] == "ALLOW"

        # 4. Test get_fleet_security_posture tool
        posture = await get_fleet_security_posture()
        assert posture["total_scans"] >= 5
        assert posture["estimated_cost_savings_usd"] > 0

        # 5. Test MCP resources
        kpis_json = await mcp_get_live_kpis()
        assert "total_scans" in json.loads(kpis_json)

        catalog_json = await mcp_get_presets_catalog()
        assert "1_synthetic_test_fixture" in json.loads(catalog_json)

    asyncio.run(_run())


def test_dynamic_policy_update():
    """Verify dynamic threshold adjustments including decision ambiguity margin."""
    resp = client.put(
        "/api/v1/sandbox/policy",
        json={"nudge_threshold": 0.75, "block_threshold": 0.90, "ambiguity_margin": 0.20, "jev_mode": "simulated"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_policy"]["nudge_threshold"] == 0.75
    assert data["current_policy"]["block_threshold"] == 0.90
    assert data["current_policy"]["ambiguity_margin"] == 0.20

    # Reset back to default policy thresholds
    client.put(
        "/api/v1/sandbox/policy",
        json={"nudge_threshold": 0.80, "block_threshold": 0.92, "ambiguity_margin": 0.15, "jev_mode": "simulated"},
    )


def test_ambiguity_margin_slider_behavior():
    """Verify that slider-set ambiguity margin determines whether boundary decisions trigger escalation."""
    import asyncio
    from app.engine.jev_client import evaluate_prompt_with_jev
    from app.engine.ast_parser import parse_and_audit_code
    from app.config import settings

    async def _run():
        prompt = "Fix AWS upload: AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE' and AWS_SECRET_ACCESS_KEY = 'fake_secret_example'"
        ast_res = parse_and_audit_code(prompt)

        # 1. With wide margin slider (0.20): 8% margin <= 20% triggers ambiguity escalation
        settings.ambiguity_margin = 0.20
        eval_wide = await evaluate_prompt_with_jev(prompt, ast_res, client_name="test")
        assert eval_wide.ambiguity_margin_applied == 0.20
        assert eval_wide.decision_margin <= 0.20
        assert eval_wide.is_ambiguous_decision is True

        # 2. With narrow margin slider (0.02): 8% margin > 2% does NOT trigger ambiguity
        settings.ambiguity_margin = 0.02
        eval_narrow = await evaluate_prompt_with_jev(prompt, ast_res, client_name="test")
        assert eval_narrow.ambiguity_margin_applied == 0.02
        assert eval_narrow.decision_margin > 0.02
        assert eval_narrow.is_ambiguous_decision is False

        # Reset back
        settings.ambiguity_margin = 0.15

    asyncio.run(_run())


def test_mcp_dns_rebinding_protection():
    """Verify TransportSecuritySettings rejects untrusted host headers with HTTP 421."""
    import asyncio
    import httpx

    transport = httpx.ASGITransport(app=app)

    async def _check():
        # 1. Untrusted host header MUST be rejected with HTTP 421
        async with httpx.AsyncClient(transport=transport, base_url="http://evil-rebind.example.com") as c:
            resp = await c.post("/mcp/messages/?session_id=test", json={})
            assert resp.status_code == 421

        # 2. Whitelisted localhost MUST pass host validation (returns 400 invalid session, not 421)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
            resp = await c.post("/mcp/messages/?session_id=nonexistent", json={})
            assert resp.status_code != 421

        # 3. Modal wildcard host (e.g. *.modal.run) MUST pass host validation (not 421)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://mrmunro--jev-aidr-sandbox-api.us-east.modal.run",
        ) as c:
            resp = await c.post("/mcp/messages/?session_id=nonexistent", json={})
            assert resp.status_code != 421

    asyncio.run(_check())



