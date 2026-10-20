"""Dual-Engine TypeSafe AI Jev System 1 Evaluator (Simulated + Live API)."""

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx
from fastapi import HTTPException

from app.config import settings
from app.domain.models import (
    ASTAnalysisResult,
    DataClassification,
    InterventionAction,
    JevEvaluation,
)

# Ordered level descriptions required by TypeSafe AI Jev Score `criteria` (0 to 4)
URGENCY_SCORE_CRITERIA = [
    "Irrelevant prompt or synthetic test code; nominal risk requiring zero logging or action",
    "Low-risk non-sensitive internal context; allow through and silently log in audit stream",
    "Ambiguous sensitive data or internal documentation; surface inline user nudge",
    "Sensitive customer PII or confidential IP; redact sensitive spans before forwarding",
    "Critical production secret, live cloud credential, or malicious exfiltration attempt; immediately block traffic",
]

# Option map required by TypeSafe AI Jev Choice `criteria`
DATA_CLASSIFICATION_CRITERIA = {
    "Clean_Code_Or_Chat": "Benign general chat, public algorithms, formatting requests, or documentation questions",
    "Synthetic_Test_Fixture": "Synthetic identifiers, mock credit cards, test fixtures, or dummy tokens within unit tests",
    "Customer_PII": "Real consumer Personally Identifiable Information such as SSN, personal phone, address, or banking details",
    "Live_API_Secret": "Production API keys, cloud root credentials, private SSH keys, or live database passwords",
    "Proprietary_Core_IP": "Core algorithmic proprietary IP, unreleased financial reports, or adversarial jailbreak prompts",
}


def build_typesafe_jev_payload(
    prompt_text: str,
    ast_res: ASTAnalysisResult,
    client_name: str = "Unknown",
) -> Dict[str, Any]:
    """
    Constructs the official TypeSafe AI Jev `/v1/systemone` request payload.
    Conforms strictly to the TypeSafe AI System 1 specification:
      - `state`: context dictionary containing client identity, AST metadata, and candidate text.
      - `questions`: typed questions mapping to `noul`, `choice`, and `score`.
    """
    return {
        "model": os.getenv("TYPESAFE_MODEL", "jev-latest"),
        "state": {
            "client_identity": {
                "client_name": client_name,
            },
            "ast_context": {
                "has_code": ast_res.has_code,
                "is_synthetic_test_fixture": ast_res.is_synthetic_test_fixture,
                "test_function_count": ast_res.test_function_count,
                "mock_frameworks": ast_res.mock_frameworks,
                "confidence_penalty": ast_res.confidence_penalty,
                "reason": ast_res.reason,
            },
            "candidate_payload": {
                "text_snippet": prompt_text[:2000],
                "char_length": len(prompt_text),
            },
        },
        "questions": {
            "is_synthetic_or_mock": {
                "type": "noul",
                "instructions": (
                    "Does candidate_payload contain exclusively synthetic test data, mock fixtures, "
                    "or dummy code within a unit testing scope?"
                ),
                "criteria": {
                    "true": "Content is mock data, synthetic fixtures, test assertions, or sample documentation code.",
                    "false": "Content contains real production credentials, real customer PII, or proprietary business logic.",
                },
            },
            "data_classification": {
                "type": "choice",
                "instructions": "Which data classification best describes any sensitive content within candidate_payload?",
                "criteria": DATA_CLASSIFICATION_CRITERIA,
            },
            "intervention_urgency": {
                "type": "score",
                "instructions": (
                    "How severe is the policy violation and how urgently should the gatekeeper intervene "
                    "given the data classification and AST context?"
                ),
                "criteria": URGENCY_SCORE_CRITERIA,
            },
        },
    }


