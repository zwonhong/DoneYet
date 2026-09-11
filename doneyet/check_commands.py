"""Check command entry points and creation access policy."""

import asyncio
import logging

import discord
from discord import app_commands

from doneyet.check_ui import CreateCheckView
from doneyet.check_browser import CheckBrowser
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

    async def open_browser(self, interaction: discord.Interaction, mode: str) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message("서버에서 실행해 주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            checks = await asyncio.to_thread(self.repository.list_checks, interaction.guild_id)
        except Exception:
            logging.getLogger(__name__).exception("Could not list Checks")
            await interaction.edit_original_response(content="목록을 불러오지 못했습니다. 잠시 후 다시 시도하세요.")
            return
        if not checks:
            await interaction.edit_original_response(content="이 서버에 등록된 Check가 없습니다.")
            return
        view = CheckBrowser(interaction.user.id, interaction.guild_id, self.repository, checks, mode)
        await interaction.edit_original_response(embed=view.embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="list", description="이 서버의 Check 목록을 봅니다.")
    async def list(self, interaction: discord.Interaction) -> None:
        await self.open_browser(interaction, "list")

    @app_commands.command(name="info", description="Check를 선택하여 상세 설정을 봅니다.")
    async def info(self, interaction: discord.Interaction) -> None:
        await self.open_browser(interaction, "info")

    @app_commands.command(name="delete", description="Check를 선택하고 확인 후 삭제합니다.")
    async def delete(self, interaction: discord.Interaction) -> None:
        await self.open_browser(interaction, "delete")
