"""Sprint 1 End-to-End Verification Test Suite.

Tests:
1. AST Parser: Synthetic test fixtures vs. production secret detection.
2. Client Fingerprinting: User-Agent, schema morphology, and virtual route profiles.
3. FastAPI Reverse Proxy: Interception, policy enforcement (Allow vs Block), and telemetry.
"""

import pytest
from starlette.testclient import TestClient

from app.domain.models import ClientType, DataClassification, InterventionAction
from app.engine.ast_parser import parse_and_audit_code
from app.gateway.proxy import app, TELEMETRY, INCIDENTS


client = TestClient(app)


def test_ast_parser_detects_synthetic_fixture():
    """Verify that unit test scopes with mock variables receive a 95% risk discount."""
    code_snippet = """
def test_stripe_webhook_failure():
    mock_customer_ssn = "987-65-4321"
    fake_stripe_key = "sk_test_51MzFakeKeyNotRealEntropyCheck001"
    response = client.post("/webhook", json={"ssn": mock_customer_ssn, "key": fake_stripe_key})
    assert response.status_code == 400
"""
    result = parse_and_audit_code(code_snippet)
    assert result.has_code is True
    assert result.ast_parsable is True
    assert result.is_synthetic_test_fixture is True
    assert result.confidence_penalty == 0.05
    assert len(result.fixtures) >= 1
    assert any("mock_customer_ssn" in f.identifier or "fake_stripe_key" in f.identifier for f in result.fixtures)


def test_ast_parser_flags_production_code_without_discount():
    """Verify that production code with high-entropy keys is NOT flagged as synthetic fixture."""
    code_snippet = """
def authenticate_production_service():
    client_id = "prod_client_live_001"
    raw_secret = "AKIAIOSFODNN7EXAMPLE"
    return establish_connection(client_id, raw_secret)
"""
    result = parse_and_audit_code(code_snippet)
    assert result.has_code is True
    assert result.is_synthetic_test_fixture is False
    assert result.confidence_penalty == 1.0


def test_ast_parser_handles_plain_natural_language():
    """Verify that pure conversational text returns has_code=False."""
    text = "Can you summarize the difference between DeBERTa and ModernBERT for classification?"
    result = parse_and_audit_code(text)
    assert result.has_code is False
    assert result.is_synthetic_test_fixture is False
    assert result.confidence_penalty == 1.0


def test_proxy_fingerprints_user_agent_and_route():
    """Verify client identification via User-Agent and virtual route profiles."""
    # 1. Cursor User-Agent
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "Hello world"}]},
        headers={"User-Agent": "Cursor/0.42.1 (Macintosh; Intel Mac OS X)"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Processed successfully" in data["choices"][0]["message"]["content"]
    assert "Cursor" in data["choices"][0]["message"]["content"]

    # 2. Virtual Route Profile for Copilot
    resp_copilot = client.post(
        "/proxy/copilot/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "How do I reverse a list in Python?"}]},
    )
    assert resp_copilot.status_code == 200
    data_copilot = resp_copilot.json()
    assert "Copilot" in data_copilot["choices"][0]["message"]["content"]


def test_proxy_eliminates_false_positive_on_synthetic_fixture():
    """
    Core AIDR Test: Synthetic test fixtures that would trigger traditional DLP / SLMs
    are verified by AST and ALLOWED through the proxy without false alarm.
    """
    synthetic_payload = {
        "messages": [
            {
                "role": "user",
                "content": """Please review my test case:
```python
def test_user_billing_mock():
    mock_card = "4111-2222-3333-4444"
    dummy_key = "sk_test_fake12345"
    assert process_charge(mock_card, dummy_key) is False
```""",
            }
        ]
    }
    resp = client.post("/v1/chat/completions", json=synthetic_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["x_jev_aidr"]["action"] == "ALLOW"
    assert data["x_jev_aidr"]["risk_score"] < 0.30


def test_proxy_blocks_live_production_credentials():
    """
    Verify that genuine production credentials trigger an immediate HTTP 403 Block.
    """
    leaked_secret_payload = {
        "messages": [
            {
                "role": "user",
                "content": "Deploying with production credentials: AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'",
            }
        ]
    }
    resp = client.post("/v1/chat/completions", json=leaked_secret_payload)
    assert resp.status_code == 403
    err_data = resp.json()
    assert err_data["error"]["type"] == "policy_violation"
    assert "Blocked by Jev Gatekeeper" in err_data["error"]["message"]


def test_telemetry_endpoint():
    """Verify aggregated telemetry metrics reflect recent scans."""
    resp = client.get("/api/v1/telemetry")
    assert resp.status_code == 200
    telemetry = resp.json()
    assert telemetry["total_scans"] >= 4
    assert telemetry["blocked_count"] >= 1
    assert telemetry["ast_false_positives_eliminated"] >= 1
    assert telemetry["estimated_cost_savings_usd"] > 0
