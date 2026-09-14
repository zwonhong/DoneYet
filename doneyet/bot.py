import logging
import sys
from pathlib import Path

import discord
from discord import app_commands

from doneyet.check_commands import CheckCommands
from doneyet.repository import CheckRepository
from doneyet.member_commands import MemberCommands


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
        super().__init__(intents=intents)
        self.development_guild_id = guild_id
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(test_command)
        check_commands = CheckCommands(CheckRepository())
        check_commands.add_command(MemberCommands(check_commands.repository))
        self.tree.add_command(check_commands)

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
