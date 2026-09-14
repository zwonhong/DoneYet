import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from doneyet.database import initialize_database
from doneyet.member_commands import MemberCommands, MemberListView, MemberView
from doneyet.models import CheckInput, ScheduleInput, VerificationMode
from doneyet.repository import CheckRepository


def event(user=300, guild=100):
    return SimpleNamespace(user=SimpleNamespace(id=user), guild_id=guild, data={'values': ['1']},
                           response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()))


class MemberCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / 'db'; initialize_database(path); self.repo = CheckRepository(path)
        self.check = self.repo.create_check(CheckInput(100, 200, 'Test', VerificationMode.BUTTON, (300,), (0,), (ScheduleInput('09:00', '22:00'),)))

    def view(self, action='add'):
        view = MemberView(300, 100, self.repo, [self.check], action); self.addCleanup(view.stop); return view

    async def test_commands_and_owner_guard(self):
        commands = MemberCommands(self.repo)
        e = event(); await commands.add.callback(commands, e)
        self.assertTrue(e.response.send_message.call_args.kwargs['ephemeral'])
        self.assertIsInstance(e.response.send_message.call_args.kwargs['view'], MemberView)
        denied = event(999); self.assertFalse(await self.view().interaction_check(denied))
        self.assertTrue(denied.response.send_message.call_args.kwargs['ephemeral'])

    async def test_selected_check_name_is_kept_in_panel(self):
        view = self.view(); await view._check(event())
        self.assertEqual(view.children[0].placeholder, '선택됨: Test')
        self.assertTrue(view.children[0].options[0].default)

    async def test_user_options_are_filtered_by_channel_and_active_members(self):
        allowed = SimpleNamespace(id=400, display_name='Allowed')
        denied = SimpleNamespace(id=401, display_name='Denied')
        channel = SimpleNamespace(permissions_for=lambda member: SimpleNamespace(view_channel=member.id == 400))
        current = SimpleNamespace(id=300, display_name='Current')
        guild = SimpleNamespace(members=[allowed, denied, current], get_channel=lambda _id: channel)
        e = event(); e.guild = guild
        view = self.view('add'); await view._check(e)
        self.assertEqual([option.label for option in view.children[1].options], ['Allowed'])
        remove = self.view('remove'); e = event(); e.guild = guild
        await remove._check(e)
        self.assertEqual([option.label for option in remove.children[1].options], ['Current'])

    async def test_add_duplicate_remove_and_history(self):
        view = self.view(); view.check_id = self.check.id; view.user_id = 300
        e = event(); await view._submit(e); self.assertIn('이미 참여자', e.response.edit_message.call_args.kwargs['content'])
        view = self.view('remove'); view.check_id = self.check.id; view.user_id = 999
        e = event(); await view._submit(e); self.assertIn('현재 참여자가 아닙니다', e.response.edit_message.call_args.kwargs['content'])
        self.assertEqual(self.repo.remove_member(100, self.check.id, 300), 'removed')
        self.assertFalse(self.repo.is_check_member(self.check.id, 300))

    async def test_cancel_and_nested_registration(self):
        view = self.view(); await view._cancel(event()); self.assertTrue(view.closed)
        from doneyet.bot import DoneYetBot
        bot = DoneYetBot(); self.addAsyncCleanup(bot.close)
        member = bot.tree.get_command('check').get_command('member')
        self.assertIsNotNone(member.get_command('add')); self.assertIsNotNone(member.get_command('remove'))

    async def test_member_list_shows_active_members_after_check_selection(self):
        commands = MemberCommands(self.repo)
        e = event(); await commands.list.callback(commands, e)
        view = e.response.send_message.call_args.kwargs['view']
        self.assertIsInstance(view, MemberListView)
        e = event(); await view._select(e)
        self.assertIn('<@300>', e.response.edit_message.call_args.kwargs['embed'].description)


if __name__ == '__main__': unittest.main()
