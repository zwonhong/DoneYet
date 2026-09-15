"""Transactional Check creation and guild-scoped reads."""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from doneyet.database import DB_PATH, connect_database
from doneyet.models import Check, CheckInput, CheckMember, CheckSchedule, ScheduleInput, VerificationMode


def _validate_id(value: int) -> None:
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise ValueError("Discord IDs must be positive SQLite-compatible integers.")


def validate_schedule_input(schedule: ScheduleInput) -> None:
    for value in (schedule.check_time, schedule.reminder_time):
        if not isinstance(value, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
            raise ValueError("시간은 00:00~23:59 범위의 HH:MM 형식으로 입력하세요.")
    # Fixed-width HH:MM strings sort chronologically after format validation.
    if schedule.reminder_time <= schedule.check_time:
        raise ValueError("Reminder Time은 Check Time보다 이후여야 합니다. 다음 날 Reminder는 지원하지 않습니다.")


def validate_check_input(data: CheckInput) -> None:
    """Validate without writing, also usable by a confirmation UI."""
    _validate_id(data.guild_id)
    _validate_id(data.channel_id)
    if not isinstance(data.name, str) or not data.name.strip():
        raise ValueError("Check name must not be empty.")
    VerificationMode(data.verification_mode)
    if type(data.enabled) is not bool:
        raise ValueError("enabled must be a boolean.")
    if not isinstance(data.timezone, str) or not data.timezone:
        raise ValueError("An IANA timezone is required.")
    try:
        ZoneInfo(data.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Unknown IANA timezone.") from exc
    if not data.member_ids or len(set(data.member_ids)) != len(data.member_ids):
        raise ValueError("At least one member is required; duplicate members are not allowed.")
    for user_id in data.member_ids:
        _validate_id(user_id)
    if not data.weekdays or len(set(data.weekdays)) != len(data.weekdays):
        raise ValueError("At least one weekday is required; duplicate weekdays are not allowed.")
    if any(type(day) is not int or not 0 <= day <= 6 for day in data.weekdays):
        raise ValueError("Weekdays must be integers from 0 (Monday) to 6 (Sunday).")
    if not data.schedules:
        raise ValueError("At least one schedule is required.")
    for schedule in data.schedules:
        validate_schedule_input(schedule)


def _read_check(db: sqlite3.Connection, row: sqlite3.Row) -> Check:
    check_id = row["id"]
    return Check(
        id=check_id, guild_id=row["guild_id"], channel_id=row["channel_id"],
        name=row["name"], verification_mode=VerificationMode(row["verification_mode"]),
        timezone=row["timezone"], enabled=bool(row["enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        weekdays=tuple(r[0] for r in db.execute(
            "SELECT weekday FROM check_days WHERE check_id = ? ORDER BY weekday", (check_id,))),
        members=tuple(CheckMember(r["user_id"], datetime.fromisoformat(r["joined_at"]),
                                   datetime.fromisoformat(r["left_at"]) if r["left_at"] else None,
                                   bool(r["active"]))
                      for r in db.execute("SELECT * FROM check_members WHERE check_id = ? AND active = 1 ORDER BY user_id", (check_id,))),
        schedules=tuple(CheckSchedule(r["id"], r["sequence"], r["check_time"], r["reminder_time"])
                        for r in db.execute("SELECT * FROM check_schedules WHERE check_id = ? ORDER BY sequence", (check_id,))),
    )


class CheckRepository:
    """Use after initialize_database(); each operation opens its own connection.

    Methods are synchronous. Future async callers should offload them with
    asyncio.to_thread to avoid blocking the Discord event loop.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)

    def create_check(self, data: CheckInput) -> Check:
        validate_check_input(data)
        with connect_database(self.db_path) as db:
            cursor = db.execute(
                "INSERT INTO checks (guild_id, channel_id, name, verification_mode, timezone, enabled) VALUES (?, ?, ?, ?, ?, ?)",
                (data.guild_id, data.channel_id, data.name.strip(),
                 VerificationMode(data.verification_mode).value, data.timezone, int(data.enabled)),
            )
            check_id = cursor.lastrowid
            db.executemany("INSERT INTO check_days (check_id, weekday) VALUES (?, ?)",
                           ((check_id, day) for day in data.weekdays))
            db.executemany("INSERT INTO check_members (check_id, user_id) VALUES (?, ?)",
                           ((check_id, user_id) for user_id in data.member_ids))
            db.executemany(
                "INSERT INTO check_schedules (check_id, sequence, check_time, reminder_time) VALUES (?, ?, ?, ?)",
                ((check_id, sequence, s.check_time, s.reminder_time)
                 for sequence, s in enumerate(data.schedules, start=1)),
            )
            row = db.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
            return _read_check(db, row)

    def update_check_basic(self, guild_id: int, check_id: int, *, name=None, channel_id=None, enabled=None) -> bool:
        with connect_database(self.db_path) as db:
            fields, values = [], []
            if name is not None: fields.append("name=?"); values.append(name.strip())
            if channel_id is not None: fields.append("channel_id=?"); values.append(channel_id)
            if enabled is not None: fields.append("enabled=?"); values.append(int(enabled))
            if not fields: return False
            values.extend((check_id, guild_id))
            cur = db.execute(f"UPDATE checks SET {', '.join(fields)} WHERE id=? AND guild_id=?", values)
            return cur.rowcount > 0

    def update_check_settings(self, guild_id: int, check_id: int, data: CheckInput) -> bool:
        with connect_database(self.db_path) as db:
            if db.execute("SELECT 1 FROM checks WHERE id=? AND guild_id=?", (check_id, guild_id)).fetchone() is None:
                return False
            db.execute("UPDATE checks SET name=?, channel_id=?, verification_mode=?, enabled=? WHERE id=?", (data.name.strip(), data.channel_id, VerificationMode(data.verification_mode).value, int(data.enabled), check_id))
            db.execute("DELETE FROM check_days WHERE check_id=?", (check_id,)); db.executemany("INSERT INTO check_days(check_id,weekday) VALUES (?,?)", ((check_id,d) for d in data.weekdays))
            for i,s in enumerate(data.schedules,1):
                db.execute("UPDATE check_schedules SET check_time=?, reminder_time=? WHERE check_id=? AND sequence=?", (s.check_time,s.reminder_time,check_id,i))
            return True

    def update_schedule(self, guild_id: int, check_id: int, sequence: int, check_time: str, reminder_time: str) -> bool:
        with connect_database(self.db_path) as db:
            cur = db.execute("UPDATE check_schedules SET check_time=?, reminder_time=? WHERE check_id=? AND sequence=? AND EXISTS (SELECT 1 FROM checks WHERE id=? AND guild_id=?)", (check_time, reminder_time, check_id, sequence, check_id, guild_id))
            return cur.rowcount > 0

    def get_check(self, guild_id: int, check_id: int) -> Check | None:
        with connect_database(self.db_path) as db:
            db.execute("BEGIN")  # Keep parent and child reads in one snapshot.
            row = db.execute("SELECT * FROM checks WHERE guild_id = ? AND id = ?",
                             (guild_id, check_id)).fetchone()
            return None if row is None else _read_check(db, row)

    def list_checks(self, guild_id: int) -> list[Check]:
        with connect_database(self.db_path) as db:
            db.execute("BEGIN")
            rows = db.execute("SELECT * FROM checks WHERE guild_id = ? ORDER BY id", (guild_id,)).fetchall()
            return [_read_check(db, row) for row in rows]

    def is_check_member(self, check_id: int, user_id: int) -> bool:
        with connect_database(self.db_path) as db:
            return db.execute("SELECT 1 FROM check_members WHERE check_id = ? AND user_id = ? AND active = 1",
                              (check_id, user_id)).fetchone() is not None

    def list_members(self, guild_id: int, check_id: int) -> list[CheckMember] | None:
        """Return active members only when the Check belongs to the guild."""
        with connect_database(self.db_path) as db:
            if db.execute("SELECT 1 FROM checks WHERE id = ? AND guild_id = ?", (check_id, guild_id)).fetchone() is None:
                return None
            return [CheckMember(r["user_id"], datetime.fromisoformat(r["joined_at"]),
                                datetime.fromisoformat(r["left_at"]) if r["left_at"] else None,
                                bool(r["active"]))
                    for r in db.execute("SELECT * FROM check_members WHERE check_id = ? AND active = 1 ORDER BY user_id", (check_id,))]

    def add_member(self, guild_id: int, check_id: int, user_id: int) -> str:
        with connect_database(self.db_path) as db:
            check = db.execute("SELECT 1 FROM checks WHERE id = ? AND guild_id = ?", (check_id, guild_id)).fetchone()
            if check is None:
                return "missing_check"
            row = db.execute("SELECT active FROM check_members WHERE check_id = ? AND user_id = ?", (check_id, user_id)).fetchone()
            if row and row["active"]:
                return "already_member"
            if row:
                db.execute("UPDATE check_members SET active = 1, left_at = NULL WHERE check_id = ? AND user_id = ?", (check_id, user_id))
                return "reactivated"
            db.execute("INSERT INTO check_members (check_id, user_id) VALUES (?, ?)", (check_id, user_id))
            return "added"

    def remove_member(self, guild_id: int, check_id: int, user_id: int) -> str:
        with connect_database(self.db_path) as db:
            if db.execute("SELECT 1 FROM checks WHERE id = ? AND guild_id = ?", (check_id, guild_id)).fetchone() is None:
                return "missing_check"
            if db.execute("SELECT 1 FROM check_members WHERE check_id = ? AND user_id = ? AND active = 1", (check_id, user_id)).fetchone() is None:
                return "not_member"
            db.execute("UPDATE check_members SET active = 0, left_at = strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now') WHERE check_id = ? AND user_id = ?", (check_id, user_id))
            return "removed"

    def checkin_exists(self, check_id: int, schedule_id: int, date: str) -> bool:
        with connect_database(self.db_path) as db:
            return db.execute("SELECT 1 FROM daily_checkins WHERE check_id = ? AND schedule_id = ? AND date = ?",
                              (check_id, schedule_id, date)).fetchone() is not None

    def create_daily_checkin(self, check_id: int, schedule_id: int, date: str, message_id: int, thread_id: int | None = None) -> bool:
        """Persist a successfully sent message; UNIQUE is the final duplicate guard."""
        with connect_database(self.db_path) as db:
            try:
                db.execute("INSERT INTO daily_checkins (check_id, schedule_id, date, message_id, thread_id) VALUES (?, ?, ?, ?, ?)",
                           (check_id, schedule_id, date, message_id, thread_id))
            except sqlite3.IntegrityError:
                return False
            return True

    def get_checkin_by_thread(self, thread_id: int):
        with connect_database(self.db_path) as db:
            return db.execute("SELECT check_id, schedule_id, date FROM daily_checkins WHERE thread_id = ?", (thread_id,)).fetchone()

    def create_verification(self, check_id: int, schedule_id: int, user_id: int, date: str, method: str) -> bool:
        with connect_database(self.db_path) as db:
            try:
                db.execute("INSERT INTO verifications (check_id, schedule_id, user_id, date, verification_method) VALUES (?, ?, ?, ?, ?)", (check_id, schedule_id, user_id, date, method))
            except sqlite3.IntegrityError:
                return False
            return True

    def list_daily_checkins(self, check_id: int | None = None) -> list[dict]:
        """Return persisted check-ins, used to restore persistent buttons."""
        with connect_database(self.db_path) as db:
            if check_id is None:
                rows = db.execute("SELECT check_id, schedule_id, date, message_id, thread_id FROM daily_checkins").fetchall()
            else:
                rows = db.execute("SELECT check_id, schedule_id, date, message_id, thread_id FROM daily_checkins WHERE check_id = ?", (check_id,)).fetchall()
            return [dict(row) for row in rows]

    def reminder_sent(self, check_id: int, schedule_id: int, date: str) -> bool:
        with connect_database(self.db_path) as db:
            return db.execute("SELECT reminder_sent_at FROM daily_checkins WHERE check_id=? AND schedule_id=? AND date=?", (check_id, schedule_id, date)).fetchone()[0] is not None

    def mark_reminder_sent(self, check_id: int, schedule_id: int, date: str) -> bool:
        with connect_database(self.db_path) as db:
            try:
                db.execute("UPDATE daily_checkins SET reminder_sent_at = strftime('%Y-%m-%dT%H:%M:%f+00:00','now') WHERE check_id=? AND schedule_id=? AND date=? AND reminder_sent_at IS NULL", (check_id, schedule_id, date))
                if db.total_changes == 0:
                    return False
            except sqlite3.IntegrityError:
                return False
            return True

    def unverified_member_ids(self, check_id: int, schedule_id: int, date: str) -> list[int]:
        with connect_database(self.db_path) as db:
            return [r[0] for r in db.execute("SELECT m.user_id FROM check_members m WHERE m.check_id=? AND m.active=1 AND NOT EXISTS (SELECT 1 FROM verifications v WHERE v.check_id=? AND v.schedule_id=? AND v.date=? AND v.user_id=m.user_id)", (check_id, check_id, schedule_id, date))]

    def verified_member_ids(self, check_id: int, schedule_id: int, date: str) -> list[int]:
        with connect_database(self.db_path) as db:
            return [r[0] for r in db.execute("SELECT user_id FROM verifications WHERE check_id=? AND schedule_id=? AND date=?", (check_id, schedule_id, date))]

    def report_sent(self, check_id: int, year: int, month: int) -> bool:
        with connect_database(self.db_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS monthly_reports(check_id INTEGER, year INTEGER, month INTEGER, sent_at TEXT, PRIMARY KEY(check_id,year,month))")
            return db.execute("SELECT 1 FROM monthly_reports WHERE check_id=? AND year=? AND month=?", (check_id, year, month)).fetchone() is not None

    def mark_report_sent(self, check_id: int, year: int, month: int) -> bool:
        with connect_database(self.db_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS monthly_reports(check_id INTEGER, year INTEGER, month INTEGER, sent_at TEXT, PRIMARY KEY(check_id,year,month))")
            try:
                db.execute("INSERT INTO monthly_reports VALUES(?,?,?,strftime('%Y-%m-%dT%H:%M:%f+00:00','now'))", (check_id, year, month))
            except sqlite3.IntegrityError:
                return False
            return True

    def delete_check(self, guild_id: int, check_id: int, *, expected: Check | None = None) -> bool:
        """Delete only a Check in this guild, including all dependent records."""
        with connect_database(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM checks WHERE id = ? AND guild_id = ?",
                             (check_id, guild_id)).fetchone()
            if row is None:
                return False
            # SQLite can reuse a deleted INTEGER PRIMARY KEY. A stale confirmation
            # must not delete a replacement record or settings the user never saw.
            if expected is not None and _read_check(db, row) != expected:
                return False
            # Existing foreign keys use NO ACTION: remove children first.
            for table in ("verifications", "daily_checkins", "check_members", "check_days", "check_schedules"):
                db.execute(f"DELETE FROM {table} WHERE check_id = ?", (check_id,))
            db.execute("DELETE FROM checks WHERE id = ? AND guild_id = ?", (check_id, guild_id))
            return True
