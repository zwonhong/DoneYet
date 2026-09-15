import logging
import sys
import asyncio
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import tasks

from doneyet.check_commands import CheckCommands
from doneyet.repository import CheckRepository
from doneyet.member_commands import MemberCommands
from doneyet.checkin_scheduler import CheckinScheduler
from doneyet.verification import ButtonVerificationView


logger = logging.getLogger(__name__)


def command_paths(payload: dict, prefix: str = "") -> list[str]:
    """Extract slash invocation paths from local or Discord-returned payloads."""
    path = f"{prefix} {payload['name']}" if prefix else f"/{payload['name']}"
    subcommands = [option for option in payload.get("options", []) if option.get("type") in (1, 2)]
    if not subcommands:
        return [path]
    return [name for option in subcommands for name in command_paths(option, path)]


@app_commands.command(name="test", description="Check whether DoneYet? is running.")
async def test_command(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("DoneYet? is running! ✅")


class DoneYetBot(discord.Client):
    def __init__(self, *, guild_id: int | None = None) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        intents.messages = True
        # Required by Discord to deliver guild message events to on_message.
        intents.message_content = True
        super().__init__(intents=intents)
        self.development_guild_id = guild_id
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(test_command)
        check_commands = CheckCommands(CheckRepository())
        check_commands.add_command(MemberCommands(check_commands.repository))
        self.tree.add_command(check_commands)
        self.repository = check_commands.repository
        self.scheduler = CheckinScheduler(self, self.repository)
        self._scheduler_started = False
        self._views_restored = False

    async def setup_hook(self) -> None:
        # All modules/groups are registered in __init__ before any sync occurs.
        print(f"DoneYet? startup: {Path(__file__).resolve()} | Python: {sys.executable} | application_id={self.application_id}", flush=True)
        await self.sync_commands()
        if self.development_guild_id is not None:
            guild = discord.Object(id=self.development_guild_id)
            # sync(guild=...) alone would send an empty guild tree. Copy first.
            self.tree.copy_global_to(guild=guild)
            await self.sync_commands(guild=guild)

    async def sync_commands(self, *, guild: discord.Object | None = None) -> None:
        scope = "global" if guild is None else f"guild:{guild.id}"
        local = self.tree.get_commands(guild=guild)
        expected = sorted(name for command in local for name in command_paths(command.to_dict(self.tree)))
        print(f"DoneYet? syncing [{scope}]: {', '.join(expected) or '(empty)'}", flush=True)
        try:
            synced = await self.tree.sync(guild=guild)
        except Exception:
            logger.exception("DoneYet? command sync failed [%s] application_id=%s", scope, self.application_id)
            raise
        actual = sorted(name for command in synced for name in command_paths(command.to_dict()))
        print(f"Synced {len(synced)} application commands [{scope}]:", flush=True)
        for command in synced:
            print(f"- /{command.name} (id={command.id})", flush=True)
        if actual != expected:
            logger.error("Command sync mismatch [%s]: expected %s, received %s", scope, expected, actual)
            raise RuntimeError(f"Command sync mismatch [{scope}]: expected {expected}, received {actual}")

    async def on_ready(self) -> None:
        print(f"DoneYet? logged in as {self.user}", flush=True)
        # ``on_ready`` is also called directly by unit tests; before login
        # discord.py has no ready event, so starting a loop would fail.
        if getattr(self, "_ready", None) is None:
            return
        if not self._views_restored:
            await self.restore_verification_views()
            self._views_restored = True
        if not self._scheduler_started:
            self._scheduler_started = True
            self.daily_scheduler.start()

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.webhook_id or not isinstance(message.channel, discord.Thread):
            return
        row = await asyncio.to_thread(self.repository.get_checkin_by_thread, message.channel.id)
        if row is None or not message.attachments:
            return
        check_id, schedule_id, date = row
        check = await asyncio.to_thread(self.repository.get_check, message.guild.id if message.guild else 0, check_id)
        if check is None or check.verification_mode.value not in ("photo", "either"):
            return
        if not await asyncio.to_thread(self.repository.is_check_member, check_id, message.author.id):
            return
        image = any((a.content_type or "").lower().startswith("image/") or a.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) for a in message.attachments)
        if not image:
            return
        created = await asyncio.to_thread(self.repository.create_verification, check_id, schedule_id, message.author.id, date, "photo")
        if created:
            await message.channel.send(f"{message.author.display_name}님 인증 완료! ✅")
        else:
            await message.channel.send(f"{message.author.display_name}님, 이미 이번 회차를 완료했어요. ✅")

    async def restore_verification_views(self) -> None:
        """Re-register buttons for persisted check-ins after a restart."""
        for guild in self.guilds:
            for check in await asyncio.to_thread(self.repository.list_checks, guild.id):
                if check.verification_mode.value not in ("button", "photo", "either"):
                    continue
                rows = await asyncio.to_thread(self.repository.list_daily_checkins, check.id)
                for row in rows:
                    # Register globally by stable custom_id so buttons posted
                    # inside the verification Thread also survive restarts.
                    self.add_view(ButtonVerificationView(self.repository, check.id, row["schedule_id"], row["date"]))

    @tasks.loop(seconds=30)
    async def daily_scheduler(self) -> None:
        await self.scheduler.tick()

    @daily_scheduler.before_loop
    async def wait_for_scheduler_ready(self) -> None:
        if getattr(self._connection, "_ready", None) is None:
            return
        await self.wait_until_ready()

    async def close(self) -> None:
        if self._scheduler_started:
            self.daily_scheduler.cancel()
            self._scheduler_started = False
        await super().close()
