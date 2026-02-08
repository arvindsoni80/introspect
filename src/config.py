"""Configuration management for the application."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Gong API settings
    gong_api_url: str = "https://api.gong.io/v2"
    gong_access_key: str
    gong_secret_key: str
    gong_lookback_days: int = 7
    internal_domain: str  # e.g., "company.com" for external party detection

    # LLM settings
    llm_provider: str = "anthropic"
    llm_api_key: str
    llm_model: str = "claude-haiku-4-5-20251001"  # Haiku for cost optimization

    # Slack settings
    slack_webhook_url: Optional[str] = None  # Deprecated - use slack_bot_token for threading
    slack_bot_token: Optional[str] = None  # Bot User OAuth Token (xoxb-...)
    slack_channel_id: Optional[str] = None  # Channel ID to post to (e.g., C01234567)

    # Database settings
    db_type: str = "sqlite"  # "sqlite" for local, "firestore" for cloud
    sqlite_db_path: str = "./data/calls.db"

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


def load_settings() -> Settings:
    """Load and return application settings."""
    load_dotenv()
    return Settings()
