import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from doneyet.database import connect_database, initialize_database, serialize_datetime


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data" / "test.db"
        initialize_database(self.path)
        with connect_database(self.path) as db:
            db.execute("INSERT INTO checks (id, guild_id, channel_id, name, verification_mode) VALUES (1, 10, 20, 'Test', 'either')")
            db.execute("INSERT INTO check_schedules VALUES (1, 1, 1, '09:00', '22:00')")

    def test_initialization_preserves_data_and_enables_foreign_keys(self):
        initialize_database(self.path)
        with connect_database(self.path) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            self.assertEqual(tables, {'checks', 'check_days', 'check_schedules', 'check_members', 'daily_checkins', 'verifications'})
            self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            check = db.execute('SELECT * FROM checks').fetchone()
            self.assertEqual(check['timezone'], 'Asia/Seoul')
            self.assertEqual(datetime.fromisoformat(check['created_at']).utcoffset(), timedelta(0))
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')), [])

    def test_unique_constraints_and_distinct_sessions(self):
        with connect_database(self.path) as db:
            statements = [
                "INSERT INTO check_days VALUES (1, 0)",
                "INSERT INTO check_members (check_id, user_id) VALUES (1, 30)",
                "INSERT INTO daily_checkins (check_id, schedule_id, date, message_id) VALUES (1, 1, '2026-09-11', 40)",
                "INSERT INTO verifications (check_id, schedule_id, user_id, date, verification_method) VALUES (1, 1, 30, '2026-09-11', 'button')",
            ]
            for statement in statements:
                db.execute(statement)
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO check_schedules VALUES (2, 1, 1, '10:00', '23:00')")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(statements[-1].replace("'button'", "'photo'"))
            db.execute("INSERT INTO check_schedules VALUES (2, 1, 2, '21:00', '23:00')")
            db.execute("INSERT INTO daily_checkins (check_id, schedule_id, date, message_id) VALUES (1, 2, '2026-09-11', 41)")
            db.execute("INSERT INTO verifications (check_id, schedule_id, user_id, date, verification_method) VALUES (1, 2, 30, '2026-09-11', 'photo')")

    def test_foreign_keys_reject_orphans_and_cross_check_schedule(self):
        with connect_database(self.path) as db:
            db.execute("INSERT INTO checks (id, guild_id, channel_id, name, verification_mode) VALUES (2, 10, 21, 'Other', 'button')")
            for statement in [
                'INSERT INTO check_days VALUES (99, 0)',
                'INSERT INTO check_members (check_id, user_id) VALUES (99, 30)',
                "INSERT INTO check_schedules VALUES (2, 99, 1, '09:00', '22:00')",
                "INSERT INTO daily_checkins (check_id, schedule_id, date, message_id) VALUES (2, 1, '2026-09-11', 40)",
                "INSERT INTO verifications (check_id, schedule_id, user_id, date, verification_method) VALUES (1, 1, 30, '2026-09-11', 'button')",
                'DELETE FROM checks WHERE id = 1',
            ]:
                with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)

    def test_transaction_rolls_back(self):
        with self.assertRaises(RuntimeError):
            with connect_database(self.path) as db:
                db.execute('INSERT INTO check_days VALUES (1, 0)')
                raise RuntimeError('Abort')
        with connect_database(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM check_days').fetchone()[0], 0)

    def test_aware_datetime_round_trip(self):
        value = datetime(2026, 9, 11, 1, 30, tzinfo=timezone(timedelta(hours=9)))
        stored = serialize_datetime(value)
        self.assertEqual(stored, '2026-09-10T16:30:00.000000+00:00')
        self.assertEqual(datetime.fromisoformat(stored), value)
        with self.assertRaises(ValueError):
            serialize_datetime(datetime(2026, 9, 11))


if __name__ == '__main__':
    unittest.main()
