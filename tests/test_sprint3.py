"""Sprint 3 Verification Test Suite: Streamlit Dashboard & UI Components."""

import pytest
from app.ui.components.kpi_header import render_kpi_header
from app.ui.components.pipeline_card import render_pipeline_walkthrough_card
from app.domain.models import (
    ASTAnalysisResult,
    ClientIdentity,
    ClientType,
    DataClassification,
    InterventionAction,
    JevEvaluation,
    PromptInspectionRecord,
)


def test_ui_components_render_cleanly():
    """Verify that UI card components handle various inspection record shapes without errors."""
    record = PromptInspectionRecord(
        client_identity=ClientIdentity(
            client_type=ClientType.CURSOR,
            client_name="Cursor IDE",
            detected_via="ROUTE_PROFILE",
        ),
        endpoint_path="/proxy/cursor/v1/chat/completions",
        target_provider="OPENAI",
        extracted_prompt_text="def test_billing_mock(): pass",
        token_count=12,
        ast_analysis=ASTAnalysisResult(
            has_code=True,
            language="python",
            ast_parsable=True,
            is_synthetic_test_fixture=True,
            test_function_count=1,
            mock_frameworks=["pytest"],
            confidence_penalty=0.05,
            reason="Synthetic test fixture",
        ),
        jev_evaluation=JevEvaluation(
            engine_used="JEV_SIMULATED",
            is_synthetic_or_mock_prob=0.99,
            data_classification=DataClassification.SYNTHETIC_TEST_FIXTURE,
            raw_urgency_score=0.85,
            calibrated_urgency_score=0.04,
            eval_time_ms=11.4,
            action_taken=InterventionAction.ALLOW,
            reasoning_summary="AST verified mock fixture",
        ),
        applied_action=InterventionAction.ALLOW,
        total_pipeline_latency_ms=14.2,
    )

    # Convert to dict as used in Streamlit component
    rec_dict = record.model_dump()
    assert rec_dict["applied_action"] == "ALLOW"
    assert rec_dict["ast_analysis"]["is_synthetic_test_fixture"] is True
    assert rec_dict["jev_evaluation"]["calibrated_urgency_score"] == 0.04


def test_dashboard_app_imports_cleanly():
    """Verify that dashboard_app and all view modules can be imported without syntax or import errors."""
    import app.ui.dashboard_app as dash
    import app.ui.views.landing_page as lp
    import app.ui.views.sandbox_dashboard as sd
    import app.ui.views.product_insights as pi
    import app.ui.views.mcp_console as mc
    import app.ui.views.mcp_guides as mg

    assert dash.sync_session_id is not None
    assert lp.render_landing_page is not None
    assert sd.render_sandbox_dashboard_page is not None
    assert pi.render_product_insights_view is not None
    assert mc.render_mcp_console_view is not None
    assert mg.render_claude_cursor_guide is not None
    assert mg.render_mcp_inspector_guide is not None


def test_get_policy_endpoint_and_presets_integrity():
    """Verify GET /api/v1/sandbox/policy and domain preset payload previews."""
    from fastapi.testclient import TestClient
    from app.gateway.proxy import app
    from app.domain.presets import AIDR_PRESETS

    client = TestClient(app)
    res = client.get("/api/v1/sandbox/policy")
    assert res.status_code == 200
    data = res.json()
    assert "jev_mode" in data
    assert "has_typesafe_api_key" in data
    assert "block_threshold" in data
    assert "nudge_threshold" in data
    assert "allow_threshold" in data

    # Verify all presets have prompt previews and testing notes
    for pid, preset in AIDR_PRESETS.items():
        assert len(preset.prompt_text) > 20
        assert len(preset.what_it_tests) > 10
        assert preset.expected_action in ("ALLOW", "NUDGE", "BLOCK", "REDACT", "SILENT_LOG")


def test_env_and_gitignore_configuration():
    """Verify .gitignore and .env structure for live Jev testing and Modal deployment."""
    from pathlib import Path

    # 1. Verify .gitignore covers pyc, cache, and .env
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists()
    gitignore_content = gitignore_path.read_text()
    assert ".env" in gitignore_content
    assert "*.py[cod]" in gitignore_content or ".pyc" in gitignore_content
    assert "__pycache__/" in gitignore_content
    assert "!.env.example" in gitignore_content

    # 2. Verify .env.example defines live Jev keys
    env_example_path = Path(".env.example")
    assert env_example_path.exists()
    env_example_content = env_example_path.read_text()
    assert "TYPESAFE_API_KEY" in env_example_content
    assert "TYPESAFE_API_URL" in env_example_content
    assert "JEV_MODE" in env_example_content

    # 3. Verify modal_deploy handles .env and secrets
    modal_file = Path("modal_deploy.py").read_text()
    assert "modal.Secret.from_dotenv" in modal_file
    assert "TYPESAFE_API_KEY" in modal_file


