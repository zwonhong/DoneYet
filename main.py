from doneyet.bot import DoneYetBot
from doneyet.config import load_guild_id, load_token
from doneyet.database import initialize_database


def main() -> None:
    try:
        token = load_token()
        guild_id = load_guild_id()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    initialize_database()
    DoneYetBot(guild_id=guild_id).run(token)


if __name__ == "__main__":
    main()
