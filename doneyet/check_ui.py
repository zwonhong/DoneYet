"""In-memory single-panel Check editor. Only final confirmation writes to SQLite."""

import asyncio
import logging
import sqlite3

import discord

from doneyet.models import Check, CheckInput, ScheduleInput, VerificationMode
from doneyet.repository import CheckRepository, validate_check_input, validate_schedule_input


logger = logging.getLogger(__name__)
WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
MAX_SESSIONS = 25
MAX_PARTICIPANTS = 25
UI_TIMEOUT = 300


def settings_embed(data: CheckInput, *, created: Check) -> discord.Embed:
    embed = discord.Embed(
        title="DoneYet? Check Created",
        colour=discord.Colour.green(),
    )
    embed.add_field(name="이름", value=discord.utils.escape_markdown(data.name), inline=False)
    embed.add_field(name="채널", value=f"<#{data.channel_id}>")
    embed.add_field(name="인증 방식", value=VerificationMode(data.verification_mode).value.title())
    embed.add_field(name="요일", value="매일" if len(data.weekdays) == 7 else " / ".join(WEEKDAYS[d] for d in sorted(data.weekdays)))
    embed.add_field(name=f"참여자: {len(data.member_ids)}명", value=" ".join(f"<@{uid}>" for uid in data.member_ids), inline=False)
    embed.add_field(name="하루 체크", value=f"{len(data.schedules)}회")
    embed.add_field(name="시간대", value=data.timezone)
    # Group schedules to stay within Discord's per-field and total embed limits.
    lines = [f"{i}회차: {s.check_time} → Reminder {s.reminder_time}" for i, s in enumerate(data.schedules, 1)]
    for start in range(0, len(lines), 10):
        embed.add_field(name="회차별 시간", value="\n".join(lines[start:start + 10]), inline=False)
    embed.set_footer(text=f"Check ID: {created.id}")
    return embed


