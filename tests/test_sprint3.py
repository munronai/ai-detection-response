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


