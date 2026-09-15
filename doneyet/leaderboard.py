"""Pure monthly leaderboard calculation."""
import calendar
from datetime import date, datetime, timezone
from doneyet.database import connect_database

def calculate_month(repository, check, year: int, month: int):
    start, days = date(year, month, 1), calendar.monthrange(year, month)[1]
    with connect_database(repository.db_path) as db:
        rows = db.execute("SELECT user_id, joined_at, left_at FROM check_members WHERE check_id=?", (check.id,)).fetchall()
        completed = {(r[0], r[1], r[2]) for r in db.execute("SELECT user_id,date,schedule_id FROM verifications WHERE check_id=? AND date LIKE ?", (check.id, f"{year:04d}-{month:02d}-%"))}
    result=[]
    for row in rows:
        joined = datetime.fromisoformat(row[1]).date()
        left = datetime.fromisoformat(row[2]).date() if row[2] else None
        scheduled = 0; done = 0
        for offset in range(days):
            day = start.fromordinal(start.toordinal()+offset)
            if day.weekday() not in check.weekdays or day < joined or (left and day >= left): continue
            scheduled += check.daily_sessions
            done += sum((row[0], day.isoformat(), schedule.id) in completed for schedule in check.schedules)
        result.append((row[0], done, scheduled, (done/scheduled if scheduled else 0.0)))
    return sorted(result, key=lambda x: (-x[3], -x[1], x[0]))
