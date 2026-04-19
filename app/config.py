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
    bolna_webhook_url: str = "http://localhost:8000/webhook/bolna"
    bolna_agent_language: str = "kn-IN"
    max_concurrent_calls: int = 3
    call_timeout_seconds: int = 120

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
