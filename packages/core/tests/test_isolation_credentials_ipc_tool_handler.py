"""Credential scoping and generic IPC tool-call handler behavior."""

from __future__ import annotations

import pytest
from isolation_credentials_helpers import _tool_call_boom, _tool_call_echo
from runsight_core.isolation import SubprocessHarness

pytestmark = pytest.mark.real_subprocess_isolation


class TestSubprocessCredentialScoping:
    """Harness must resolve tool credentials and pass them only via IPC handlers."""

    def test_harness_accepts_tool_credentials(self):
        """SubprocessHarness accepts a tool_credentials dict for IPC handler setup."""
        harness = SubprocessHarness(
            api_keys={"fixture-provider": "dummy-provider-key"},
            tool_credentials={
                "credentialed_http_tool": {"Authorization": "Bearer dummy-credential"}
            },
        )
        assert harness is not None

    def test_tool_credentials_not_in_subprocess_env(self):
        """Tool credentials must not appear in the subprocess environment."""
        harness = SubprocessHarness(
            api_keys={"fixture-provider": "dummy-provider-key"},
            tool_credentials={
                "credentialed_http_tool": {"Authorization": "Bearer dummy-tool-credential"}
            },
        )
        env = harness._build_subprocess_env(socket_path="fixture.sock")

        # The tool credential value must not appear anywhere in the env
        all_env_values = " ".join(env.values())
        assert "dummy-tool-credential" not in all_env_values

    def test_harness_creates_handlers_with_credentials(self):
        """Harness builds IPC handlers that have the tool credentials baked in."""
        harness = SubprocessHarness(
            api_keys={"fixture-provider": "dummy-provider-key"},
            tool_credentials={
                "credentialed_http_tool": {"Authorization": "Bearer dummy-injected-credential"}
            },
        )
        handlers = harness._build_ipc_handlers()
        assert "http" in handlers
        assert "file_io" in handlers


# ---------------------------------------------------------------------------
# Generic tool_call IPC handler
# ---------------------------------------------------------------------------


class TestGenericToolCallHandler:
    """Generic IPC tool_call handler dispatches to resolved ToolInstances by name."""

    @pytest.mark.asyncio
    async def test_make_tool_call_handler_dispatches_to_tool_by_name(self):
        """Resolved tool instances should be callable through the generic tool_call handler."""
        from runsight_core.isolation.handlers import make_tool_call_handler
        from runsight_core.tools import ToolInstance

        handler = make_tool_call_handler(
            {
                "echo_tool": ToolInstance(
                    name="echo_tool",
                    description="Echoes input",
                    parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                    execute=_tool_call_echo,
                )
            }
        )

        result = await handler({"name": "echo_tool", "arguments": {"value": "hi"}})

        assert result == {"output": "echo:hi"}

    @pytest.mark.asyncio
    async def test_make_tool_call_handler_returns_error_for_unknown_tool_name(self):
        """Unknown tool names should not crash the handler."""
        from runsight_core.isolation.handlers import make_tool_call_handler

        handler = make_tool_call_handler({})

        result = await handler({"name": "missing_tool", "arguments": {"value": "hi"}})

        assert "error" in result
        assert "missing_tool" in result["error"]

    @pytest.mark.asyncio
    async def test_make_tool_call_handler_catches_execute_exceptions(self):
        """Tool execution exceptions should be returned as error strings."""
        from runsight_core.isolation.handlers import make_tool_call_handler
        from runsight_core.tools import ToolInstance

        handler = make_tool_call_handler(
            {
                "boom_tool": ToolInstance(
                    name="boom_tool",
                    description="Always fails",
                    parameters={"type": "object", "properties": {}},
                    execute=_tool_call_boom,
                )
            }
        )

        result = await handler({"name": "boom_tool", "arguments": {}})

        assert "error" in result
        assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# LLM handler budget ownership
# ---------------------------------------------------------------------------
