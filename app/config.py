"""Application configuration loaded from environment / .env file.

Usage:
    from app.config import get_settings
    settings = get_settings()
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    bolna_api_key: str = ""
    google_places_api_key: str = ""
    serpapi_api_key: str = ""
    sarvam_api_key: str = ""
    bolna_webhook_url: str = "http://localhost:8000/webhook/bolna"
    bolna_agent_language: str = "kn-IN"
    max_concurrent_calls: int = 3
    call_timeout_seconds: int = 120

    # Langfuse — enabled iff both keys are present.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    # Optional tag/release identifiers for splitting traces by env
    langfuse_release: str = "dev"
    langfuse_environment: str = "local"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
