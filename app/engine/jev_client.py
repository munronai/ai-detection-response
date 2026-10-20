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
    Note: TypeSafe AI System 1 does not require a `model` parameter; omitting it defaults
    automatically to the standard System 1 model on the server.
    """
    payload: Dict[str, Any] = {
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

    # Required top-level model identifier for TypeSafe AI System 1 API
    model = os.getenv("TYPESAFE_MODEL", "").strip().strip('"').strip("'")
    if not model or model == "jev-system1-aidr":
        model = "jev-latest"
    payload["model"] = model

    return payload


async def evaluate_with_live_jev_api(
    payload: Dict[str, Any],
    api_key: str,
    api_url: str,
) -> Tuple[float, DataClassification, float, Dict[str, float], Dict[str, Any], float]:
    """
    Calls the official TypeSafe AI `/v1/systemone` API over HTTP and normalizes responses:
      - is_synthetic_or_mock -> `noul` (float 0.0 .. 1.0)
      - data_classification -> `choice` (key from DATA_CLASSIFICATION_CRITERIA)
      - intervention_urgency -> `score` (normalized 0.0 .. 1.0)
      - choice_probabilities -> dict of probabilities for each candidate classification
      - raw_response -> full raw JSON response dictionary from API
      - raw_score_0_to_4 -> raw score on original 0..4 scale
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

    # Extract or synthesize normalized probability distribution across choices
    choice_probs: Dict[str, float] = {}
    if isinstance(class_ans, dict):
        prob_dict = class_ans.get("probabilities", class_ans.get("distribution", class_ans.get("scores", {})))
        if isinstance(prob_dict, dict) and prob_dict:
            for k, v in prob_dict.items():
                try:
                    choice_probs[str(k)] = round(float(v), 4)
                except (ValueError, TypeError):
                    pass

    # If the API returned a top choice without the full distribution dict, build a calibrated vector
    all_class_keys = list(DATA_CLASSIFICATION_CRITERIA.keys())
    if not choice_probs or len(choice_probs) < 2:
        top_prob = 0.52
        if isinstance(class_ans, dict):
            top_prob = float(class_ans.get("probability", class_ans.get("confidence", 0.52)))
            top_prob = max(0.45, min(0.95, top_prob))

        choice_probs[classification.value] = top_prob
        rem = round(1.0 - top_prob, 4)
        others = [k for k in all_class_keys if k != classification.value]

        # Prioritize runner-up based on context (e.g. AWS sample key: Synthetic fixture vs Secret)
        if classification == DataClassification.SYNTHETIC_TEST_FIXTURE:
            runner_up = DataClassification.LIVE_API_SECRET.value
        elif classification == DataClassification.LIVE_API_SECRET:
            runner_up = DataClassification.SYNTHETIC_TEST_FIXTURE.value
        elif classification == DataClassification.CUSTOMER_PII:
            runner_up = DataClassification.CLEAN_CODE_OR_CHAT.value
        else:
            runner_up = DataClassification.SYNTHETIC_TEST_FIXTURE.value

        if runner_up in others:
            runner_share = round(rem * 0.85, 4)
            choice_probs[runner_up] = runner_share
            rest = [k for k in others if k != runner_up]
            rest_share = round((rem - runner_share) / max(1, len(rest)), 4)
            for r in rest:
                choice_probs[r] = rest_share
        else:
            share = round(rem / max(1, len(others)), 4)
            for k in others:
                choice_probs[k] = share

    # 3. Score: intervention_urgency (0 to 4)
    urg_ans = raw_answers.get("intervention_urgency", {})
    max_idx = len(URGENCY_SCORE_CRITERIA) - 1  # 4
    if isinstance(urg_ans, dict) and "score" in urg_ans:
        raw_score_0_to_4 = float(urg_ans["score"])
        normalized_score = max(0.0, min(1.0, raw_score_0_to_4 / max_idx))
    elif isinstance(urg_ans, dict):
        normalized_score = float(urg_ans.get("probability", urg_ans.get("value", 0.2)))
        raw_score_0_to_4 = round(normalized_score * max_idx, 2)
    else:
        raw_score_0_to_4 = float(urg_ans)
        normalized_score = max(0.0, min(1.0, raw_score_0_to_4 / max_idx))

    return mock_prob, classification, normalized_score, choice_probs, data, raw_score_0_to_4


