import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from doneyet.database import initialize_database
from doneyet.member_commands import MemberView
from doneyet.models import CheckInput, ScheduleInput, VerificationMode
from doneyet.repository import CheckRepository


class ParticipantNameTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_participant_name_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db'; initialize_database(path)
            repo = CheckRepository(path)
            check = repo.create_check(CheckInput(100, 200, 'Test', VerificationMode.BUTTON, (300,), (0,), (ScheduleInput('09:00', '22:00'),)))
            view = MemberView(1, 100, repo, [check], 'add')
            view.check_id = check.id; view.selected_check = check
            user = SimpleNamespace(id=400, display_name='Alice')
            view.available_users = [user]
            view._build()
            event = SimpleNamespace(user=SimpleNamespace(id=1), guild_id=100, data={'values': ['400']}, response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()))
            await view._user(event)
            self.assertEqual(view.children[1].placeholder, '선택됨: Alice')
            self.assertTrue(view.children[1].options[0].default)
            view.stop()


if __name__ == '__main__': unittest.main()
