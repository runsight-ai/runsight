"""Worker IPC tool stub behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.isolation.envelope import ToolDefEnvelope


class TestWorkerIPCToolStubs:
    """Tools must be routed through IPCClient, not executed locally."""

    def test_worker_creates_tool_stubs_from_envelope(self):
        """Worker converts ToolDefEnvelope list into IPC-backed tool stubs."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs
        from runsight_core.tools import ToolInstance

        tool_defs = [
            ToolDefEnvelope(
                source="http",
                config={"url": "worker-fixture-url"},
                exits=["done"],
                name="http_lookup",
                description="Look up a URL",
                parameters={"type": "object", "properties": {"url": {"type": "string"}}},
                tool_type="http",
            ),
        ]
        stubs = create_tool_stubs(tool_defs, ipc_client=object())
        assert len(stubs) == 1
        assert isinstance(stubs[0], ToolInstance)

    def test_tool_stubs_are_callable(self):
        """Each tool stub must be callable (used as a tool function)."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="http",
                config={"url": "worker-fixture-url"},
                exits=["done"],
                name="http_lookup",
                description="Look up a URL",
                parameters={"type": "object", "properties": {"url": {"type": "string"}}},
                tool_type="http",
            ),
        ]
        stubs = create_tool_stubs(tool_defs, ipc_client=object())
        assert callable(stubs[0].execute)

    def test_tool_stub_openai_schema_comes_from_envelope_metadata(self):
        """Stub to_openai_schema should use name/description/parameters from ToolDefEnvelope."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="fixture/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        stub = create_tool_stubs(tool_defs, ipc_client=object())[0]
        schema = stub.to_openai_schema()

        assert schema == {
            "type": "function",
            "function": {
                "name": "echo_tool",
                "description": "Echoes a string",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                },
            },
        }

    @pytest.mark.asyncio
    async def test_tool_stub_execute_sends_tool_call_request_to_ipc_client(self):
        """Stub execute() should call IPCClient.request('tool_call', ...) with tool name + args."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="fixture/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        client = MagicMock()
        client.request = AsyncMock(return_value={"output": "echo:hi"})

        stub = create_tool_stubs(tool_defs, ipc_client=client)[0]
        result = await stub.execute({"value": "hi"})

        client.request.assert_awaited_once_with(
            "tool_call",
            {"name": "echo_tool", "arguments": {"value": "hi"}},
        )
        assert result == "echo:hi"

    @pytest.mark.asyncio
    async def test_tool_stub_returns_error_string_on_ipc_error(self):
        """IPC error payloads should come back as 'Error: ...' strings."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="fixture/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        client = MagicMock()
        client.request = AsyncMock(return_value={"error": "tool failed"})

        stub = create_tool_stubs(tool_defs, ipc_client=client)[0]
        result = await stub.execute({"value": "hi"})

        assert result == "Error: tool failed"
