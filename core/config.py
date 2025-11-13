"""Configuration management."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration."""

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
    MAX_STEPS = int(os.getenv("MAX_STEPS", "15"))
    MIN_SUCCESSFUL_ACTIONS = int(os.getenv("MIN_SUCCESSFUL_ACTIONS", "2"))

    APP_URLS = {
        "linear": "https://linear.app",
        "notion": "https://www.notion.so",
        "asana": "https://app.asana.com",
    }

    @classmethod
    def validate(cls) -> bool:
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")

        Path(cls.OUTPUT_DIR).mkdir(exist_ok=True)
        return True

    @classmethod
    def get_app_url(cls, app_name: str) -> str:
        """Get URL for a known app.

        Args:
            app_name: App name (case-insensitive)

        Returns:
            URL string or empty string if not found
        """

        return cls.APP_URLS.get(app_name.lower(), "")


Config.validate()
