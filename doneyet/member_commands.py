import asyncio
import logging

import discord
from discord import app_commands

from doneyet.repository import CheckRepository

logger = logging.getLogger(__name__)


class MemberView(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int, repository: CheckRepository, checks, action: str):
        super().__init__(timeout=300)
        self.owner_id, self.guild_id, self.repository = owner_id, guild_id, repository
        self.checks, self.action = checks, action
        self.selected_check = None
        self.available_users = []
        self.check_id = None
        self.user_id = None
        self.selected_user_name = None
        self.closed = False
        self._build()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id or interaction.guild_id != self.guild_id:
            await interaction.response.send_message("명령어를 실행한 사용자만 같은 서버에서 조작할 수 있습니다.", ephemeral=True)
            return False
        return not self.closed

    def _build(self):
        self.clear_items()
        selected = next((c for c in self.checks if c.id == self.check_id), None)
        check_select = discord.ui.Select(
            placeholder=f"선택됨: {selected.name[:90]}" if selected else "Check 선택",
            options=[discord.SelectOption(label=c.name[:100], value=str(c.id), default=c.id == self.check_id) for c in self.checks],
        )
        self.add_item(check_select)
        self.children[0].callback = self._check
        if self.selected_check is None:
            user_select = discord.ui.UserSelect(
                placeholder="사용자 선택 (Check를 먼저 선택하세요)", min_values=1, max_values=1, disabled=True)
        else:
            user_select = discord.ui.Select(
                placeholder=(f"선택됨: {self.selected_user_name[:80]}" if self.selected_user_name else
                             ("현재 참여자 선택" if self.action == 'remove' else "채널 접근 가능한 멤버 선택")),
                min_values=1, max_values=1,
                options=[discord.SelectOption(label=getattr(u, 'display_name', str(u))[:100], value=str(u.id), default=u.id == self.user_id)
                         for u in self.available_users[:25]],
                disabled=not self.available_users)
        self.add_item(user_select)
        self.children[1].callback = self._user
        button = discord.ui.Button(label="추가" if self.action == 'add' else "제거", style=discord.ButtonStyle.success)
        button.callback = self._submit
        self.add_item(button)
        cancel = discord.ui.Button(label="취소", style=discord.ButtonStyle.danger)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _check(self, interaction):
        if not await self.interaction_check(interaction): return
        self.check_id = int(interaction.data['values'][0])
        self.selected_check = await asyncio.to_thread(self.repository.get_check, self.guild_id, self.check_id)
        if self.selected_check is None:
            await interaction.response.send_message("이 서버의 Check가 아닙니다.", ephemeral=True); return
        members = await asyncio.to_thread(self.repository.list_members, self.guild_id, self.check_id)
        active_ids = {member.user_id for member in (members or [])}
        guild = getattr(interaction, 'guild', None)
        channel = guild.get_channel(self.selected_check.channel_id) if guild else None
        guild_members = list(guild.members) if guild else []
        if self.action == 'remove':
            self.available_users = [member for member in guild_members if member.id in active_ids]
        else:
            self.available_users = [member for member in guild_members
                                    if member.id not in active_ids and channel is not None
                                    and channel.permissions_for(member).view_channel]
        self._build()
        await interaction.response.edit_message(view=self)

    async def _user(self, interaction):
        if not await self.interaction_check(interaction): return
        values = interaction.data.get('resolved', {}).get('users', {})
        self.user_id = int(next(iter(values))) if values else int(interaction.data['values'][0])
        selected = next((u for u in self.available_users if u.id == self.user_id), None)
        self.selected_user_name = getattr(selected, 'display_name', None) or getattr(selected, 'name', None) or str(self.user_id)
        member = interaction.guild.get_member(self.user_id) if getattr(interaction, 'guild', None) else None
        if member is None and getattr(interaction, 'guild', None):
            try:
                member = await interaction.guild.fetch_member(self.user_id)
            except discord.HTTPException:
                member = None
        if member is None and getattr(interaction, 'guild', None):
            await interaction.response.send_message("이 서버의 멤버를 선택해 주세요.", ephemeral=True); return
        if self.action == 'add' and member is not None:
            channel = interaction.guild.get_channel(self.selected_check.channel_id)
            if channel is None or not channel.permissions_for(member).view_channel:
                await interaction.response.send_message("이 Check 채널에 접근 권한이 없는 멤버입니다.", ephemeral=True); return
        elif self.action == 'remove' and self.user_id not in {m.user_id for m in (await asyncio.to_thread(self.repository.list_members, self.guild_id, self.check_id) or [])}:
            await interaction.response.send_message("현재 참여자가 아닙니다.", ephemeral=True); return
        self._build()
        await interaction.response.edit_message(view=self)

    async def _submit(self, interaction):
        if not await self.interaction_check(interaction): return
        if self.check_id is None or self.user_id is None:
            await interaction.response.send_message("Check와 사용자를 먼저 선택하세요.", ephemeral=True); return
        if self.action == 'add':
            result = await asyncio.to_thread(self.repository.add_member, self.guild_id, self.check_id, self.user_id)
            messages = {'added': '참여자를 추가했습니다.', 'already_member': '이미 참여자입니다.', 'reactivated': '참여자를 다시 활성화했습니다.', 'missing_check': '이 서버의 Check가 아닙니다.'}
        else:
            result = await asyncio.to_thread(self.repository.remove_member, self.guild_id, self.check_id, self.user_id)
            messages = {'removed': '참여자를 제거했습니다. 참여 이력은 보존됩니다.', 'not_member': '현재 참여자가 아닙니다.', 'missing_check': '이 서버의 Check가 아닙니다.'}
        self.closed = True; self.stop()
        logger.info("Member %s: guild=%s check=%s user=%s actor=%s result=%s", self.action, self.guild_id, self.check_id, self.user_id, self.owner_id, result)
        await interaction.response.edit_message(content=messages[result], view=None)

    async def _cancel(self, interaction):
        if not await self.interaction_check(interaction): return
        self.closed = True; self.stop()
        await interaction.response.edit_message(content="취소했습니다.", view=None)

    async def on_timeout(self):
        self.closed = True; self.stop()


