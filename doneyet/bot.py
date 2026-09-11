import discord
from discord import app_commands


@app_commands.command(name="test", description="Check whether DoneYet? is running.")
async def test_command(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("DoneYet? is running! ✅")


class DoneYetBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(test_command)

    async def setup_hook(self) -> None:
        # Register global commands once at startup, rather than on each reconnect.
        await self.tree.sync()

    async def on_ready(self) -> None:
        print(f"DoneYet? logged in as {self.user}", flush=True)
