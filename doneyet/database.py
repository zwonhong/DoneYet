"""SQLite schema and connections, independent of Discord."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "doneyet.db"

# Timestamps are UTC ISO 8601 TEXT with an explicit offset. Dates and schedule
# times are local to checks.timezone, not to the host operating system.
SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    verification_mode TEXT NOT NULL CHECK (verification_mode IN ('button', 'photo', 'either')),
    timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'))
);

CREATE TABLE IF NOT EXISTS check_days (
    check_id INTEGER NOT NULL REFERENCES checks(id),
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    PRIMARY KEY (check_id, weekday)
);

CREATE TABLE IF NOT EXISTS check_schedules (
    id INTEGER PRIMARY KEY,
    check_id INTEGER NOT NULL REFERENCES checks(id),
    sequence INTEGER NOT NULL CHECK (sequence >= 1),
    check_time TEXT NOT NULL CHECK (check_time GLOB '[0-2][0-9]:[0-5][0-9]' AND check_time < '24:00'),
    reminder_time TEXT NOT NULL CHECK (reminder_time GLOB '[0-2][0-9]:[0-5][0-9]' AND reminder_time < '24:00'),
    UNIQUE (check_id, sequence),
    UNIQUE (check_id, id)
);

CREATE TABLE IF NOT EXISTS check_members (
    check_id INTEGER NOT NULL REFERENCES checks(id),
    user_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')),
    PRIMARY KEY (check_id, user_id)
);

CREATE TABLE IF NOT EXISTS daily_checkins (
    id INTEGER PRIMARY KEY,
    check_id INTEGER NOT NULL REFERENCES checks(id),
    schedule_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    thread_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')),
    closed_at TEXT,
    UNIQUE (check_id, schedule_id, date),
    FOREIGN KEY (check_id, schedule_id) REFERENCES check_schedules(check_id, id)
);

CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY,
    check_id INTEGER NOT NULL REFERENCES checks(id),
    schedule_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    verification_method TEXT NOT NULL CHECK (verification_method IN ('button', 'photo')),
    verified_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')),
    UNIQUE (check_id, schedule_id, user_id, date),
    FOREIGN KEY (check_id, schedule_id, date)
        REFERENCES daily_checkins(check_id, schedule_id, date)
);
"""


def serialize_datetime(value: datetime) -> str:
    """Reject naive datetimes and normalize aware values to UTC for storage."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware datetime is required.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


@contextmanager
def connect_database(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Enable foreign keys per connection; commit/rollback and always close."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(db_path: Path = DB_PATH) -> None:
    """Create missing tables without clearing existing records."""
    with connect_database(db_path) as connection:
        connection.executescript("BEGIN;\n" + SCHEMA + "\nCOMMIT;")


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")
