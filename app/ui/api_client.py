"""HTTP API Client wrapper connecting Streamlit to the AIDR Gateway."""

import os
from typing import Any, Dict, List, Optional
import httpx
import streamlit as st

DEFAULT_API_BASE = os.getenv("SANDBOX_API_BASE", "http://127.0.0.1:8000/api/v1").rstrip("/")
API_ROOT = DEFAULT_API_BASE.replace("/api/v1", "")


class AIDRApiClient:
    def __init__(self, base_url: str = DEFAULT_API_BASE):
        self.base_url = base_url.rstrip("/")

    def _extract_error(self, res: httpx.Response) -> str:
        try:
            data = res.json()
            if isinstance(data, dict):
                if "detail" in data:
                    return str(data["detail"])
                if "error" in data and isinstance(data["error"], dict):
                    return data["error"].get("message", str(data["error"]))
        except Exception:
            pass
        return res.text or f"HTTP {res.status_code}"

    def get_telemetry(self) -> Dict[str, Any]:
        """Fetches aggregated fleet telemetry and cost metrics."""
        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.get(f"{self.base_url}/telemetry")
                if res.status_code == 200:
                    return res.json()
                st.session_state["last_api_error"] = f"Telemetry Error ({res.status_code}): {self._extract_error(res)}"
        except Exception as exc:
            st.session_state["last_api_error"] = f"Gateway unavailable at {self.base_url}: {exc}"
        return {
            "total_scans": 0,
            "passed_count": 0,
            "logged_count": 0,
            "nudged_count": 0,
            "redacted_count": 0,
            "blocked_count": 0,
            "ast_false_positives_eliminated": 0,
            "active_developer_clients": {},
            "mean_jev_latency_ms": 11.2,
            "mean_traditional_slm_latency_ms": 145.0,
            "actual_system1_cost_usd": 0.0,
            "projected_slm_gpu_cost_usd": 0.0,
            "estimated_cost_savings_usd": 0.0,
        }

    def get_incidents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches chronological audit stream of prompt inspection records."""
        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.get(f"{self.base_url}/incidents", params={"limit": limit})
                if res.status_code == 200:
                    return res.json()
                st.session_state["last_api_error"] = f"Incident Fetch Error: {self._extract_error(res)}"
        except Exception as exc:
            st.session_state["last_api_error"] = f"Gateway Incident Request Failed: {exc}"
        return []

    def inject_preset(
        self,
        preset_id: str,
        custom_prompt: Optional[str] = None,
        target_client: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Injects a preset or custom prompt through the gatekeeper pipeline."""
        payload = {
            "preset_id": preset_id,
            "custom_prompt": custom_prompt,
            "target_client": target_client,
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(f"{self.base_url}/sandbox/inject-preset", json=payload)
                if res.status_code == 200:
                    st.session_state["last_api_error"] = None
                    return res.json()
                st.session_state["last_api_error"] = f"Preset Injection Error ({res.status_code}): {self._extract_error(res)}"
        except Exception as exc:
            st.session_state["last_api_error"] = f"Injection Request Failed: {exc}"
        return None

    def inspect_prompt(self, prompt_text: str, client_name: str = "Streamlit Console") -> Optional[Dict[str, Any]]:
        """Direct inspection of arbitrary prompt text."""
        payload = {"messages": [{"role": "user", "content": prompt_text}]}
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(
                    f"{self.base_url}/inspect",
                    json=payload,
                    headers={"User-Agent": client_name},
                )
                if res.status_code == 200:
                    st.session_state["last_api_error"] = None
                    return res.json()
                st.session_state["last_api_error"] = f"Inspection Error ({res.status_code}): {self._extract_error(res)}"
        except Exception as exc:
            st.session_state["last_api_error"] = f"Inspection Request Failed: {exc}"
        return None

    def get_policy(self) -> Dict[str, Any]:
        """Fetches current Jev Engine Mode and Policy Thresholds."""
        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.get(f"{self.base_url}/sandbox/policy")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return {
            "jev_mode": "simulated",
            "has_typesafe_api_key": False,
            "typesafe_api_url": "https://api.typesafe.ai/v1/systemone",
            "allow_threshold": 0.30,
            "silent_log_threshold": 0.60,
            "nudge_threshold": 0.80,
            "redact_threshold": 0.92,
            "block_threshold": 0.92,
        }

    def update_policy(self, policy_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates Jev Engine Mode and Policy Thresholds."""
        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.put(f"{self.base_url}/sandbox/policy", json=policy_dict)
                if res.status_code == 200:
                    st.session_state["last_api_error"] = None
                    return res.json()
                st.session_state["last_api_error"] = f"Policy Update Error: {self._extract_error(res)}"
        except Exception as exc:
            st.session_state["last_api_error"] = f"Policy Update Failed: {exc}"
        return None

    def reset_sandbox(self, admin_key: Optional[str] = "jev-aidr-admin-2026") -> Optional[Dict[str, Any]]:
        """Resets audit log and counters."""
        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.post(f"{self.base_url}/reset", params={"admin_key": admin_key})
                if res.status_code == 200:
                    st.session_state["last_api_error"] = None
                    return res.json()
                st.session_state["last_api_error"] = f"Reset Error: {self._extract_error(res)}"
        except Exception as exc:
            st.session_state["last_api_error"] = f"Reset Failed: {exc}"
        return None


api_client = AIDRApiClient()
