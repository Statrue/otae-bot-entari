from __future__ import annotations

import unittest
from unittest import mock

from arclet.letoderea.exceptions import ExitState

import plugins.endfield as endfield
from plugins.endfield import commands as commands_module


class EndfieldCalendarCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_calendar_finish_stop_is_propagated_without_failure_reply(self):
        matcher = mock.AsyncMock()
        matcher.finish.side_effect = ExitState.stop
        command = commands_module.parse_command("日历")

        with mock.patch.object(
            endfield,
            "_render_current_version_calendar",
            new=mock.AsyncMock(return_value=b"\x89PNG\r\n\x1a\n"),
        ):
            with self.assertRaises(ExitState):
                await endfield._handle_command(matcher, None, command)

        matcher.finish.assert_awaited_once()