class MemberListView(discord.ui.View):
    def __init__(self, owner_id, guild_id, repository, checks):
        super().__init__(timeout=300)
        self.owner_id, self.guild_id, self.repository = owner_id, guild_id, repository
        self.checks, self.closed = checks, False
        select = discord.ui.Select(placeholder="Check 선택", options=[
            discord.SelectOption(label=c.name[:100], value=str(c.id)) for c in checks])
        select.callback = self._select
        self.add_item(select)
        close = discord.ui.Button(label="닫기", style=discord.ButtonStyle.danger)
        close.callback = self._close
        self.add_item(close)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id or interaction.guild_id != self.guild_id:
            await interaction.response.send_message("명령어를 실행한 사용자만 같은 서버에서 조작할 수 있습니다.", ephemeral=True)
            return False
        return not self.closed

    async def _select(self, interaction):
        if not await self.interaction_check(interaction): return
        check_id = int(interaction.data['values'][0])
        check = next((c for c in self.checks if c.id == check_id), None)
        members = await asyncio.to_thread(self.repository.list_members, self.guild_id, check_id)
        if check is None or members is None:
            await interaction.response.send_message("이 서버의 Check가 아닙니다.", ephemeral=True); return
        embed = discord.Embed(title=f"{check.name} 참여자", colour=discord.Colour.blurple())
        embed.description = "\n".join(f"<@{m.user_id}> · 가입 {m.joined_at.date().isoformat()}" for m in members) or "현재 참여자가 없습니다."
        embed.set_footer(text=f"Check ID: {check.id} · 활성 참여자 {len(members)}명")
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    async def _close(self, interaction):
        if not await self.interaction_check(interaction): return
        self.closed = True; self.stop()
        await interaction.response.edit_message(content="종료했습니다.", embed=None, view=None)

    async def on_timeout(self):
        self.closed = True; self.stop()


class MemberCommands(app_commands.Group):
    def __init__(self, repository):
        super().__init__(name='member', description='Check 참여자 관리')
        self.repository = repository

    async def open(self, interaction, action):
        if interaction.guild_id is None:
            await interaction.response.send_message('서버에서 실행해 주세요.', ephemeral=True); return
        checks = await asyncio.to_thread(self.repository.list_checks, interaction.guild_id)
        if not checks:
            await interaction.response.send_message('이 서버에 Check가 없습니다.', ephemeral=True); return
        view = MemberView(interaction.user.id, interaction.guild_id, self.repository, checks, action)
        await interaction.response.send_message('Check와 사용자를 선택하세요.', view=view, ephemeral=True)

    async def open_list(self, interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message('서버에서 실행해 주세요.', ephemeral=True); return
        checks = await asyncio.to_thread(self.repository.list_checks, interaction.guild_id)
        if not checks:
            await interaction.response.send_message('이 서버에 Check가 없습니다.', ephemeral=True); return
        view = MemberListView(interaction.user.id, interaction.guild_id, self.repository, checks)
        await interaction.response.send_message('참여자를 확인할 Check를 선택하세요.', view=view, ephemeral=True)

    @app_commands.command(name='add', description='Check 참여자를 추가합니다.')
    async def add(self, interaction): await self.open(interaction, 'add')

    @app_commands.command(name='remove', description='Check 참여자를 제거합니다.')
    async def remove(self, interaction): await self.open(interaction, 'remove')

    @app_commands.command(name='list', description='Check의 현재 참여자 목록을 봅니다.')
    async def list(self, interaction): await self.open_list(interaction)
