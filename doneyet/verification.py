"""Persistent Button verification view and repository operation."""

import sqlite3

import discord

from doneyet.repository import CheckRepository


class ButtonVerificationView(discord.ui.View):
    def __init__(self, repository: CheckRepository, check_id: int, schedule_id: int, date: str):
        super().__init__(timeout=None)
        self.repository = repository
        self.check_id, self.schedule_id, self.date = check_id, schedule_id, date
        button = discord.ui.Button(label="완료", emoji="✅", style=discord.ButtonStyle.success,
                                   custom_id=f"doneyet:verify:{check_id}:{schedule_id}:{date}")
        button.callback = self.verify
        self.add_item(button)

    async def verify(self, interaction: discord.Interaction) -> None:
        try:
            check = await __import__('asyncio').to_thread(self.repository.get_check, interaction.guild_id, self.check_id)
            if check is None:
                await interaction.response.send_message("이 Check를 찾을 수 없습니다.", ephemeral=True); return
            if not await __import__('asyncio').to_thread(self.repository.is_check_member, self.check_id, interaction.user.id):
                await interaction.response.send_message("이 Check의 참여자가 아닙니다.", ephemeral=True); return
            with __import__('doneyet.database', fromlist=['connect_database']).connect_database(self.repository.db_path) as db:
                try:
                    db.execute("INSERT INTO verifications (check_id, schedule_id, user_id, date, verification_method) VALUES (?, ?, ?, ?, 'button')",
                               (self.check_id, self.schedule_id, interaction.user.id, self.date))
                except sqlite3.IntegrityError:
                    await interaction.response.send_message(f"{interaction.user.display_name}님, 이미 이번 회차를 완료했어요. ✅", ephemeral=True); return
            await interaction.response.send_message(f"{interaction.user.display_name}님 인증 완료! ✅", ephemeral=True)
        except Exception:
            await interaction.response.send_message("인증 처리 중 오류가 발생했습니다.", ephemeral=True)
