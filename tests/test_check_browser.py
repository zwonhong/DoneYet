import asyncio
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from doneyet.check_browser import CheckBrowser, detail_pages
from doneyet.check_commands import CheckCommands
from doneyet.database import connect_database, initialize_database
from doneyet.models import CheckInput, CheckMember, CheckSchedule, ScheduleInput, VerificationMode
from doneyet.repository import CheckRepository


def interaction(owner=300, guild=100):
    return SimpleNamespace(user=SimpleNamespace(id=owner), guild_id=guild,
        response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock(), is_done=Mock(return_value=True)),
        followup=SimpleNamespace(send=AsyncMock()), edit_original_response=AsyncMock(), original_response=AsyncMock())


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'test.db'
        initialize_database(self.path)
        self.repo = CheckRepository(self.path)
        self.data = CheckInput(100, 200, '공부', VerificationMode.EITHER, (300,), (0, 1), (ScheduleInput('09:00', '22:00'),))
        self.check = self.repo.create_check(self.data)
        self.other = self.repo.create_check(replace(self.data, guild_id=101, name='Other'))

    def browser(self, mode='delete'):
        view = CheckBrowser(300, 100, self.repo, self.repo.list_checks(100), mode)
        self.addCleanup(view.stop)
        return view

    async def act(self, view, action, value=None, owner=300, guild=100):
        event = interaction(owner, guild)
        await view.handle(event, action, view.revision, value)
        return event

    async def test_commands_open_current_guild_only_and_empty_state(self):
        commands = CheckCommands(self.repo)
        for name in ('list', 'info', 'delete'):
            event = interaction()
            command = commands.get_command(name)
            self.assertIsNotNone(command)
            await command.callback(commands, event)
            event.response.defer.assert_awaited_once_with(ephemeral=True)
            view = event.edit_original_response.call_args.kwargs['view']
            self.assertEqual([c.id for c in view.checks], [self.check.id])
            view.stop()
        event = interaction(guild=999)
        await commands.open_browser(event, 'info')
        self.assertIn('없습니다', event.edit_original_response.call_args.kwargs['content'])

    async def test_list_paginates_with_required_fields(self):
        for i in range(11):
            self.repo.create_check(replace(self.data, name=f'Check {i}'))
        view = self.browser('list')
        self.assertEqual(len(view.embed().fields), 5)
        text = view.embed().fields[0].value
        for word in ('채널', '인증', '요일', '하루', '참여자', 'Enabled'):
            self.assertIn(word, text)
        await self.act(view, 'next')
        self.assertEqual(view.page, 1)
        await self.act(view, 'next')
        self.assertEqual(len(view.embed().fields), 2)

    async def test_info_displays_members_and_session(self):
        view = self.browser('info')
        await self.act(view, 'select', str(self.check.id))
        text = view.embed().description
        for value in ('공부', '<#200>', '<@300>', '1회차', '09:00', '22:00', 'Enabled', 'Either'):
            self.assertIn(value, text)
        self.assertNotIn('Confirm', [getattr(c, 'label', '') for c in view.children])

    async def test_forged_foreign_id_cannot_be_read_or_deleted(self):
        view = self.browser()
        event = await self.act(view, 'select', str(self.other.id))
        self.assertIsNone(view.selected)
        self.assertTrue(event.followup.send.call_args.kwargs['ephemeral'])
        await self.act(view, 'confirm')
        self.assertIsNotNone(self.repo.get_check(101, self.other.id))

    async def test_owner_and_guild_guards(self):
        view = self.browser()
        for owner, guild in ((301, 100), (300, 101)):
            event = await self.act(view, 'select', str(self.check.id), owner, guild)
            self.assertTrue(event.response.send_message.call_args.kwargs['ephemeral'])
            self.assertIsNone(view.selected)

    async def test_confirm_required_and_cancel_preserves_data(self):
        view = self.browser()
        await self.act(view, 'confirm')
        await self.act(view, 'select', str(self.check.id))
        self.assertIsNotNone(self.repo.get_check(100, self.check.id))
        self.assertIn('삭제', view.embed().title)
        await self.act(view, 'cancel')
        await self.act(view, 'confirm')
        self.assertIsNotNone(self.repo.get_check(100, self.check.id))

    async def test_delete_once_and_other_check_survives(self):
        view = self.browser()
        await self.act(view, 'select', str(self.check.id))
        self.repo.delete_check = Mock(wraps=self.repo.delete_check)
        await asyncio.gather(self.act(view, 'confirm'), self.act(view, 'confirm'))
        self.repo.delete_check.assert_called_once_with(100, self.check.id, expected=self.check)
        self.assertIsNone(self.repo.get_check(100, self.check.id))
        self.assertIsNotNone(self.repo.get_check(101, self.other.id))

    async def test_timeout_does_not_delete(self):
        view = self.browser()
        await self.act(view, 'select', str(self.check.id))
        view.message = SimpleNamespace(edit=AsyncMock())
        await view.on_timeout()
        await self.act(view, 'confirm')
        self.assertIsNotNone(self.repo.get_check(100, self.check.id))
        view.message.edit.assert_awaited_once()

    async def test_already_deleted_target_is_handled(self):
        view = self.browser()
        await self.act(view, 'select', str(self.check.id))
        self.repo.delete_check(100, self.check.id)
        event = await self.act(view, 'confirm')
        self.assertIn('이미 삭제', event.edit_original_response.call_args.kwargs['content'])

    async def test_large_details_fit_discord_limits(self):
        huge = replace(self.check, name='Long' * 2000,
                       members=tuple(CheckMember(i, self.check.created_at) for i in range(1000)),
                       schedules=tuple(CheckSchedule(i, i, '09:00', '22:00') for i in range(100)))
        pages = detail_pages(huge)
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(p.description) <= 4096 and len(p) <= 6000 for p in pages))
        self.assertIn('99회차', ''.join(p.description for p in pages))

    def seed_history(self):
        with connect_database(self.path) as db:
            db.execute("INSERT INTO daily_checkins (check_id, schedule_id, date, message_id) VALUES (?, ?, '2026-09-11', 400)",
                       (self.check.id, self.check.schedules[0].id))
            db.execute("INSERT INTO verifications (check_id, schedule_id, user_id, date, verification_method) VALUES (?, ?, 300, '2026-09-11', 'button')",
                       (self.check.id, self.check.schedules[0].id))

    async def test_repository_deletes_dependents_and_rejects_other_guild(self):
        self.seed_history()
        same_guild = self.repo.create_check(replace(self.data, name='Separate'))
        self.assertFalse(self.repo.delete_check(101, self.check.id))
        self.assertTrue(self.repo.delete_check(100, self.check.id))
        with connect_database(self.path) as db:
            for table in ('check_days', 'check_members', 'check_schedules', 'daily_checkins', 'verifications'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table} WHERE check_id = ?', (self.check.id,)).fetchone()[0], 0)
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')), [])
        self.assertIsNotNone(self.repo.get_check(101, self.other.id))
        self.assertEqual(self.repo.get_check(100, same_guild.id), same_guild)

    async def test_stale_confirmation_cannot_delete_reused_id(self):
        old = self.repo.create_check(replace(self.data, name='Old'))
        view = self.browser()
        await self.act(view, 'select', str(old.id))
        self.repo.delete_check(100, old.id)
        replacement = self.repo.create_check(replace(self.data, name='New'))
        self.assertEqual(old.id, replacement.id)
        await self.act(view, 'confirm')
        self.assertEqual(self.repo.get_check(100, replacement.id), replacement)

    async def test_delete_failure_rolls_back_all_records_and_allows_retry(self):
        self.seed_history()
        with connect_database(self.path) as db:
            db.execute("CREATE TRIGGER prevent_delete BEFORE DELETE ON checks BEGIN SELECT RAISE(ABORT, 'Test failure'); END")
        view = self.browser()
        await self.act(view, 'select', str(self.check.id))
        event = interaction()
        with self.assertRaises(sqlite3.IntegrityError) as error:
            await view.handle(event, 'confirm', view.revision)
        with self.assertLogs('doneyet.check_browser', level='ERROR'):
            await view.on_error(event, error.exception, None)
        self.assertTrue(event.followup.send.call_args.kwargs['ephemeral'])
        self.assertFalse(view.closed)
        with connect_database(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM verifications').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM daily_checkins').fetchone()[0], 1)
            db.execute('DROP TRIGGER prevent_delete')
        self.assertEqual(self.repo.get_check(100, self.check.id), self.check)
        await self.act(view, 'confirm')
        self.assertIsNone(self.repo.get_check(100, self.check.id))
