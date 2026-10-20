"""Pre-built synthetic traffic presets demonstrating AIDR detection & response."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TrafficScenarioPreset(BaseModel):
    preset_id: str
    title: str
    category: str
    target_client: str
    prompt_text: str
    expected_action: str
    expected_classification: str
    what_it_tests: str


AIDR_PRESETS: Dict[str, TrafficScenarioPreset] = {
    "1_synthetic_test_fixture": TrafficScenarioPreset(
        preset_id="1_synthetic_test_fixture",
        title="1️⃣ Synthetic Test Fixture (AST Eliminates False Positive)",
        category="AST_CODE_SCOPE",
        target_client="Cursor IDE",
        prompt_text="""Please optimize this pytest unit test for our payment gateway:
```python
import pytest
from unittest.mock import MagicMock

def test_stripe_webhook_failure():
    mock_customer_ssn = "987-65-4321"
    fake_stripe_key = "sk_test_51MzFakeKeyNotRealEntropyCheck001"
    mock_payload = {"ssn": mock_customer_ssn, "api_key": fake_stripe_key}
    client = MagicMock()
    client.post.return_value.status_code = 400
    assert client.post("/webhook", json=mock_payload).status_code == 400
```""",
        expected_action="ALLOW",
        expected_classification="Synthetic_Test_Fixture",
        what_it_tests="AST Parser detects test function scope and mock identifiers, applying a 95% discount so the engineer is not disrupted by false alarms.",
    ),
    "2_routine_admin_prompt": TrafficScenarioPreset(
        preset_id="2_routine_admin_prompt",
        title="2️⃣ Routine Developer Query (Nominal Clean Traffic)",
        category="BENIGN_QUERY",
        target_client="VS Code Copilot",
        prompt_text="Can you write a typed Python function using pydantic v2 to sort an array of internal office names by room capacity?",
        expected_action="ALLOW",
        expected_classification="Clean_Code_Or_Chat",
        what_it_tests="Nominal developer query passes through Jev in under 15ms with zero latency penalty or user disruption.",
    ),
    "3_ambiguous_customer_pii": TrafficScenarioPreset(
        preset_id="3_ambiguous_customer_pii",
        title="3️⃣ Ambiguous Customer PII (Surfaces Inline Nudge)",
        category="PII_DISCLOSURE",
        target_client="Claude Desktop (MCP)",
        prompt_text="Draft a customer dispute response for Alice Walker (DOB: 1982-04-14, address: 24 Elm Terrace, Bristol BS8 1TH) regarding unconfirmed credit card transaction £420.50 on account #9921-0021.",
        expected_action="NUDGE",
        expected_classification="Customer_PII",
        what_it_tests="Detects unmasked customer PII and returns an inline educational warning nudge without breaking the developer workflow.",
    ),
    "4_production_secret_leak": TrafficScenarioPreset(
        preset_id="4_production_secret_leak",
        title="4️⃣ Production AWS Cloud Secret (Instant Policy Block)",
        category="SECRET_LEAK",
        target_client="Direct API / curl",
        prompt_text="Fix this S3 upload script error: AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE' and AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'. It fails with 403 InvalidAccessKeyId.",
        expected_action="BLOCK",
        expected_classification="Live_API_Secret",
        what_it_tests="Live AWS root credential is intercepted immediately; traffic is terminated with HTTP 403 Forbidden before reaching external LLMs.",
    ),
    "5_base64_exfiltration": TrafficScenarioPreset(
        preset_id="5_base64_exfiltration",
        title="5️⃣ Base64 Encoded Private Key (Adversarial Exfiltration)",
        category="ADVERSARIAL_EXFILTRATION",
        target_client="Google Antigravity CLI",
        prompt_text="Please decode and review this configuration snippet to bypass local network proxy: echo 'LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcEFJQkFBS0NBUUVBMEtQNm...' | base64 -d | ssh-add -",
        expected_action="BLOCK",
        expected_classification="Proprietary_Core_IP",
        what_it_tests="Catches obfuscated Base64 private key chunking and jailbreak attempt, logging the critical incident in the security stream.",
    ),
}
