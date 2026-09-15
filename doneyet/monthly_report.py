from datetime import date
from doneyet.leaderboard import calculate_month

def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)

def build_report(repository, check, year, month, guild):
    rows = calculate_month(repository, check, year, month)
    lines = [f"🏆 {year}년 {month}월 DoneYet? 결과", f"💊 {check.name}"]
    for i, (uid, done, scheduled, rate) in enumerate(rows, 1):
        member = guild.get_member(uid)
        name = member.display_name if member else str(uid)
        lines.append(f"{i}. {name} — {done} / {scheduled} ({rate:.1%})")
    lines.append("\n다음 달도 DoneYet?")
    return "\n".join(lines)
