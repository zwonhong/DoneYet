import os
from pathlib import Path

from dotenv import load_dotenv


def load_guild_id() -> int | None:
    """Optional development guild; blank keeps global-only synchronization."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, encoding="utf-8-sig")
    value = os.getenv("DISCORD_GUILD_ID", "").strip()
    if not value:
        return None
    if not value.isascii() or not value.isdecimal() or not 0 < int(value) < 2**64:
        raise ValueError("DISCORD_GUILD_ID must be a positive Discord server ID, or blank.")
    return int(value)


def load_token() -> str:
    """Load configuration relative to the project, regardless of working directory."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, encoding="utf-8-sig")
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "your_bot_token_here":
        raise ValueError("Set DISCORD_TOKEN in the project's .env file before starting the bot.")
    return token
