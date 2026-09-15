"""Discord adapter for the pure scheduler decisions."""

import asyncio
import logging
from datetime import datetime, timezone

import discord

from doneyet.repository import CheckRepository
from doneyet.scheduler import due_sessions
from doneyet.verification import ButtonVerificationView
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class CheckinScheduler:
    def __init__(self, client: discord.Client, repository: CheckRepository):
        self.client, self.repository = client, repository
        self._lock = asyncio.Lock()

    async def tick(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        created = 0
        async with self._lock:
            for guild in self.client.guilds:
                for check in await asyncio.to_thread(self.repository.list_checks, guild.id):
                    try:
                        local = now.astimezone(ZoneInfo(check.timezone))
                        await self._process_reminders(check, guild, local)
                        await self._close_threads(check, guild, local)
                        for due in due_sessions(check, now):
                            if await asyncio.to_thread(self.repository.checkin_exists, check.id, due.schedule.id, due.local_date):
                                continue
                            channel = self.client.get_channel(check.channel_id)
                            if channel is None:
                                logger.warning("Channel %s for Check %s is unavailable", check.channel_id, check.id)
                                continue
                            content = f"📋 {check.name} — {due.schedule.sequence}/{check.daily_sessions}\n{due.local_date} · {due.schedule.sequence}회차"
                            view = ButtonVerificationView(self.repository, check.id, due.schedule.id, due.local_date) if check.verification_mode.value in ("button", "either") else None
                            # Keep the parent message as the daily entry point; for
                            # Thread based checks also place the button inside the thread.
                            message = await channel.send(content)
                            thread_id = None
                            if check.verification_mode.value in ("button", "photo", "either"):
                                thread_name = f"{check.name} · {due.local_date} · {due.schedule.sequence}회차 인증"
                                thread = await message.create_thread(name=thread_name[:100])
                                thread_id = thread.id
                                if view is not None:
                                    await thread.send("아래 버튼을 눌러 인증하세요.", view=view)
                            if await asyncio.to_thread(self.repository.create_daily_checkin, check.id, due.schedule.id, due.local_date, message.id, thread_id):
                                created += 1
                    except Exception:
                        logger.exception("Scheduler failed for Check %s", check.id)
        return created

    async def _process_reminders(self, check, guild, local):
        for schedule in check.schedules:
            if local.strftime("%H:%M") < schedule.reminder_time or local.weekday() not in check.weekdays:
                continue
            date = local.date().isoformat()
            if not await asyncio.to_thread(self.repository.checkin_exists, check.id, schedule.id, date):
                continue
            if await asyncio.to_thread(self.repository.reminder_sent, check.id, schedule.id, date):
                continue
            ids = await asyncio.to_thread(self.repository.unverified_member_ids, check.id, schedule.id, date)
            if not ids or not await asyncio.to_thread(self.repository.mark_reminder_sent, check.id, schedule.id, date):
                continue
            channel = self.client.get_channel(check.channel_id)
            rows = await asyncio.to_thread(self.repository.list_daily_checkins, check.id)
            target_id = next((r["thread_id"] for r in rows if r["schedule_id"] == schedule.id and r["date"] == date and r["thread_id"]), None)
            target = self.client.get_channel(target_id) if target_id else channel
            if target:
                names = [getattr(guild.get_member(uid), "mention", str(uid)) for uid in ids]
                await target.send(f"🔔 아직 {schedule.sequence}회차 체크를 완료하지 않았어요.\n" + "\n".join(names))

    async def _close_threads(self, check, guild, local):
        for row in await asyncio.to_thread(self.repository.list_daily_checkins, check.id):
            if not row["thread_id"] or row["date"] >= local.date().isoformat():
                continue
            thread = self.client.get_channel(row["thread_id"])
            if thread and not getattr(thread, "archived", False):
                done = await asyncio.to_thread(self.repository.verified_member_ids, check.id, row["schedule_id"], row["date"])
                pending = await asyncio.to_thread(self.repository.unverified_member_ids, check.id, row["schedule_id"], row["date"])
                names = lambda ids: "\n".join(getattr(guild.get_member(uid), "display_name", str(uid)) for uid in ids) or "없음"
                await thread.send(f"오늘 인증 완료한 사람:\n{names(done)}\n\n오늘 인증하지 않은 사람:\n{names(pending)}")
                await thread.edit(locked=True, archived=True)
