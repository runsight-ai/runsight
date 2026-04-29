"""IPC tool call integration tests."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from runsight_core.isolation.handlers import make_tool_call_handler
from runsight_core.isolation.ipc import IPCServer
from runsight_core.tools import ToolInstance


class TestIpcToolCalls:
    """Tool calls should round-trip across the IPC boundary."""

    @pytest.mark.asyncio
    async def test_ipc_tool_call_round_trip_returns_engine_tool_output(
        self, tmp_path: Path
    ) -> None:
        """tool_call actions should round-trip through the IPC server."""

        async def _echo(args: dict[str, Any]) -> str:
            return f"echo:{args['value']}"

        socket_path = tmp_path / "tool_call.sock"
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(socket_path))
        sock.listen(1)

        from runsight_core.isolation.ipc_models import GrantToken

        grant = GrantToken(block_id="test-tool-call")
        server = IPCServer(
            sock=sock,
            handlers={
                "tool_call": make_tool_call_handler(
                    {
                        "echo_tool": ToolInstance(
                            name="echo_tool",
                            description="Echo values.",
                            parameters={
                                "type": "object",
                                "properties": {"value": {"type": "string"}},
                                "required": ["value"],
                            },
                            execute=_echo,
                        )
                    }
                )
            },
            grant_token=grant,
        )
        server_task = asyncio.create_task(server.serve())
        await asyncio.sleep(0)

        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))

            # Capability negotiation
            cap_req = (
                json.dumps(
                    {
                        "action": "capability_negotiation",
                        "id": "cap-1",
                        "grant_token": grant.token,
                        "supported_actions": ["tool_call"],
                        "worker_version": "test",
                    }
                )
                + "\n"
            )
            writer.write(cap_req.encode())
            await writer.drain()
            cap_resp = json.loads(await asyncio.wait_for(reader.readline(), timeout=2))
            assert cap_resp.get("accepted") is True

            # Tool call
            tool_req = (
                json.dumps(
                    {
                        "id": "tc-1",
                        "action": "tool_call",
                        "payload": {"name": "echo_tool", "arguments": {"value": "hi"}},
                    }
                )
                + "\n"
            )
            writer.write(tool_req.encode())
            await writer.drain()
            tool_resp = json.loads(await asyncio.wait_for(reader.readline(), timeout=2))
            assert tool_resp.get("done") is True
            assert tool_resp["payload"]["output"] == "echo:hi"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.shutdown()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            sock.close()
            socket_path.unlink(missing_ok=True)