async def evaluate_with_live_jev_api(
    payload: Dict[str, Any],
    api_key: str,
    api_url: str,
) -> Tuple[float, DataClassification, float]:
    """
    Calls the official TypeSafe AI `/v1/systemone` API over HTTP and normalizes responses:
      - is_synthetic_or_mock -> `noul` (float 0.0 .. 1.0)
      - data_classification -> `choice` (key from DATA_CLASSIFICATION_CRITERIA)
      - intervention_urgency -> `score` (normalized 0.0 .. 1.0)
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(api_url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"TypeSafe AI Jev API error ({resp.status_code}) at {api_url}: {resp.text}",
                )
            data = resp.json()
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach live TypeSafe AI Jev API at {api_url}: {exc}",
            ) from exc

    raw_answers = data.get("answers", data.get("results", data))

    # 1. Noul: is_synthetic_or_mock
    mock_ans = raw_answers.get("is_synthetic_or_mock", {})
    if isinstance(mock_ans, dict):
        mock_prob = float(
            mock_ans.get("noul", mock_ans.get("probability", mock_ans.get("true_prob", 0.5)))
        )
    else:
        mock_prob = float(mock_ans)

    # 2. Choice: data_classification
    class_ans = raw_answers.get("data_classification", {})
    if isinstance(class_ans, dict):
        class_key = str(
            class_ans.get("choice", class_ans.get("top_choice", "Clean_Code_Or_Chat"))
        )
    else:
        class_key = str(class_ans)

    try:
        classification = DataClassification(class_key)
    except ValueError:
        classification = DataClassification.CLEAN_CODE_OR_CHAT

    # 3. Score: intervention_urgency (0 to 4)
    urg_ans = raw_answers.get("intervention_urgency", {})
    max_idx = len(URGENCY_SCORE_CRITERIA) - 1  # 4
    if isinstance(urg_ans, dict) and "score" in urg_ans:
        raw_score = float(urg_ans["score"])
        normalized_score = max(0.0, min(1.0, raw_score / max_idx))
    elif isinstance(urg_ans, dict):
        normalized_score = float(urg_ans.get("probability", urg_ans.get("value", 0.2)))
    else:
        normalized_score = float(urg_ans) / max_idx

    return mock_prob, classification, normalized_score


def simulate_jev_distributions(
    prompt_text: str,
    ast_res: ASTAnalysisResult,
) -> Tuple[float, DataClassification, float]:
    """
    High-fidelity offline calibrated System 1 simulation.
    Produces repeatable mathematical distributions for offline demos and zero-cost testing.
    """
    lower = prompt_text.lower()

    # Rule-calibrated probability distributions
    has_live_aws = bool(re.search(r"AKIA[0-9A-Z]{16}", prompt_text))
    has_live_private_key = "-----BEGIN RSA PRIVATE KEY-----" in prompt_text or "-----BEGIN OPENSSH PRIVATE KEY-----" in prompt_text
    has_real_ssn = bool(re.search(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b", prompt_text))
    has_customer_pii = has_real_ssn or bool(
        re.search(
            r"\b(dob|birth|account #|residential address|invoice inv-|disputed a £|credit card transaction|bristol bs[0-9])\b",
            lower,
        )
    )
    has_exfiltration = any(kw in lower for kw in ["exfiltrate", "bypass dlp", "jailbreak", "override guardrails", "base64"])

    if has_live_aws or has_live_private_key:
        return 0.02, DataClassification.LIVE_API_SECRET, 0.98
    if has_exfiltration:
        return 0.04, DataClassification.PROPRIETARY_CORE_IP, 0.95
    if has_customer_pii and not ast_res.is_synthetic_test_fixture:
        return 0.05, DataClassification.CUSTOMER_PII, 0.85
    if ast_res.is_synthetic_test_fixture:
        return 0.99, DataClassification.SYNTHETIC_TEST_FIXTURE, 0.85
    if ast_res.has_code:
        return 0.15, DataClassification.CLEAN_CODE_OR_CHAT, 0.35

    # Nominal clean prompt
    return 0.08, DataClassification.CLEAN_CODE_OR_CHAT, 0.12


async def evaluate_prompt_with_jev(
    prompt_text: str,
    ast_res: ASTAnalysisResult,
    client_name: str = "Unknown",
    override_mode: Optional[str] = None,
) -> JevEvaluation:
    """
    Evaluates a candidate prompt using TypeSafe AI Jev (System 1).
    Toggles between Live `/v1/systemone` API and offline calibrated simulation based on settings.
    """
    start_time = time.perf_counter()
    active_mode = override_mode or settings.jev_mode

    api_key = settings.typesafe_api_key or os.getenv("TYPESAFE_API_KEY", "")
    api_key = str(api_key).strip().strip('"').strip("'")
    api_url = settings.typesafe_api_url

    if active_mode == "live" and api_key:
        engine_used = "JEV_LIVE_API"
        payload = build_typesafe_jev_payload(prompt_text, ast_res, client_name)
        mock_prob, classification, raw_score = await evaluate_with_live_jev_api(
            payload=payload,
            api_key=api_key,
            api_url=api_url,
        )
    else:
        engine_used = "JEV_SIMULATED"
        mock_prob, classification, raw_score = simulate_jev_distributions(prompt_text, ast_res)

    # Core False-Positive Elimination:
    # If AST confirms synthetic test fixture, apply the confidence penalty discount
    calibrated_score = round(raw_score * ast_res.confidence_penalty, 4)

    # Policy Action Mapping
    if calibrated_score >= settings.block_threshold:
        action = InterventionAction.BLOCK
        reason = f"[{engine_used}] Critical policy violation ({calibrated_score:.2f} >= {settings.block_threshold}): {classification.value}"
    elif calibrated_score >= settings.redact_threshold:
        action = InterventionAction.REDACT
        reason = f"[{engine_used}] High sensitive data risk ({calibrated_score:.2f}): Redacting sensitive spans"
    elif calibrated_score >= settings.nudge_threshold:
        action = InterventionAction.NUDGE
        reason = f"[{engine_used}] Moderate compliance alert ({calibrated_score:.2f}): Displaying inline user nudge"
    elif calibrated_score >= settings.silent_log_threshold:
        action = InterventionAction.SILENT_LOG
        reason = f"[{engine_used}] Low risk internal context ({calibrated_score:.2f}): Appending to silent audit log"
    else:
        action = InterventionAction.ALLOW
        if ast_res.is_synthetic_test_fixture:
            reason = (
                f"[{engine_used}] AST eliminated false positive: synthetic fixture discounted "
                f"from {raw_score:.2f} to {calibrated_score:.2f} (mock probability: {mock_prob:.0%})"
            )
        else:
            reason = f"[{engine_used}] Clean traffic permitted by policy gatekeeper"

    eval_duration_ms = (time.perf_counter() - start_time) * 1000

    return JevEvaluation(
        engine_used=engine_used,
        is_synthetic_or_mock_prob=round(mock_prob, 4),
        data_classification=classification,
        raw_urgency_score=round(raw_score, 4),
        calibrated_urgency_score=round(calibrated_score, 4),
        eval_time_ms=round(eval_duration_ms, 2),
        action_taken=action,
        reasoning_summary=reason,
        estimated_inference_cost_usd=0.00001,
    )
