import asyncio
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from doneyet.bot import DoneYetBot, test_command
from doneyet.check_commands import CheckCommands
from doneyet.check_ui import BasicsModal, CreateCheckView, MAX_SESSIONS, SessionModal, settings_embed
from doneyet.database import connect_database, initialize_database
from doneyet.models import ScheduleInput, VerificationMode
from doneyet.repository import CheckRepository


def interaction(user_id=300, guild_id=100):
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id), guild_id=guild_id,
        response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock(),
                                 send_modal=AsyncMock(), defer=AsyncMock(), is_done=Mock(return_value=False)),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(), original_response=AsyncMock(),
    )


class CheckUITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'test.db'
        initialize_database(self.path)
        self.repository = CheckRepository(self.path)

    async def asyncSetUp(self):
        self.view = CreateCheckView(300, 100, self.repository)
        self.addCleanup(self.view.stop)

    async def act(self, action, values=(), *, user_id=300, revision=None):
        event = interaction(user_id=user_id)
        await self.view.handle(event, action, self.view.revision if revision is None else revision, values)
        return event

    async def complete_draft(self):
        await self.act('basics_submit', ('공부', '2'))
        channel = SimpleNamespace(id=200, type=discord.ChannelType.text, guild=SimpleNamespace(id=100))
        await self.act('channel', (channel,))
        await self.act('mode', ('either',))
        await self.act('weekdays', ('0', '1', '2', '3', '4'))
        await self.act('members', (SimpleNamespace(id=300), SimpleNamespace(id=301)))
        await self.act('session_submit', (0, '09:00', '12:00'))
        await self.act('session_submit', (1, '21:00', '23:30'))

    async def test_full_flow_only_persists_on_confirm(self):
        await self.complete_draft()
        self.assertEqual(self.repository.list_checks(100), [])
        event = await self.act('confirm')
        saved = self.repository.list_checks(100)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].name, '공부')
        self.assertEqual(saved[0].daily_sessions, 2)
        self.assertEqual(saved[0].weekdays, (0, 1, 2, 3, 4))
        self.assertEqual([m.user_id for m in saved[0].members], [300, 301])
        self.assertEqual(saved[0].schedules[1].reminder_time, '23:30')
        event.response.defer.assert_awaited_once()
        result = event.edit_original_response.call_args.kwargs
        self.assertEqual(result['embed'].title, 'DoneYet? Check Created')
        self.assertIsNone(result['view'])
        self.assertEqual(self.view.state, 'saved')

    async def test_cancel_never_persists(self):
        await self.complete_draft()
        event = await self.act('cancel')
        self.assertEqual(self.view.state, 'cancelled')
        self.assertIsNone(event.response.edit_message.call_args.kwargs['view'])
        await self.act('confirm')
        self.assertEqual(self.repository.list_checks(100), [])

    async def test_timeout_never_persists_and_rejects_open_modal(self):
        modal = BasicsModal(self.view)
        self.view.message = SimpleNamespace(edit=AsyncMock())
        await self.view.on_timeout()
        self.assertEqual(self.view.state, 'expired')
        self.view.message.edit.assert_awaited_once()
        event = interaction()
        self.assertFalse(await modal.interaction_check(event))
        self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
        await self.act('confirm')
        self.assertEqual(self.repository.list_checks(100), [])

    async def test_non_owner_cannot_change_or_submit(self):
        revision = self.view.revision
        for action, values in [('basics_submit', ('Other', '1')), ('cancel', ())]:
            event = await self.act(action, values, user_id=999)
            self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
        modal = BasicsModal(self.view)
        self.assertFalse(await modal.interaction_check(interaction(user_id=999)))
        self.assertEqual(self.view.revision, revision)
        self.assertEqual(self.view.state, 'active')

    async def test_wrong_guild_is_rejected(self):
        event = interaction(guild_id=101)
        self.assertFalse(await self.view.interaction_check(event))
        self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])

    async def test_missing_fields_do_not_advance_or_save(self):
        for action in ('confirm',):
            event = await self.act(action)
            self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
        self.assertEqual(self.repository.list_checks(100), [])

    async def test_invalid_modal_input_can_be_corrected(self):
        for values in [(' ', '1'), ('공부', '0'), ('공부', '26'), ('공부', '1.5')]:
            event = await self.act('basics_submit', values)
            self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
            self.assertEqual(self.view.name, '')
        event = await self.act('session_submit', (0, '24:00', '23:00'))
        self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
        self.assertEqual(self.view.schedules, {})
        await self.complete_draft()
        await self.act('confirm')
        self.assertEqual(len(self.repository.list_checks(100)), 1)

    async def test_stale_modal_does_not_overwrite_new_settings(self):
        modal = BasicsModal(self.view)
        modal.check_name._value = 'Old'
        modal.count._value = '1'
        await self.act('basics_submit', ('New', '2'))
        event = interaction()
        await modal.on_submit(event)
        self.assertEqual(self.view.name, 'New')
        self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])

    async def test_components_open_modals_and_submit(self):
        button = next(c for c in self.view.children if isinstance(c, discord.ui.Button) and c.label == '기본 설정')
        event = interaction()
        await button.callback(event)
        modal = event.response.send_modal.call_args.args[0]
        self.assertIsInstance(modal, BasicsModal)
        modal.check_name._value = '영양제'
        modal.count._value = '1'
        await modal.on_submit(interaction())
        self.assertEqual(self.view.name, '영양제')
        session = SessionModal(self.view, 0)
        session.check_time._value = '09:00'
        session.reminder_time._value = '22:00'
        await session.on_submit(interaction())
        self.assertEqual(self.view.schedules[0], ScheduleInput('09:00', '22:00'))

    async def test_count_change_preserves_values_and_requires_new_times(self):
        await self.complete_draft()
        await self.act('basics_submit', ('Study', '3'))
        event = await self.act('confirm')
        self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
        self.assertEqual(len(self.view.schedules), 2)
        self.assertEqual(self.repository.list_checks(100), [])
        await self.act('session_submit', (2, '23:40', '23:50'))
        self.assertEqual(len(self.view.input().schedules), 3)
        await self.act('basics_submit', ('Study', '1'))
        self.assertEqual(set(self.view.schedules), {0})

    async def test_channel_select_without_guild_cache(self):
        channel = discord.app_commands.AppCommandChannel(
            state=Mock(), guild_id=100,
            data={'id': '200', 'type': 0, 'name': 'study', 'permissions': '0'},
        )
        select = next(c for c in self.view.children if isinstance(c, discord.ui.ChannelSelect))
        select._values = [channel]
        await select.callback(interaction())
        self.assertEqual(self.view.channel_id, 200)
        channel.guild_id = 101
        event = await self.act('channel', (channel,))
        self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])

    async def test_failed_save_rolls_back_and_can_retry(self):
        await self.complete_draft()
        with connect_database(self.path) as db:
            db.execute("""CREATE TRIGGER fail_schedule BEFORE INSERT ON check_schedules
                          WHEN NEW.sequence = 2 BEGIN
                          SELECT RAISE(ABORT, 'Simulated failure'); END""")
        with self.assertLogs('doneyet.check_ui', level='ERROR'):
            event = await self.act('confirm')
        self.assertTrue(event.followup.send.call_args.kwargs['ephemeral'])
        self.assertEqual(self.view.state, 'active')
        with connect_database(self.path) as db:
            for table in ('checks', 'check_days', 'check_members', 'check_schedules'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)
            db.execute('DROP TRIGGER fail_schedule')
        await self.act('confirm')
        self.assertEqual(len(self.repository.list_checks(100)), 1)

    async def test_double_confirm_and_timeout_during_save_do_not_duplicate(self):
        await self.complete_draft()
        started, release = threading.Event(), threading.Event()
        original = self.repository.create_check

        def delayed(data):
            started.set()
            if not release.wait(5):
                raise RuntimeError('Test timed out')
            return original(data)

        self.repository.create_check = Mock(side_effect=delayed)
        first = asyncio.create_task(self.act('confirm'))
        self.assertTrue(await asyncio.to_thread(started.wait, 3))
        try:
            second = await self.act('confirm')
            self.assertTrue(second.response.send_message.call_args.kwargs['ephemeral'])
            timeout = asyncio.create_task(self.view.on_timeout())
        finally:
            release.set()
        await first
        await timeout
        await self.act('confirm')
        self.repository.create_check.assert_called_once()
        self.assertEqual(self.view.state, 'saved')
        self.assertEqual(len(self.repository.list_checks(100)), 1)

    async def test_discord_error_after_commit_does_not_allow_resave(self):
        await self.complete_draft()
        event = interaction()
        event.response.is_done.return_value = True
        error = discord.HTTPException(SimpleNamespace(status=500, reason='Test'), 'Test error')
        event.edit_original_response.side_effect = error
        with self.assertRaises(discord.HTTPException):
            await self.view.handle(event, 'confirm', self.view.revision)
        with self.assertLogs('doneyet.check_ui', level='ERROR'):
            await self.view.on_error(event, error, None)
        self.assertIn('저장되었습니다', event.followup.send.call_args.args[0])
        await self.act('confirm')
        self.assertEqual(len(self.repository.list_checks(100)), 1)

    async def test_maximum_draft_fits_discord_component_and_embed_limits(self):
        await self.complete_draft()
        self.view.session_count = MAX_SESSIONS
        self.view.schedules = {i: ScheduleInput('09:00', '22:00') for i in range(MAX_SESSIONS)}
        self.view.member_ids = tuple(range(100000000000000000, 100000000000000025))
        self.view.name = '*' * 100
        self.view.rebuild()
        self.assertLessEqual(len(self.view.to_components()), 5)
        embed = self.view.embed()
        self.assertLessEqual(len(embed), 6000)
        self.assertLessEqual(len(embed.fields), 25)
        self.assertTrue(all(len(field.value) <= 1024 for field in embed.fields))
        self.assertEqual(len(self.view.input().schedules), 25)

    async def test_command_registration_and_private_entry(self):
        bot = DoneYetBot()
        self.addAsyncCleanup(bot.close)
        group = bot.tree.get_command('check')
        self.assertTrue(group.guild_only)
        self.assertIsNone(group.default_permissions)
        self.assertIsNotNone(group.get_command('create'))
        event = interaction()
        commands = CheckCommands(self.repository)
        await commands.create.callback(commands, event)
        kwargs = event.response.send_message.call_args.kwargs
        self.assertTrue(kwargs['ephemeral'])
        self.assertIsInstance(kwargs['view'], CreateCheckView)
        self.assertEqual(kwargs['embed'].title, '⚙️ DoneYet? Check 만들기')
        kwargs['view'].stop()
        dm = interaction(guild_id=None)
        await commands.create.callback(commands, dm)
        self.assertIn('서버', dm.response.send_message.call_args.args[0])
        test = interaction()
        await test_command.callback(test)
        test.response.send_message.assert_awaited_once_with('DoneYet? is running! ✅')

    async def test_panel_has_all_settings_and_no_navigation(self):
        labels = [c.label for c in self.view.children if isinstance(c, discord.ui.Button)]
        self.assertEqual(labels, ['기본 설정', '회차 설정', '생성', '취소'])
        self.assertFalse(hasattr(self.view, 'step'))
        fields = {field.name for field in self.view.embed().fields}
        self.assertTrue({'이름', '채널', '인증 방식', '요일', '참여자: 0명', '하루 체크', '시간대', '회차별 시간'} <= fields)
        event = await self.act('confirm')
        error = event.response.send_message.call_args.args[0]
        for field in ('이름', '채널', '인증 방식', '요일', '참여자', '1회차 시간'):
            self.assertIn(field, error)

    async def test_settings_can_be_changed_in_any_order_on_same_panel(self):
        for action, values in [
            ('session_submit', (0, '09:00', '22:00')),
            ('members', (SimpleNamespace(id=300),)),
            ('weekdays', ('0', '6')),
            ('mode', ('photo',)),
            ('basics_submit', ('Study', '1')),
        ]:
            event = await self.act(action, values)
            event.response.edit_message.assert_awaited_once()
            event.response.send_message.assert_not_awaited()
            self.assertIs(event.response.edit_message.call_args.kwargs['view'], self.view)
            self.assertEqual(event.response.edit_message.call_args.kwargs['embed'].title, '⚙️ DoneYet? Check 만들기')
        self.assertEqual(self.repository.list_checks(100), [])

    async def test_time_rules_reject_invalid_changes_and_allow_correction(self):
        for check_time, reminder_time, valid in [
            ('09:00', '22:00', True), ('14:00', '13:00', False),
            ('14:00', '14:00', False), ('22:00', '23:30', True),
            ('23:00', '00:30', False),
        ]:
            before = dict(self.view.schedules)
            event = await self.act('session_submit', (0, check_time, reminder_time))
            if valid:
                self.assertEqual(self.view.schedules[0], ScheduleInput(check_time, reminder_time))
                event.response.edit_message.assert_awaited_once()
            else:
                self.assertEqual(self.view.schedules, before)
                self.assertIn('Reminder Time은 Check Time보다 이후', event.response.send_message.call_args.args[0])
                self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
                event.response.edit_message.assert_not_awaited()

    async def test_session_modal_can_edit_each_session(self):
        await self.act('basics_submit', ('Study', '2'))
        event = await self.act('session')
        modal = event.response.send_modal.call_args.args[0]
        modal.session_number._value = '2'
        modal.check_time._value = '14:00'
        modal.reminder_time._value = '13:00'
        await modal.on_submit(interaction())
        self.assertEqual(self.view.schedules, {})
        modal.reminder_time._value = '15:00'
        await modal.on_submit(interaction())
        self.assertEqual(self.view.schedules, {1: ScheduleInput('14:00', '15:00')})

    async def test_create_uses_repository_after_all_settings_are_present(self):
        self.repository.create_check = Mock(wraps=self.repository.create_check)
        await self.complete_draft()
        self.repository.create_check.assert_not_called()
        expected = self.view.input()
        await self.act('confirm')
        self.repository.create_check.assert_called_once_with(expected)


if __name__ == '__main__':
    unittest.main()