def simulate_jev_distributions(
    prompt_text: str,
    ast_res: ASTAnalysisResult,
) -> Tuple[float, DataClassification, float, Dict[str, float], Dict[str, Any], float]:
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

    # Check for documentation sample keys like ...EXAMPLE in AWS keys (Preset 4 boundary case)
    is_aws_example_key = has_live_aws and ("example" in lower or "fake" in lower or "mock" in lower)

    if has_live_aws or has_live_private_key:
        mock_p = 0.02
        data_class = DataClassification.LIVE_API_SECRET
        urgency = 0.98
        if is_aws_example_key:
            choice_probs = {
                DataClassification.LIVE_API_SECRET.value: 0.52,
                DataClassification.SYNTHETIC_TEST_FIXTURE.value: 0.44,
                DataClassification.CLEAN_CODE_OR_CHAT.value: 0.02,
                DataClassification.CUSTOMER_PII.value: 0.01,
                DataClassification.PROPRIETARY_CORE_IP.value: 0.01,
            }
        else:
            choice_probs = {
                DataClassification.LIVE_API_SECRET.value: 0.94,
                DataClassification.PROPRIETARY_CORE_IP.value: 0.03,
                DataClassification.SYNTHETIC_TEST_FIXTURE.value: 0.01,
                DataClassification.CUSTOMER_PII.value: 0.01,
                DataClassification.CLEAN_CODE_OR_CHAT.value: 0.01,
            }
    elif has_exfiltration:
        mock_p = 0.04
        data_class = DataClassification.PROPRIETARY_CORE_IP
        urgency = 0.95
        choice_probs = {
            DataClassification.PROPRIETARY_CORE_IP.value: 0.86,
            DataClassification.LIVE_API_SECRET.value: 0.10,
            DataClassification.CLEAN_CODE_OR_CHAT.value: 0.02,
            DataClassification.CUSTOMER_PII.value: 0.01,
            DataClassification.SYNTHETIC_TEST_FIXTURE.value: 0.01,
        }
    elif has_customer_pii and not ast_res.is_synthetic_test_fixture:
        mock_p = 0.05
        data_class = DataClassification.CUSTOMER_PII
        urgency = 0.85
        choice_probs = {
            DataClassification.CUSTOMER_PII.value: 0.78,
            DataClassification.CLEAN_CODE_OR_CHAT.value: 0.16,
            DataClassification.PROPRIETARY_CORE_IP.value: 0.04,
            DataClassification.SYNTHETIC_TEST_FIXTURE.value: 0.01,
            DataClassification.LIVE_API_SECRET.value: 0.01,
        }
    elif ast_res.is_synthetic_test_fixture:
        mock_p = 0.99
        data_class = DataClassification.SYNTHETIC_TEST_FIXTURE
        urgency = 0.85
        choice_probs = {
            DataClassification.SYNTHETIC_TEST_FIXTURE.value: 0.94,
            DataClassification.CLEAN_CODE_OR_CHAT.value: 0.04,
            DataClassification.LIVE_API_SECRET.value: 0.01,
            DataClassification.CUSTOMER_PII.value: 0.01,
            DataClassification.PROPRIETARY_CORE_IP.value: 0.00,
        }
    elif ast_res.has_code:
        mock_p = 0.15
        data_class = DataClassification.CLEAN_CODE_OR_CHAT
        urgency = 0.35
        choice_probs = {
            DataClassification.CLEAN_CODE_OR_CHAT.value: 0.82,
            DataClassification.SYNTHETIC_TEST_FIXTURE.value: 0.12,
            DataClassification.CUSTOMER_PII.value: 0.03,
            DataClassification.LIVE_API_SECRET.value: 0.02,
            DataClassification.PROPRIETARY_CORE_IP.value: 0.01,
        }
    else:
        # Nominal clean prompt
        mock_p = 0.08
        data_class = DataClassification.CLEAN_CODE_OR_CHAT
        urgency = 0.12
        choice_probs = {
            DataClassification.CLEAN_CODE_OR_CHAT.value: 0.96,
            DataClassification.CUSTOMER_PII.value: 0.02,
            DataClassification.SYNTHETIC_TEST_FIXTURE.value: 0.01,
            DataClassification.LIVE_API_SECRET.value: 0.01,
            DataClassification.PROPRIETARY_CORE_IP.value: 0.00,
        }

    raw_score_0_to_4 = round(urgency * 4, 2)
    raw_response = {
        "model": "jev-simulated-v1",
        "answers": {
            "is_synthetic_or_mock": {
                "noul": mock_p,
                "type": "noul",
                "instructions": "Does candidate_payload contain exclusively synthetic test data, mock fixtures, or dummy code within a unit testing scope?",
            },
            "data_classification": {
                "choice": data_class.value,
                "probabilities": choice_probs,
                "type": "choice",
                "instructions": "Which data classification best describes any sensitive content within candidate_payload?",
            },
            "intervention_urgency": {
                "score": raw_score_0_to_4,
                "normalized_score": urgency,
                "type": "score",
                "instructions": "How severe is the policy violation and how urgently should the gatekeeper intervene given the data classification and AST context?",
            },
        },
        "ast_discount_applied": ast_res.is_synthetic_test_fixture,
        "calibrated_urgency": round(urgency * ast_res.confidence_penalty, 4),
        "char_count": len(prompt_text),
    }

    return mock_p, data_class, urgency, choice_probs, raw_response, raw_score_0_to_4


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
        mock_prob, classification, raw_score, choice_probs, raw_response, raw_score_0_to_4 = await evaluate_with_live_jev_api(
            payload=payload,
            api_key=api_key,
            api_url=api_url,
        )
    else:
        engine_used = "JEV_SIMULATED"
        mock_prob, classification, raw_score, choice_probs, raw_response, raw_score_0_to_4 = simulate_jev_distributions(prompt_text, ast_res)

    # Core False-Positive Elimination:
    # If AST confirms synthetic test fixture, apply the confidence penalty discount
    calibrated_score = round(raw_score * ast_res.confidence_penalty, 4)

    # Ambiguity Margin Evaluation across Data Classification Choices
    sorted_choices = sorted(choice_probs.items(), key=lambda x: x[1], reverse=True)
    decision_margin = 1.0
    is_ambiguous = False
    applied_margin = float(settings.ambiguity_margin)
    top1_name = classification.value
    top1_prob = 1.0
    top2_name = ""
    top2_prob = 0.0

    if len(sorted_choices) >= 2:
        top1_name, top1_prob = sorted_choices[0]
        top2_name, top2_prob = sorted_choices[1]
        decision_margin = round(top1_prob - top2_prob, 4)

        # Trigger ambiguity if margin is within configured slider threshold
        if decision_margin <= applied_margin and top2_prob >= 0.15:
            is_ambiguous = True

    # Policy Action Mapping with Ambiguity Margin Evaluation
    if calibrated_score >= settings.block_threshold:
        action = InterventionAction.BLOCK
        reason = f"[{engine_used}] Critical policy violation ({calibrated_score:.2f} >= {settings.block_threshold}): {classification.value}"
    elif calibrated_score >= settings.redact_threshold:
        action = InterventionAction.REDACT
        reason = f"[{engine_used}] High sensitive data risk ({calibrated_score:.2f}): Redacting sensitive spans"
    elif calibrated_score >= settings.nudge_threshold or (
        classification == DataClassification.CUSTOMER_PII and not ast_res.is_synthetic_test_fixture
    ):
        action = InterventionAction.NUDGE
        if classification == DataClassification.CUSTOMER_PII and not ast_res.is_synthetic_test_fixture:
            reason = (
                f"[{engine_used}] Customer PII policy warning (score {raw_score_0_to_4:.2f}/4.0, "
                f"normalized {calibrated_score:.2f} >= {settings.nudge_threshold:.2f}): "
                f"Displaying inline user warning under Policy DP-104"
            )
        else:
            reason = f"[{engine_used}] Moderate compliance alert ({calibrated_score:.2f}): Displaying inline user nudge"
        if is_ambiguous:
            reason += f" | Ambiguity Margin Active: {decision_margin:.1%} <= {applied_margin:.1%} ({top1_name} vs {top2_name})"
    elif is_ambiguous:
        # Sensitive runner-up escalates nominal allow to inline policy warning
        sensitive_classes = {
            DataClassification.LIVE_API_SECRET.value,
            DataClassification.CUSTOMER_PII.value,
            DataClassification.PROPRIETARY_CORE_IP.value,
        }
        if top2_name in sensitive_classes:
            action = InterventionAction.NUDGE
            reason = (
                f"[{engine_used}] Ambiguity Escalation (Margin {decision_margin:.1%} <= {applied_margin:.1%}): "
                f"Close split between '{top1_name}' ({top1_prob:.0%}) and '{top2_name}' ({top2_prob:.0%}) escalated to Policy Warning"
            )
        elif calibrated_score >= settings.silent_log_threshold:
            action = InterventionAction.SILENT_LOG
            reason = f"[{engine_used}] Ambiguous internal context ({calibrated_score:.2f}): Appending to silent audit log"
        else:
            action = InterventionAction.ALLOW
            reason = f"[{engine_used}] Clean traffic permitted by policy gatekeeper"
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
        classification_probabilities=choice_probs,
        raw_score=round(raw_score_0_to_4, 2),
        raw_urgency_score=round(raw_score, 4),
        calibrated_urgency_score=round(calibrated_score, 4),
        eval_time_ms=round(eval_duration_ms, 2),
        action_taken=action,
        reasoning_summary=reason,
        ambiguity_margin_applied=applied_margin,
        is_ambiguous_decision=is_ambiguous,
        decision_margin=decision_margin,
        raw_api_response=raw_response,
        estimated_inference_cost_usd=0.00001,
    )
