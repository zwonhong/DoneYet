import contextlib
import io
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from doneyet.bot import DoneYetBot
from doneyet.config import load_guild_id


class CommandSyncTests(unittest.IsolatedAsyncioTestCase):
    async def make_bot(self, guild_id=None):
        bot = DoneYetBot(guild_id=guild_id)
        self.addAsyncCleanup(bot.close)
        return bot

    def remote_commands(self, bot, guild=None):
        # Use real Discord AppCommand parsing to exercise the returned group payload.
        commands = []
        for index, command in enumerate(bot.tree.get_commands(guild=guild), 1):
            payload = command.to_dict(bot.tree)
            payload.update(id=str(index), application_id='123', version='1')
            if guild:
                payload['guild_id'] = str(guild.id)
            commands.append(discord.app_commands.AppCommand(data=payload, state=bot._connection))
        return commands

    async def test_global_sync_contains_group_and_subcommand_before_request(self):
        bot = await self.make_bot()

        async def sync(*, guild=None):
            self.assertIsNone(guild)
            group = bot.tree.get_command('check')
            self.assertIsNotNone(group.get_command('create'))
            self.assertIsNotNone(bot.tree.get_command('test'))
            return self.remote_commands(bot)

        bot.tree.sync = AsyncMock(side_effect=sync)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            await bot.setup_hook()
        bot.tree.sync.assert_awaited_once_with(guild=None)
        self.assertIn('Synced 2 application commands [global]:', output.getvalue())
        self.assertIn('application_id=', output.getvalue())
        self.assertIn('- /check (id=2)', output.getvalue())

    async def test_development_guild_is_copied_before_sync_and_keeps_test(self):
        bot = await self.make_bot(456)

        async def sync(*, guild=None):
            self.assertEqual({c.name for c in bot.tree.get_commands(guild=guild)}, {'test', 'check'})
            self.assertIsNotNone(bot.tree.get_command('check', guild=guild).get_command('create'))
            return self.remote_commands(bot, guild)

        bot.tree.sync = AsyncMock(side_effect=sync)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            await bot.setup_hook()
        self.assertEqual(bot.tree.sync.await_count, 2)
        self.assertIsNone(bot.tree.sync.await_args_list[0].kwargs['guild'])
        self.assertEqual(bot.tree.sync.await_args_list[1].kwargs['guild'].id, 456)
        self.assertIn('Synced 2 application commands [guild:456]:', output.getvalue())

    async def test_real_tree_sync_sends_group_in_global_http_payload(self):
        bot = await self.make_bot()
        bot._connection.application_id = 123

        async def upsert(application_id, *, payload):
            self.assertEqual(application_id, 123)
            self.assertEqual([command['name'] for command in payload], ['test', 'check'])
            group = payload[1]
            self.assertEqual(group['options'][0]['name'], 'create')
            self.assertEqual(group['options'][0]['type'], 1)
            self.assertFalse(group['dm_permission'])
            return [dict(command, id=str(index), application_id='123', version='1')
                    for index, command in enumerate(payload, 1)]

        # Keep the real CommandTree.sync implementation; intercept only HTTP.
        with patch.object(bot.http, 'bulk_upsert_global_commands', new_callable=AsyncMock, side_effect=upsert) as http, \
             patch.object(bot.http, 'bulk_upsert_guild_commands', new_callable=AsyncMock) as guild_http, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            await bot.setup_hook()
        http.assert_awaited_once()
        guild_http.assert_not_awaited()
        self.assertEqual(bot.tree.get_commands(guild=discord.Object(id=456)), [])
        self.assertIn('- /test (id=1)', output.getvalue())
        self.assertIn('- /check (id=2)', output.getvalue())

    async def test_sync_failure_is_logged_and_propagated(self):
        bot = await self.make_bot()
        bot.tree.sync = AsyncMock(side_effect=RuntimeError('Simulated sync failure'))
        with contextlib.redirect_stdout(io.StringIO()), self.assertLogs('doneyet.bot', level='ERROR') as logs:
            with self.assertRaisesRegex(RuntimeError, 'Simulated sync failure'):
                await bot.setup_hook()
        self.assertIn('command sync failed [global]', logs.output[0])

    async def test_missing_remote_group_cannot_look_like_success(self):
        bot = await self.make_bot()
        bot.tree.sync = AsyncMock(return_value=self.remote_commands(bot)[:1])
        with contextlib.redirect_stdout(io.StringIO()), self.assertLogs('doneyet.bot', level='ERROR'):
            with self.assertRaisesRegex(RuntimeError, 'Command sync mismatch'):
                await bot.setup_hook()

    async def test_ready_does_not_resync(self):
        bot = await self.make_bot()
        bot.tree.sync = AsyncMock()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            await bot.on_ready()
            await bot.on_ready()
        self.assertIn('DoneYet? logged in as', output.getvalue())
        bot.tree.sync.assert_not_awaited()


class GuildConfigurationTests(unittest.TestCase):
    def test_optional_guild_id(self):
        for value, expected in [('', None), ('  ', None), (' 456 ', 456)]:
            with self.subTest(value=value), patch('doneyet.config.load_dotenv'), patch.dict(os.environ, {'DISCORD_GUILD_ID': value}):
                self.assertEqual(load_guild_id(), expected)

    def test_invalid_guild_id(self):
        for value in ('abc', '0', '-1', '1.5', str(2**64)):
            with self.subTest(value=value), patch('doneyet.config.load_dotenv'), patch.dict(os.environ, {'DISCORD_GUILD_ID': value}):
                with self.assertRaises(ValueError):
                    load_guild_id()

    def test_main_passes_configuration_to_bot(self):
        import main

        with patch.object(main, 'load_token', return_value='dummy-token'), \
             patch.object(main, 'load_guild_id', return_value=456), \
             patch.object(main, 'initialize_database') as initialize, \
             patch.object(main, 'DoneYetBot') as bot:
            main.main()
        initialize.assert_called_once_with()
        bot.assert_called_once_with(guild_id=456)
        bot.return_value.run.assert_called_once_with('dummy-token')


if __name__ == '__main__':
    unittest.main()