class CreateCheckView(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int, repository: CheckRepository) -> None:
        super().__init__(timeout=UI_TIMEOUT)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.repository = repository
        self.message: discord.InteractionMessage | None = None
        self.revision = 0
        self.state = "active"
        self.created: Check | None = None
        self.lock = asyncio.Lock()
        self.name = ""
        self.channel_id: int | None = None
        self.mode: VerificationMode | None = None
        self.weekdays: tuple[int, ...] = ()
        self.member_ids: tuple[int, ...] = ()
        self.session_count = 1
        self.schedules: dict[int, ScheduleInput] = {}
        self.rebuild()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("이 설정은 명령어를 실행한 사용자만 조작할 수 있습니다.", ephemeral=True)
            return False
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("처음 명령어를 실행한 서버에서만 설정할 수 있습니다.", ephemeral=True)
            return False
        if self.state != "active" or self.is_finished():
            await interaction.response.send_message("이미 종료되었거나 만료된 설정입니다. /check create로 다시 시작하세요.", ephemeral=True)
            return False
        return True

    def input(self) -> CheckInput:
        missing = []
        if not self.name:
            missing.append("이름")
        if self.channel_id is None:
            missing.append("채널")
        if self.mode is None:
            missing.append("인증 방식")
        if not self.weekdays:
            missing.append("요일")
        if not self.member_ids:
            missing.append("참여자")
        missing.extend(f"{i + 1}회차 시간" for i in range(self.session_count) if i not in self.schedules)
        if missing:
            raise ValueError("필수 설정을 입력해 주세요: " + ", ".join(missing))
        data = CheckInput(
            guild_id=self.guild_id, channel_id=self.channel_id, name=self.name,
            verification_mode=self.mode, member_ids=self.member_ids,
            weekdays=self.weekdays,
            schedules=tuple(self.schedules[i] for i in range(self.session_count)),
        )
        validate_check_input(data)
        return data

    def embed(self) -> discord.Embed:
        embed = discord.Embed(title="⚙️ DoneYet? Check 만들기", colour=discord.Colour.blurple())
        embed.description = "원하는 순서로 설정을 수정한 뒤 생성 버튼을 누르세요."
        embed.add_field(name="이름", value=discord.utils.escape_markdown(self.name) or "미설정", inline=False)
        embed.add_field(name="채널", value=f"<#{self.channel_id}>" if self.channel_id else "미설정")
        embed.add_field(name="인증 방식", value=self.mode.value.title() if self.mode else "미설정")
        days = "매일" if len(self.weekdays) == 7 else " / ".join(WEEKDAYS[d] for d in self.weekdays)
        embed.add_field(name="요일", value=days or "미설정")
        embed.add_field(name=f"참여자: {len(self.member_ids)}명",
                        value=" ".join(f"<@{uid}>" for uid in self.member_ids) or "미설정", inline=False)
        embed.add_field(name="하루 체크", value=f"{self.session_count}회")
        embed.add_field(name="시간대", value="Asia/Seoul")
        lines = []
        for i in range(self.session_count):
            schedule = self.schedules.get(i)
            lines.append(f"{i + 1}회차: {schedule.check_time} → Reminder {schedule.reminder_time}"
                         if schedule else f"{i + 1}회차: 미입력")
        for start in range(0, len(lines), 10):
            embed.add_field(name="회차별 시간", value="\n".join(lines[start:start + 10]), inline=False)
        embed.set_footer(text="아직 저장되지 않았습니다. 5분 동안 조작하지 않으면 만료됩니다.")
        return embed

    def _bind(self, item: discord.ui.Item, action: str) -> None:
        revision = self.revision

        async def callback(interaction: discord.Interaction) -> None:
            # Snapshot values before another interaction can update the component.
            values = tuple(item.values) if isinstance(item, discord.ui.Select) else ()
            if isinstance(item, (discord.ui.UserSelect, discord.ui.ChannelSelect)):
                values = tuple(item.values)
            await self.handle(interaction, action, revision, values)

        item.callback = callback
        self.add_item(item)

    def rebuild(self) -> None:
        self.revision += 1
        self.clear_items()
        self._bind(discord.ui.ChannelSelect(
            placeholder="채널 선택", channel_types=[discord.ChannelType.text], row=0,
            default_values=[discord.Object(self.channel_id)] if self.channel_id else [],
        ), "channel")
        self._bind(discord.ui.Select(placeholder="인증 방식 선택", row=1, options=[
            discord.SelectOption(label=mode.value.title(), value=mode.value, default=mode == self.mode)
            for mode in VerificationMode
        ]), "mode")
        self._bind(discord.ui.Select(placeholder="요일 선택 (복수 선택)", min_values=1, max_values=7, row=2, options=[
            discord.SelectOption(label=day, value=str(i), default=i in self.weekdays) for i, day in enumerate(WEEKDAYS)
        ]), "weekdays")
        self._bind(discord.ui.UserSelect(
            placeholder="참여자 선택 (복수 선택)", min_values=1, max_values=MAX_PARTICIPANTS, row=3,
            default_values=[discord.Object(uid) for uid in self.member_ids],
        ), "members")
        self._bind(discord.ui.Button(label="기본 설정", row=4), "basics")
        self._bind(discord.ui.Button(label="회차 설정", row=4), "session")
        self._bind(discord.ui.Button(label="생성", emoji="✅", style=discord.ButtonStyle.success, row=4), "confirm")
        self._bind(discord.ui.Button(label="취소", emoji="❌", style=discord.ButtonStyle.danger, row=4), "cancel")

    async def refresh(self, interaction: discord.Interaction) -> None:
        self.rebuild()
        await interaction.response.edit_message(embed=self.embed(), view=self)
        self.message = await interaction.original_response()

    async def handle(self, interaction: discord.Interaction, action: str, revision: int, values: tuple = ()) -> None:
        if self.lock.locked():
            await interaction.response.send_message("이전 요청을 처리 중입니다. 잠시 후 다시 시도해 주세요.", ephemeral=True)
            return
        async with self.lock:
            if not await self.interaction_check(interaction):
                return
            if revision != self.revision:
                await interaction.response.send_message("설정 화면이 변경되었습니다. 현재 화면에서 다시 입력해 주세요.", ephemeral=True)
                return
            try:
                await self._handle(interaction, action, values)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)

    async def _handle(self, interaction: discord.Interaction, action: str, values: tuple) -> None:
        if action == "cancel":
            self.state = "cancelled"
            self.stop()
            await interaction.response.edit_message(content="Check 생성을 취소했습니다. 저장된 데이터는 없습니다.", embed=None, view=None)
            return
        if action == "basics":
            await interaction.response.send_modal(BasicsModal(self))
            return
        if action == "session":
            await interaction.response.send_modal(SessionModal(self))
            return
        if action == "confirm":
            await self.confirm(interaction)
            return
        if action == "channel":
            channel = values[0]
            channel_guild_id = channel.guild_id if isinstance(channel, discord.app_commands.AppCommandChannel) else channel.guild.id
            if channel.type != discord.ChannelType.text or channel_guild_id != self.guild_id:
                raise ValueError("이 서버의 텍스트 채널을 선택해 주세요.")
            self.channel_id = channel.id
        elif action == "mode":
            self.mode = VerificationMode(values[0])
        elif action == "weekdays":
            self.weekdays = tuple(sorted(int(v) for v in values))
        elif action == "members":
            self.member_ids = tuple(sorted(user.id for user in values))
        elif action == "basics_submit":
            name, count = values
            if not name.strip():
                raise ValueError("Check 이름을 입력해 주세요.")
            if not count.isascii() or not count.isdecimal() or not 1 <= int(count) <= MAX_SESSIONS:
                raise ValueError(f"하루 횟수는 1~{MAX_SESSIONS} 사이의 정수로 입력하세요.")
            self.name = name.strip()
            self.session_count = int(count)
            self.schedules = {i: s for i, s in self.schedules.items() if i < self.session_count}
        elif action == "session_submit":
            index, check_time, reminder_time = values
            if not 0 <= index < self.session_count:
                raise ValueError(f"회차는 1~{self.session_count} 사이로 입력하세요.")
            schedule = ScheduleInput(check_time.strip(), reminder_time.strip())
            validate_schedule_input(schedule)
            self.schedules[index] = schedule
        await self.refresh(interaction)

    async def confirm(self, interaction: discord.Interaction) -> None:
        data = self.input()
        await interaction.response.defer()
        try:
            created = await asyncio.to_thread(self.repository.create_check, data)
        except (sqlite3.Error, OSError):
            logger.exception("Check creation failed")
            await interaction.followup.send("저장하지 못했습니다. 입력 내용은 유지됩니다. 잠시 후 생성 버튼으로 다시 시도해 주세요.", ephemeral=True)
            return
        except ValueError as exc:
            await interaction.followup.send(f"설정을 확인해 주세요: {exc}", ephemeral=True)
            return
        # Mark completion before Discord HTTP calls, so an edit failure cannot
        # turn a successful database commit into a duplicate on retry.
        self.created = created
        self.state = "saved"
        self.stop()
        await interaction.edit_original_response(content=None, embed=settings_embed(data, created=created), view=None)

    async def on_timeout(self) -> None:
        async with self.lock:
            if self.state != "active":
                return
            self.state = "expired"
            self.stop()
            if self.message:
                try:
                    await self.message.edit(content="설정 시간이 만료되었습니다. 저장하지 않았습니다. /check create로 다시 시작하세요.", embed=None, view=None)
                except discord.HTTPException:
                    logger.warning("Could not update an expired Check creation message", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logger.error("Check creation UI failed", exc_info=(type(error), error, error.__traceback__))
        if self.created:
            message = f"Check는 저장되었습니다 (ID: {self.created.id}). 결과 화면을 표시하지 못했습니다. 다시 생성하지 않아도 됩니다."
        else:
            message = "설정 처리 중 오류가 발생했습니다. 현재 화면에서 다시 시도해 주세요."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class PanelModal(discord.ui.Modal):
    def __init__(self, panel: CreateCheckView, title: str) -> None:
        super().__init__(title=title, timeout=UI_TIMEOUT)
        self.panel = panel
        self.revision = panel.revision

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.panel.interaction_check(interaction)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await self.panel.on_error(interaction, error, self)


class BasicsModal(PanelModal):
    def __init__(self, panel: CreateCheckView) -> None:
        super().__init__(panel, "Check 이름과 하루 횟수")
        self.check_name = discord.ui.TextInput(label="Check 이름", max_length=100, default=panel.name or None)
        self.count = discord.ui.TextInput(label=f"하루 체크 횟수 (1~{MAX_SESSIONS})", max_length=2, default=str(panel.session_count))
        self.add_item(self.check_name)
        self.add_item(self.count)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.panel.handle(interaction, "basics_submit", self.revision, (self.check_name.value, self.count.value.strip()))


class SessionModal(PanelModal):
    def __init__(self, panel: CreateCheckView, index: int = 0) -> None:
        super().__init__(panel, "회차별 시간 · Asia/Seoul")
        self.session_number = discord.ui.TextInput(label=f"회차 번호 (1~{panel.session_count})", default=str(index + 1), max_length=2)
        self.add_item(self.session_number)
        schedule = panel.schedules.get(index)
        self.check_time = discord.ui.TextInput(label="체크 시각 (HH:MM)", placeholder="09:00", max_length=5,
                                              default=schedule.check_time if schedule else None)
        self.reminder_time = discord.ui.TextInput(label="리마인더 시각 (HH:MM)", placeholder="22:00", max_length=5,
                                                 default=schedule.reminder_time if schedule else None)
        self.add_item(self.check_time)
        self.add_item(self.reminder_time)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        number = self.session_number.value.strip()
        if not number.isascii() or not number.isdecimal():
            await interaction.response.send_message("회차 번호는 정수로 입력하세요.", ephemeral=True)
            return
        await self.panel.handle(interaction, "session_submit", self.revision,
                                (int(number) - 1, self.check_time.value, self.reminder_time.value))
