"""Check command entry points and creation access policy."""

import asyncio
import logging

import discord
from discord import app_commands

from doneyet.check_ui import CreateCheckView
from doneyet.check_browser import CheckBrowser
from doneyet.repository import CheckRepository
from doneyet.leaderboard import calculate_month
from datetime import datetime


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

    @app_commands.command(name="leaderboard", description="월간 Check Leaderboard를 표시합니다.")
    @app_commands.describe(check_id="Check ID", year="연도(생략 시 현재 연도)", month="월(생략 시 현재 월)")
    async def leaderboard(self, interaction: discord.Interaction, check_id: int, year: int | None = None, month: int | None = None) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message("서버에서 실행해주세요.", ephemeral=True); return
        now = datetime.now()
        year, month = year or now.year, month or now.month
        if month < 1 or month > 12:
            await interaction.response.send_message("월은 1~12 사이여야 합니다.", ephemeral=True); return
        check = await asyncio.to_thread(self.repository.get_check, interaction.guild_id, check_id)
        if check is None:
            await interaction.response.send_message("현재 서버의 Check가 아닙니다.", ephemeral=True); return
        rows = await asyncio.to_thread(calculate_month, self.repository, check, year, month)
        if not rows:
            await interaction.response.send_message("참여자가 없습니다.", ephemeral=True); return
        lines = [f"🏆 {year}년 {month}월 — {check.name}"]
        for i, (uid, done, scheduled, rate) in enumerate(rows, 1):
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            lines.append(f"{i}. {name} — {done} / {scheduled} ({rate:.1%})")
        await interaction.response.send_message("\n".join(lines))
