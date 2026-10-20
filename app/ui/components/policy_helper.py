"""Helper utility to classify scenario-specific policy violations for Frontline and Pipeline UI."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class PolicyViolationDetails:
    violation_type: str  # "CREDENTIALS", "PII", "EXFILTRATION", "GENERAL"
    policy_code: str     # "SEC-201", "DP-104", "IP-305", "SEC-101"
    policy_name: str
    risk_title: str
    specific_detail: str
    required_action: str
    banner_nudge_desc: str
    banner_block_desc: str


def classify_incident_violation(
    record: Dict[str, Any],
    client_name: Optional[str] = None,
) -> PolicyViolationDetails:
    """
    Dynamically identifies the precise enterprise policy violation and context
    based on the evaluated data classification and payload tokens, preventing
    hardcoded 'Customer PII' text on credentials or exfiltration scenarios.
    """
    raw_prompt = str(record.get("extracted_prompt_text", ""))
    lower_prompt = raw_prompt.lower()

    # Extract data classification from either jev_evaluation dict or direct field
    jev_eval = record.get("jev_evaluation", {})
    if isinstance(jev_eval, dict):
        data_class = str(jev_eval.get("data_classification", ""))
    else:
        data_class = str(getattr(jev_eval, "data_classification", ""))

    if not client_name:
        client_id = record.get("client_identity", {})
        if isinstance(client_id, dict):
            client_name = client_id.get("client_name", "Corporate Gateway")
        else:
            client_name = getattr(client_id, "client_name", "Corporate Gateway")

    # 1. Credentials & Secrets Check (Preset 4, Live API Secrets, AWS/GCP keys)
    is_secret = (
        "secret" in data_class.lower()
        or "key" in data_class.lower()
        or "akia" in lower_prompt
        or "aws_" in lower_prompt
        or "secret_access_key" in lower_prompt
        or "api_key" in lower_prompt and "fake" not in lower_prompt and "mock" not in lower_prompt
    )

    if is_secret:
        return PolicyViolationDetails(
            violation_type="CREDENTIALS",
            policy_code="SEC-201",
            policy_name="SEC-201 (Zero-Trust Key Management & Secret Protection)",
            risk_title="Production Cloud Credentials Detected",
            specific_detail=(
                f"**{client_name}** intercepted an outbound prompt containing unmasked production cloud credentials "
                f"*(e.g. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`)*. Sending live credentials to external models "
                f"violates enterprise secret isolation standards."
            ),
            required_action=(
                "Please remove live credentials and use environment variables (e.g. `os.environ['AWS_KEY']`) "
                "or IAM temporary role assumption before dispatching."
            ),
            banner_nudge_desc=(
                "Detected live cloud credentials in prompt payload. Warning triggered under Policy SEC-201. "
                "Prompt held at boundary for key sanitization."
            ),
            banner_block_desc=(
                "Critical security violation under Policy SEC-201: Outbound payload containing live AWS root credentials "
                "dropped at perimeter before LLM dispatch."
            ),
        )

    # 2. Exfiltration & Obfuscated Payloads (Preset 5, Base64 SSH keys, jailbreaks)
    is_exfiltration = (
        "ip" in data_class.lower()
        or "exfiltration" in data_class.lower()
        or "base64" in lower_prompt
        or "ssh-add" in lower_prompt
        or "rsa private key" in lower_prompt
        or "openssh private key" in lower_prompt
        or "bypass dlp" in lower_prompt
        or "jailbreak" in lower_prompt
    )

    if is_exfiltration:
        return PolicyViolationDetails(
            violation_type="EXFILTRATION",
            policy_code="IP-305",
            policy_name="IP-305 (Proprietary Source Code & Exfiltration Prevention)",
            risk_title="Proprietary IP & Obfuscated Exfiltration Detected",
            specific_detail=(
                f"**{client_name}** intercepted an outbound command containing obfuscated cryptographic private key chunking "
                f"*(e.g. Base64 decoded RSA key injection)*. Obfuscated transfer of private keys violates perimeter security controls."
            ),
            required_action=(
                "Outbound transmission of raw encryption keys or obfuscated payloads outside approved enterprise "
                "repositories is prohibited."
            ),
            banner_nudge_desc=(
                "Detected obfuscated payload or proprietary source code under Policy IP-305. "
                "Held at perimeter boundary for security clearance."
            ),
            banner_block_desc=(
                "Critical security violation under Policy IP-305: Obfuscated Base64 cryptographic private key "
                "blocked at perimeter boundary."
            ),
        )

    # 3. Customer PII Check (Preset 3, DOB, customer addresses, bank accounts)
    is_pii = (
        "pii" in data_class.lower()
        or "customer" in data_class.lower()
        or any(k in lower_prompt for k in ["dob", "residential address", "credit card transaction", "alice walker", "account #9921", "disputed credit"])
    )

    if is_pii:
        return PolicyViolationDetails(
            violation_type="PII",
            policy_code="DP-104",
            policy_name="DP-104 (Customer PII Protection & Data Minimization)",
            risk_title="Customer PII Detected",
            specific_detail=(
                f"**{client_name}** intercepted an outbound prompt containing unmasked customer records "
                f"*(e.g. unmasked Date of Birth and residential address)*."
            ),
            required_action=(
                "Please confirm this request complies with customer data governance and data minimization "
                "policies before dispatching to external models."
            ),
            banner_nudge_desc=(
                "Detected unmasked customer PII. Warning triggered under Policy DP-104 (Customer Data Minimization). "
                "Prompt held for inline compliance acknowledgement."
            ),
            banner_block_desc=(
                "Critical privacy violation under Policy DP-104: Bulk customer records dropped at perimeter "
                "before external LLM dispatch."
            ),
        )

    # 4. General / Default Fallback
    return PolicyViolationDetails(
        violation_type="GENERAL",
        policy_code="SEC-101",
        policy_name="SEC-101 (Acceptable Enterprise AI Usage)",
        risk_title="Corporate AI Policy Advisory",
        specific_detail=(
            f"**{client_name}** intercepted an outbound prompt with sensitive content requiring corporate policy review."
        ),
        required_action=(
            "Please confirm this request complies with acceptable enterprise AI usage guidelines before dispatching."
        ),
        banner_nudge_desc=(
            "Corporate AI Policy Advisory triggered. Prompt held for inline compliance confirmation."
        ),
        banner_block_desc=(
            "Critical policy violation detected: Outbound payload terminated at network boundary."
        ),
    )