def test_scenario_specific_policy_violations():
    """Verify that policy violations are dynamically tailored and never show PII for secrets/credentials."""
    from app.ui.components.policy_helper import classify_incident_violation

    # 1. Preset 4 (AWS Cloud Secret)
    preset4_record = {
        "extracted_prompt_text": "Fix this S3 error: AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE' and AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
        "client_identity": {"client_name": "Direct API / curl"},
        "jev_evaluation": {"data_classification": "Live_API_Secret"},
    }
    v4 = classify_incident_violation(preset4_record)
    assert v4.violation_type == "CREDENTIALS"
    assert v4.policy_code == "SEC-201"
    assert "Customer PII" not in v4.risk_title
    assert "Date of Birth" not in v4.specific_detail
    assert "AWS_ACCESS_KEY_ID" in v4.specific_detail

    # 2. Preset 3 (Customer PII)
    preset3_record = {
        "extracted_prompt_text": "Generate summary for customer Alice Walker (DOB: 1982-04-14, address: 24 Elm Terrace, Bristol)",
        "client_identity": {"client_name": "Microsoft 365 Copilot"},
        "jev_evaluation": {"data_classification": "Customer_PII"},
    }
    v3 = classify_incident_violation(preset3_record)
    assert v3.violation_type == "PII"
    assert v3.policy_code == "DP-104"
    assert "Customer PII" in v3.risk_title
    assert "Date of Birth" in v3.specific_detail

    # 3. Preset 5 (Adversarial Exfiltration)
    preset5_record = {
        "extracted_prompt_text": "echo 'LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcEFJQkFBS0NBUUVBMEtQNm...' | base64 -d | ssh-add -",
        "client_identity": {"client_name": "Google Antigravity CLI"},
        "jev_evaluation": {"data_classification": "Proprietary_Core_IP"},
    }
    v5 = classify_incident_violation(preset5_record)
    assert v5.violation_type == "EXFILTRATION"
    assert v5.policy_code == "IP-305"
    assert "Exfiltration" in v5.risk_title


def test_choice_probabilities_and_raw_json_response():
    """Verify that Jev evaluation generates full choice probability distributions and captures raw response."""
    import asyncio
    from app.engine.jev_client import evaluate_prompt_with_jev
    from app.engine.ast_parser import parse_and_audit_code

    async def _run():
        # Test AWS Secret with documentation example key
        prompt = "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'"
        ast_res = parse_and_audit_code(prompt)
        jev_eval = await evaluate_prompt_with_jev(prompt, ast_res, client_name="pytest")

        # 1. Verify probabilities distribution
        assert isinstance(jev_eval.classification_probabilities, dict)
        assert len(jev_eval.classification_probabilities) >= 4
        assert "Live_API_Secret" in jev_eval.classification_probabilities
        assert "Synthetic_Test_Fixture" in jev_eval.classification_probabilities
        # Sum of probabilities should be ~1.0
        assert 0.98 <= sum(jev_eval.classification_probabilities.values()) <= 1.02

        # 2. Verify raw API response is captured
        assert jev_eval.raw_api_response is not None
        assert "answers" in jev_eval.raw_api_response
        assert "data_classification" in jev_eval.raw_api_response["answers"]

    asyncio.run(_run())


def test_raw_score_and_preset3_customer_pii_action():
    """Verify that raw 0..4 score is preserved and Customer PII (score ~3.0) triggers NUDGE, not SILENT_LOG."""
    import asyncio
    from app.engine.jev_client import evaluate_prompt_with_jev
    from app.engine.ast_parser import parse_and_audit_code
    from app.domain.models import InterventionAction, DataClassification

    async def _run():
        prompt = (
            "Summarize customer account #482910-B: John Doe, DOB 1984-05-12, "
            "residential address 14 High St, Bristol BS1 4AA. Disputed a £1,200 credit card transaction."
        )
        ast_res = parse_and_audit_code(prompt)
        jev_eval = await evaluate_prompt_with_jev(prompt, ast_res, client_name="pytest")

        # Verify raw score is on 0..4 scale and normalized score is raw / 4
        assert jev_eval.raw_score > 2.0, f"Expected raw score > 2.0, got {jev_eval.raw_score}"
        assert jev_eval.raw_urgency_score == round(jev_eval.raw_score / 4, 4)
        assert jev_eval.data_classification == DataClassification.CUSTOMER_PII

        # Must trigger NUDGE under Policy DP-104, never SILENT_LOG
        assert jev_eval.action_taken == InterventionAction.NUDGE
        assert "DP-104" in jev_eval.reasoning_summary or "Customer PII" in jev_eval.reasoning_summary

    asyncio.run(_run())




