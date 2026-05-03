"""Subprocess harness IPC handler registration behavior."""

from __future__ import annotations

import pytest
from isolation_harness_helpers import (
    _tool_call_passthrough,
)

pytestmark = pytest.mark.real_subprocess_isolation


class TestIpcHandlerRegistration:
    """Harness should register all engine-side IPC handlers, including generic tool_call."""

    @pytest.mark.asyncio
    async def test_build_ipc_handlers_keeps_http_and_file_io_and_adds_tool_call(self):
        """Harness exposes tool_call without regressing existing handlers."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.tools import ToolInstance

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        harness._resolved_tools = {
            "echo_tool": ToolInstance(
                name="echo_tool",
                description="Echo input",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                execute=_tool_call_passthrough,
            )
        }

        handlers = harness._build_ipc_handlers()

        assert "http" in handlers
        assert "file_io" in handlers
        assert "tool_call" in handlers
        assert callable(handlers["http"])
        assert callable(handlers["file_io"])
        assert callable(handlers["tool_call"])
