from doneyet.bot import DoneYetBot
from doneyet.config import load_guild_id, load_token
from doneyet.database import initialize_database
import logging
import os

logger = logging.getLogger("doneyet")


def main() -> None:
    logging.basicConfig(level=getattr(logging, os.getenv("DONEYET_LOG_LEVEL", "INFO").upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        token = load_token()
        guild_id = load_guild_id()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    initialize_database()
    logger.info("Database initialized")
    logger.info("Starting DoneYet? bot")
    DoneYetBot(guild_id=guild_id).run(token)


if __name__ == "__main__":
    main()
