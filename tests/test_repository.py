import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from doneyet.database import connect_database, initialize_database
from doneyet.models import CheckInput, ScheduleInput, VerificationMode
from doneyet.repository import CheckRepository


class CheckRepositoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'test.db'
        initialize_database(self.path)
        self.repo = CheckRepository(self.path)
        self.study = CheckInput(
            guild_id=100, channel_id=200, name='공부',
            verification_mode=VerificationMode.EITHER,
            member_ids=(301, 300), weekdays=(4, 3, 2, 1, 0),
            schedules=(ScheduleInput('09:00', '12:00'), ScheduleInput('21:00', '23:30')),
        )

    def test_create_and_reload_core_examples(self):
        study = self.repo.create_check(self.study)
        supplement = self.repo.create_check(replace(
            self.study, name='영양제', channel_id=201,
            verification_mode=VerificationMode.BUTTON, weekdays=tuple(range(7)),
            member_ids=(300, 301, 302), schedules=(ScheduleInput('09:00', '22:00'),),
        ))
        initialize_database(self.path)
        restarted = CheckRepository(self.path)
        self.assertEqual(restarted.get_check(100, study.id), study)
        self.assertEqual(restarted.list_checks(100), [study, supplement])
        self.assertEqual(study.daily_sessions, 2)
        self.assertEqual(supplement.daily_sessions, 1)
        self.assertEqual(study.weekdays, (0, 1, 2, 3, 4))
        self.assertEqual([s.sequence for s in study.schedules], [1, 2])
        self.assertEqual([m.user_id for m in study.members], [300, 301])
        self.assertIsNotNone(study.created_at.utcoffset())
        self.assertIsNotNone(study.members[0].joined_at.utcoffset())

    def test_reads_are_guild_scoped(self):
        check = self.repo.create_check(self.study)
        other = self.repo.create_check(replace(self.study, guild_id=101))
        self.assertIsNone(self.repo.get_check(101, check.id))
        self.assertIsNone(self.repo.get_check(100, 999))
        self.assertEqual(self.repo.list_checks(101), [other])
        self.assertEqual(self.repo.list_checks(999), [])

    def test_invalid_input_does_not_write(self):
        for changes in [
            {'name': ' '}, {'guild_id': 0}, {'channel_id': True},
            {'verification_mode': 'invalid'}, {'timezone': 'Invalid/Zone'},
            {'enabled': 1}, {'member_ids': ()}, {'member_ids': (300, 300)},
            {'member_ids': (-1,)}, {'weekdays': ()}, {'weekdays': (0, 0)},
            {'weekdays': (7,)}, {'schedules': ()},
            {'schedules': (ScheduleInput('24:00', '22:00'),)},
            {'schedules': (ScheduleInput('09:00', '9:30'),)},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.repo.create_check(replace(self.study, **changes))
        self.assertEqual(self.repo.list_checks(100), [])

    def test_late_database_failure_rolls_back_entire_check(self):
        with connect_database(self.path) as db:
            db.execute("""CREATE TRIGGER fail_schedule BEFORE INSERT ON check_schedules
                          WHEN NEW.sequence = 2 BEGIN
                          SELECT RAISE(ABORT, 'Simulated write failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.create_check(self.study)
        with connect_database(self.path) as db:
            for table in ('checks', 'check_days', 'check_members', 'check_schedules'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
