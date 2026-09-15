"""Timezone-aware daily Check-in scheduler."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from doneyet.models import Check, CheckSchedule

# A restart may miss a few scheduler ticks. Recover sessions up to 30 minutes
# after their scheduled time; older missed sessions are intentionally skipped.
RECOVERY_WINDOW = timedelta(minutes=30)


@dataclass(frozen=True)
class DueSession:
    check: Check
    schedule: CheckSchedule
    local_date: str


def due_sessions(check: Check, now: datetime, *, recovery_window: timedelta = RECOVERY_WINDOW) -> list[DueSession]:
    """Return sessions due at *now*; naive datetimes are rejected."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Scheduler requires a timezone-aware datetime.")
    if not check.enabled:
        return []
    local = now.astimezone(ZoneInfo(check.timezone))
    if local.weekday() not in check.weekdays:
        return []
    due = []
    for schedule in check.schedules:
        hour, minute = map(int, schedule.check_time.split(":"))
        scheduled = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled <= local < scheduled + recovery_window:
            due.append(DueSession(check, schedule, local.date().isoformat()))
    return due
