"""Application settings, loaded from environment variables and the repo-root .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

ProviderName = Literal["ollama", "gemini"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    demo_mode: bool = True

    # Auth. The default secret is for local dev only; startup refuses it outside dev.
    jwt_secret: str = "change-me"
    data_key: str = ""  # Fernet key for encrypting phone numbers; derived from jwt_secret when empty
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    # Demo login: a fixed OTP for whitelisted numbers. "*" allows any number (dev only).
    demo_otp: str = "123456"
    demo_phones: str = ""
    # When true, any valid mobile number can sign in with the fixed demo OTP (no SMS gateway is built yet). The numbers in
    # DEMO_PHONES keep working as before. Local demo only: anyone who knows a number and the code can sign in as it.
    demo_allow_any_number: bool = False
    # Numbers that also get the admin role when they sign in (teacher verification). Comma-separated; "*" is not allowed.
    admin_phones: str = ""
    otp_ttl_s: int = 300
    otp_max_attempts: int = 3
    otp_resend_cooldown_s: int = 30
    otp_per_phone_per_10min: int = 5
    otp_per_ip_per_10min: int = 30
    # Read the client IP from X-Forwarded-For. Only enable behind a proxy you control
    # (the Vite dev proxy counts), otherwise the header can be spoofed.
    trust_proxy: bool = False

    # MongoDB Atlas. Empty means "not configured": the app still starts.
    mongodb_uri: str = ""
    db_name: str = "khoj"

    # A scheme record not checked by a person (or entered) within this many days shows "Check with the office".
    verified_max_days: int = 90

    # LLM
    llm_mode: Literal["cache_only", "live"] = "cache_only"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_text_model: str = ""
    ollama_vision_model: str = ""
    ollama_timeout_s: float = 120.0
    gemini_api_key: str = ""
    gemini_text_model: str = ""
    gemini_vision_model: str = ""
    gemini_timeout_s: float = 60.0
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Gnani (Vachana): speech to text, text to speech. Two keys: the first is used until it runs out of
    # credit or quota, then the second. Empty means not configured. Keys are never logged or returned.
    gnani_api_key_id: str = ""
    gnani_api_key_id_2: str = ""
    gnani_base_url: str = "https://api.vachana.ai"
    gnani_stt_model: str = ""  # empty = Gnani's default (Prisma v2.5); "prisma-v3.0" for the newer one
    gnani_tts_model: str = "timbre-v3.0"
    gnani_tts_voice: str = "Shivani"  # voices belong to a model; v3.0 voices speak every supported language
    gnani_timeout_s: float = 30.0
    gnani_key_cooldown_s: float = 900.0  # how long a key that reported "no credit" is left alone

    # Per-task routing (CLAUDE.md section 8, "LLM routing")
    llm_route_extraction: ProviderName = "ollama"
    llm_route_drafting: ProviderName = "ollama"
    llm_route_reasoning: ProviderName = "ollama"
    llm_route_ingestion: ProviderName = "gemini"
    # Hindi and Marathi to English before extraction. Gemini translates these better than a small local model.
    llm_route_translation: ProviderName = "gemini"
    vision_route: ProviderName = "ollama"
    # A teacher's proof photos. Separate from `vision_route` so student photos never follow it to Gemini.
    proof_route: ProviderName = "gemini"
    # Student photos leave the laptop only when this is true (or vision_route is gemini).
    vision_fallback_to_gemini: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
