import unittest
from datetime import datetime, timezone

from doneyet.models import Check, CheckSchedule, CheckMember, VerificationMode
from doneyet.scheduler import due_sessions


class SchedulerDecisionTests(unittest.TestCase):
    def setUp(self):
        self.check = Check(
            id=1, guild_id=1, channel_id=2, name="x",
            verification_mode=VerificationMode.BUTTON, timezone="Asia/Seoul",
            enabled=True, created_at=datetime.now(timezone.utc), weekdays=(0,),
            members=(), schedules=(
                CheckSchedule(10, 1, "09:00", "22:00"),
                CheckSchedule(11, 2, "10:00", "23:00"),
            ))

    def test_active_weekday_and_reached_time(self):
        now = datetime(2026, 9, 14, 0, 2, tzinfo=timezone.utc)  # 09:02 Seoul Monday
        self.assertEqual([d.schedule.sequence for d in due_sessions(self.check, now)], [1])

    def test_inactive_weekday(self):
        now = datetime(2026, 9, 15, 0, 2, tzinfo=timezone.utc)
        self.assertEqual(due_sessions(self.check, now), [])

    def test_exact_time_is_due_but_old_missed_time_is_not(self):
        exact = datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)
        old = datetime(2026, 9, 14, 0, 30, tzinfo=timezone.utc)
        self.assertEqual([d.schedule.sequence for d in due_sessions(self.check, exact)], [1])
        self.assertEqual(due_sessions(self.check, old), [])

    def test_restart_recovery_within_thirty_minutes(self):
        restarted = datetime(2026, 9, 14, 0, 20, tzinfo=timezone.utc)
        self.assertEqual([d.schedule.sequence for d in due_sessions(self.check, restarted)], [1])

    def test_timezone_conversion(self):
        # 00:00 UTC is 09:00 in Asia/Seoul.
        now = datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(due_sessions(self.check, now)[0].local_date, "2026-09-14")

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            due_sessions(self.check, datetime(2026, 9, 14, 9, 0))


if __name__ == "__main__":
    unittest.main()
