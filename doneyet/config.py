import os
from pathlib import Path

from dotenv import load_dotenv


def load_token() -> str:
    """Load configuration relative to the project, regardless of working directory."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, encoding="utf-8-sig")
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "your_bot_token_here":
        raise ValueError("Set DISCORD_TOKEN in the project's .env file before starting the bot.")
    return token
