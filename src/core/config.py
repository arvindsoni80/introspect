"""Configuration management."""

import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Application configuration loaded from environment variables."""

    def __init__(self):
        """Load configuration from .env file."""
        # Load .env file from project root
        env_path = Path(__file__).parent.parent.parent / ".env"
        load_dotenv(env_path)

        # Gong API
        self.GONG_API_URL = os.getenv("GONG_API_URL", "https://api.gong.io/v2")
        self.GONG_ACCESS_KEY = os.getenv("GONG_ACCESS_KEY", "")
        self.GONG_SECRET_KEY = os.getenv("GONG_SECRET_KEY", "")
        self.GONG_LOOKBACK_DAYS = int(os.getenv("GONG_LOOKBACK_DAYS", "7"))
        self.INTERNAL_DOMAIN = os.getenv("INTERNAL_DOMAIN", "")

        # LLM
        self.LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
        self.LLM_API_KEY = os.getenv("LLM_API_KEY", "")
        self.LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")

        # Slack
        self.SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
        self.SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

        # Database
        self.DB_TYPE = os.getenv("DB_TYPE", "sqlite")
        self.SQLITE_DB_PATH = self._expand_path(
            os.getenv("SQLITE_DB_PATH", "introspect.db")
        )

    def _expand_path(self, path: str) -> str:
        """Expand ~ and environment variables in path."""
        expanded = os.path.expanduser(path)
        expanded = os.path.expandvars(expanded)
        return expanded

    def validate(self) -> bool:
        """Check if required config is present."""
        required = []

        if not self.GONG_ACCESS_KEY:
            required.append("GONG_ACCESS_KEY")
        if not self.GONG_SECRET_KEY:
            required.append("GONG_SECRET_KEY")
        if not self.LLM_API_KEY:
            required.append("LLM_API_KEY")

        if required:
            print(f"⚠️  Missing required environment variables: {', '.join(required)}")
            return False

        return True
