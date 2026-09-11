"""Guild-scoped Check browsing and explicit deletion confirmation."""

import asyncio
import logging

import discord

from doneyet.models import Check
from doneyet.repository import CheckRepository


logger = logging.getLogger(__name__)
PAGE_SIZE = 5
DAYS = ("월", "화", "수", "목", "금", "토", "일")


def summary(check: Check) -> str:
    days = "매일" if len(check.weekdays) == 7 else " / ".join(DAYS[d] for d in check.weekdays)
    return (f"채널: <#{check.channel_id}>\n인증: {check.verification_mode.value.title()} | 요일: {days or '없음'}\n"
            f"하루 {check.daily_sessions}회 | 참여자 {len(check.members)}명 | Enabled: {check.enabled}")


def detail_pages(check: Check) -> list[discord.Embed]:
    # Split even data created outside the UI, where member/session limits differ.
    text = (f"이름: {discord.utils.escape_markdown(check.name)}\nID: {check.id}\n{summary(check)}\n"
            f"시간대: {check.timezone}\n\n참여자:\n"
            + (" ".join(f"<@{m.user_id}>" for m in check.members) or "없음")
            + "\n\n회차별 시간:\n"
            + "\n".join(f"{s.sequence}회차: {s.check_time} → Reminder {s.reminder_time}" for s in check.schedules))
    pages = [discord.Embed(title="DoneYet? Check 상세", description=text[i:i + 3500], colour=discord.Colour.blurple())
             for i in range(0, len(text), 3500)]
    for i, page in enumerate(pages, 1):
        page.set_footer(text=f"Check ID: {check.id} · {i}/{len(pages)}")
    return pages


class CheckBrowser(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int, repository: CheckRepository,
                 checks: list[Check], mode: str) -> None:
        super().__init__(timeout=300)
        self.owner_id, self.guild_id = owner_id, guild_id
        self.repository, self.checks, self.mode = repository, checks, mode
        self.page = 0
        self.selected: Check | None = None
        self.details: list[discord.Embed] = []
        self.detail_page = 0
        self.closed = False
        self.lock = asyncio.Lock()
        self.revision = 0
        self.message = None
        self.rebuild()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id or interaction.guild_id != self.guild_id:
            await interaction.response.send_message("명령어를 실행한 사용자만 같은 서버에서 조작할 수 있습니다.", ephemeral=True)
            return False
        if self.closed or self.is_finished():
            await interaction.response.send_message("종료된 화면입니다. 명령어를 다시 실행하세요.", ephemeral=True)
            return False
        return True

    def embed(self) -> discord.Embed:
        if self.selected:
            embed = self.details[self.detail_page].copy()
            if self.mode == "delete":
                embed.title = "이 Check를 삭제할까요?"
                embed.set_footer(text=f"ID: {self.selected.id} · {self.detail_page + 1}/{len(self.details)} · Confirm 시 관련 DB 기록도 삭제됩니다.")
            return embed
        embed = discord.Embed(title="DoneYet? Check 목록", colour=discord.Colour.blurple())
        for check in self.checks[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]:
            embed.add_field(name=f"{discord.utils.escape_markdown(check.name)[:210]} · ID {check.id}", value=summary(check), inline=False)
        embed.set_footer(text=f"{self.page + 1}/{max(1, (len(self.checks) + PAGE_SIZE - 1) // PAGE_SIZE)} · 총 {len(self.checks)}개")
        return embed

    def bind(self, item, action):
        revision = self.revision

        async def callback(interaction):
            value = item.values[0] if isinstance(item, discord.ui.Select) else None
            await self.handle(interaction, action, revision, value)

        item.callback = callback
        self.add_item(item)

    def rebuild(self):
        self.revision += 1
        self.clear_items()
        if self.selected:
            if len(self.details) > 1:
                self.bind(discord.ui.Button(label="이전 상세", disabled=self.detail_page == 0), "detail_prev")
                self.bind(discord.ui.Button(label="다음 상세", disabled=self.detail_page == len(self.details) - 1), "detail_next")
            if self.mode == "delete":
                self.bind(discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger), "confirm")
            self.bind(discord.ui.Button(label="목록으로"), "back")
        else:
            if self.mode != "list":
                self.bind(discord.ui.Select(placeholder="Check 선택", options=[
                    discord.SelectOption(label=check.name[:100], value=str(check.id), description=f"ID {check.id}")
                    for check in self.checks[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]
                ], row=0), "select")
            self.bind(discord.ui.Button(label="이전", row=1, disabled=self.page == 0), "prev")
            self.bind(discord.ui.Button(label="다음", row=1, disabled=(self.page + 1) * PAGE_SIZE >= len(self.checks)), "next")
        self.bind(discord.ui.Button(label="Cancel" if self.mode == "delete" else "닫기", row=2), "cancel")

    async def handle(self, interaction, action, revision, value=None):
        if not await self.interaction_check(interaction):
            return
        if self.lock.locked():
            await interaction.response.send_message("처리 중입니다. 잠시 기다려 주세요.", ephemeral=True)
            return
        async with self.lock:
            if revision != self.revision:
                await interaction.response.send_message("현재 화면에서 다시 선택하세요.", ephemeral=True)
                return
            await interaction.response.defer()
            if action == "cancel":
                self.closed = True
                self.stop()
                await interaction.edit_original_response(content="종료했습니다. 삭제하지 않았습니다.", embed=None, view=None)
                return
            if action == "select":
                # Never trust the select payload: re-query by BOTH guild and ID.
                self.selected = await asyncio.to_thread(self.repository.get_check, self.guild_id, int(value))
                if self.selected is None:
                    await interaction.followup.send("이 서버에서 해당 Check를 찾을 수 없습니다.", ephemeral=True)
                    return
                self.details = detail_pages(self.selected)
                self.detail_page = 0
            elif action == "confirm":
                if self.mode != "delete" or self.selected is None:
                    await interaction.followup.send("먼저 삭제할 Check를 선택하세요.", ephemeral=True)
                    return
                deleted = await asyncio.to_thread(self.repository.delete_check, self.guild_id, self.selected.id, expected=self.selected)
                self.closed = True
                self.stop()
                await interaction.edit_original_response(
                    content=f"Check ID {self.selected.id}를 삭제했습니다." if deleted else "이미 삭제되었거나 설정이 변경된 Check입니다. 목록에서 다시 확인하세요.",
                    embed=None, view=None)
                return
            elif action == "back":
                self.selected = None
            elif action in ("prev", "next"):
                self.page = max(0, min((len(self.checks) - 1) // PAGE_SIZE, self.page + (1 if action == "next" else -1)))
            elif action in ("detail_prev", "detail_next"):
                self.detail_page = max(0, min(len(self.details) - 1, self.detail_page + (1 if action == "detail_next" else -1)))
            self.rebuild()
            await interaction.edit_original_response(embed=self.embed(), view=self)
            self.message = await interaction.original_response()

    async def on_timeout(self):
        async with self.lock:
            if self.closed:
                return
            self.closed = True
            self.stop()
            if self.message:
                try:
                    await self.message.edit(content="시간이 만료되었습니다. 명령어를 다시 실행하세요.", embed=None, view=None)
                except discord.HTTPException:
                    logger.warning("Could not close Check browser", exc_info=True)

    async def on_error(self, interaction, error, item):
        logger.error("Check browser failed", exc_info=(type(error), error, error.__traceback__))
        message = "처리에 실패했습니다. 잠시 후 다시 시도하세요." if not self.closed else "처리는 종료되었지만 결과 표시를 완료하지 못했습니다. 목록을 다시 확인하세요."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
