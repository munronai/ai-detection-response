"""Application configuration and environment settings."""

import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env is loaded into process environment
load_dotenv()


class Settings(BaseSettings):
    app_name: str = "Jev Gatekeeper & AST AIDR Sandbox"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    docs_url: str = "/docs"
    redoc_url: Optional[str] = "/redoc"

    # Upstream AI Target Endpoints (Defaults to OpenAI & Anthropic official APIs)
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Optional upstream API keys for live forwarding
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY", None)

    # TypeSafe AI Jev Settings
    typesafe_api_key: Optional[str] = os.getenv("TYPESAFE_API_KEY", None)
    typesafe_api_url: str = os.getenv("TYPESAFE_API_URL", "https://api.typesafe.ai/v1/systemone")
    typesafe_model: str = os.getenv("TYPESAFE_MODEL", "jev-latest")
    jev_mode: str = "simulated"  # "simulated" or "live"

    # Default Policy Thresholds (calibrated to 0..4 Jev System 1 scale)
    # Level 0 (0.0): Allow | Level 1 (0.25): Silent Log | Level 2 & 3 (0.50 - 0.75): Nudge Warning | Level 4 (1.00): Block
    allow_threshold: float = 0.20
    silent_log_threshold: float = 0.40
    nudge_threshold: float = 0.60
    redact_threshold: float = 0.88
    block_threshold: float = 0.88
    ambiguity_margin: float = 0.15

    # Admin key for privileged operations / golden resets
    admin_key: str = os.getenv("SANDBOX_ADMIN_KEY", "jev-aidr-admin-2026")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
