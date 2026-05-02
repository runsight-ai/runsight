"""Worker capability negotiation startup behavior."""

from __future__ import annotations

import pytest
from isolation_worker_helpers import (
    worker_socket_path,
)
from runsight_core.isolation.envelope import ToolDefEnvelope


class TestWorkerCapabilityNegotiationStartup:
    """Worker startup uses IPCClient.connect capability handshake."""

    @pytest.mark.asyncio
    async def test_tool_stub_uses_connect_handshake_without_legacy_capability_request(self):
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

        call_log: list[tuple[str, str | None]] = []

        class FakeIPCClient:
            def __init__(self, *, socket_path: str) -> None:
                self._socket_path = socket_path

            async def connect(self):
                call_log.append(("connect", None))
                return {
                    "id": "cap-worker-capability",
                    "done": True,
                    "accepted": True,
                    "active_actions": ["tool_call"],
                    "engine_context": {
                        "budget_remaining_usd": 15.0,
                        "trace_id": "trace-worker-capability",
                        "run_id": "worker-capability-run",
                        "block_id": "worker_block",
                    },
                    "error": None,
                }

            async def request(self, action: str, payload: dict[str, object]):
                call_log.append(("request", action))
                if action == "tool_call":
                    return {"output": f"echo:{payload['arguments']['value']}"}
                return {"error": "unexpected action"}

        ipc_client = FakeIPCClient(socket_path=worker_socket_path("capability"))
        await ipc_client.connect()
        stub = create_tool_stubs(tool_defs, ipc_client=ipc_client)[0]
        result = await stub.execute({"value": "hello"})

        assert call_log[0] == ("connect", None)
        assert ("request", "capability_negotiation") not in call_log
        assert ("request", "tool_call") in call_log
        assert result == "echo:hello"
