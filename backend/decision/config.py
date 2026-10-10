"""
config.py — Application settings loaded from environment variables.

All secrets and database credentials must come from environment variables
or a .env file — never hardcoded in source code.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/retainiq"

    # Routing policy defaults (overridden by admin config in DB in Phase 2)
    routing_p30_threshold: float = 0.40
    routing_policy_version: str = "routing_policy_v1"
    partially_stale_treatment: str = "human_review"

    # Budget / capacity defaults
    default_k_slots: int = 10
    default_currency: str = "MYR"

    # App
    app_title: str = "RetainIQ — Decision Engine API"
    app_version: str = "0.1.0"
    debug: bool = False


# Module-level singleton
settings = Settings()
