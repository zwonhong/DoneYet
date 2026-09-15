"""Discord adapter for the pure scheduler decisions."""

import asyncio
import logging
from datetime import datetime, timezone

import discord

from doneyet.repository import CheckRepository
from doneyet.scheduler import due_sessions
from doneyet.verification import ButtonVerificationView

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
                        for due in due_sessions(check, now):
                            if await asyncio.to_thread(self.repository.checkin_exists, check.id, due.schedule.id, due.local_date):
                                continue
                            channel = self.client.get_channel(check.channel_id)
                            if channel is None:
                                logger.warning("Channel %s for Check %s is unavailable", check.channel_id, check.id)
                                continue
                            content = f"📋 {check.name} — {due.schedule.sequence}/{check.daily_sessions}\n{due.local_date} · {due.schedule.sequence}회차"
                            view = ButtonVerificationView(self.repository, check.id, due.schedule.id, due.local_date) if check.verification_mode.value in ("button", "either") else None
                            message = await channel.send(content, view=view)
                            thread_id = None
                            if check.verification_mode.value in ("photo", "either"):
                                thread = await message.create_thread(name=f"{due.local_date} · {due.schedule.sequence}회차 인증")
                                thread_id = thread.id
                            if await asyncio.to_thread(self.repository.create_daily_checkin, check.id, due.schedule.id, due.local_date, message.id, thread_id):
                                created += 1
                    except Exception:
                        logger.exception("Scheduler failed for Check %s", check.id)
        return created
