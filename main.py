from doneyet.bot import DoneYetBot
from doneyet.config import load_token
from doneyet.database import initialize_database


def main() -> None:
    try:
        token = load_token()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    initialize_database()
    DoneYetBot().run(token)


if __name__ == "__main__":
    main()
