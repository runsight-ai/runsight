"""Worker IPC tool stub behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.isolation import (
    HostToolExecutionRef,
    HostToolExecutionRegistry,
    WorkerToolSchema,
)
from runsight_core.isolation.envelope import ToolDefEnvelope
from runsight_core.isolation.handlers import make_tool_call_handler
from runsight_core.tools import ToolInstance

pytestmark = pytest.mark.real_subprocess_isolation


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
    async def test_tool_stub_dispatches_same_name_tool_by_hidden_binding_id(self):
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        left_calls: list[dict[str, object]] = []
        right_calls: list[dict[str, object]] = []

        async def execute_left(args: dict[str, object]) -> str:
            left_calls.append(args)
            return "left-output"

        async def execute_right(args: dict[str, object]) -> str:
            right_calls.append(args)
            return "right-output"

        parameters = {"type": "object", "properties": {"value": {"type": "string"}}}
        handler = make_tool_call_handler(
            host_tools=HostToolExecutionRegistry(
                tools=[
                    HostToolExecutionRef(
                        name="shared",
                        binding_id="left-binding",
                        tool=ToolInstance(
                            name="shared",
                            description="Left config.",
                            parameters=parameters,
                            execute=execute_left,
                        ),
                    ),
                    HostToolExecutionRef(
                        name="shared",
                        binding_id="right-binding",
                        tool=ToolInstance(
                            name="shared",
                            description="Right config.",
                            parameters=parameters,
                            execute=execute_right,
                        ),
                    ),
                ]
            ),
            worker_tools=[
                WorkerToolSchema(
                    name="shared",
                    binding_id="right-binding",
                    description="Right config.",
                    parameters=parameters,
                )
            ],
        )

        class _HandlerIPCClient:
            def __init__(self) -> None:
                self.payloads: list[dict[str, object]] = []

            async def request(self, action: str, payload: dict[str, object]) -> dict[str, object]:
                assert action == "tool_call"
                self.payloads.append(payload)
                return await handler(payload)

        client = _HandlerIPCClient()
        stub = create_tool_stubs(
            [
                ToolDefEnvelope(
                    source="host",
                    binding_id="right-binding",
                    config={},
                    exits=[],
                    name="shared",
                    description="Right config.",
                    parameters=parameters,
                    tool_type="host",
                )
            ],
            ipc_client=client,
        )[0]

        result = await stub.execute({"value": "hi"})

        assert result == "right-output"
        assert client.payloads == [
            {
                "name": "shared",
                "binding_id": "right-binding",
                "arguments": {"value": "hi"},
            }
        ]
        assert left_calls == []
        assert right_calls == [{"value": "hi"}]

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
