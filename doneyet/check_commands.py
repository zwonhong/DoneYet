"""Check command entry points and creation access policy."""

import discord
from discord import app_commands

from doneyet.check_ui import CreateCheckView
from doneyet.repository import CheckRepository


def can_create_check(interaction: discord.Interaction) -> bool:
    """For now, any guild member may create a Check; no admin permission needed."""
    return interaction.guild_id is not None


class CheckCommands(app_commands.Group):
    def __init__(self, repository: CheckRepository) -> None:
        super().__init__(name="check", description="DoneYet? Check 설정", guild_only=True)
        self.repository = repository

    @app_commands.command(name="create", description="설정 패널에서 새로운 Check를 만듭니다.")
    async def create(self, interaction: discord.Interaction) -> None:
        if not can_create_check(interaction):
            await interaction.response.send_message("서버에서 실행해 주세요.", ephemeral=True)
            return
        view = CreateCheckView(interaction.user.id, interaction.guild_id, self.repository)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)
        view.message = await interaction.original_response()
