"""IPC client connect handshake behavior."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from isolation_ipc_helpers import (
    _capability_response_for,
)

# ---------------------------------------------------------------------------
# Grant token authentication and RPC allowlist contract
# ---------------------------------------------------------------------------


class TestIPCClientConnectHandshake:
    """IPCClient.connect performs startup capability negotiation."""

    @pytest.mark.asyncio
    async def test_connect_sends_capability_request_and_returns_capability_response(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "client-connect-handshake.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        observed_first_frame: dict[str, Any] = {}

        async def fake_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            try:
                raw = await asyncio.wait_for(loop.sock_recv(conn, 4096), timeout=0.25)
                if not raw:
                    return
                observed_first_frame.update(json.loads(raw.decode().strip()))
                response = (
                    json.dumps(
                        {
                            "id": observed_first_frame.get("id", ""),
                            "done": True,
                            "accepted": True,
                            "active_actions": ["tool_call"],
                            "engine_context": {
                                "budget_remaining_usd": 50.0,
                                "trace_id": "capability-trace",
                                "run_id": "capability-run",
                                "block_id": "capability-block",
                            },
                            "error": None,
                        }
                    )
                    + "\n"
                )
                await loop.sock_sendall(conn, response.encode())
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_server())
        client = IPCClient(socket_path=str(sock_path))
        try:
            capability_response = await client.connect()
            assert observed_first_frame["action"] == "capability_negotiation"
            assert set(observed_first_frame) == {
                "id",
                "action",
                "grant_token",
                "supported_actions",
                "worker_version",
            }

            assert capability_response is not None
            accepted = (
                capability_response["accepted"]
                if isinstance(capability_response, dict)
                else capability_response.accepted
            )
            assert accepted is True

            active_actions = getattr(client, "active_actions", None) or getattr(
                client, "_active_actions", None
            )
            initial_engine_context = getattr(client, "initial_engine_context", None) or getattr(
                client, "_initial_engine_context", None
            )
            assert active_actions == ["tool_call"]
            assert set(initial_engine_context) >= {
                "budget_remaining_usd",
                "trace_id",
                "run_id",
                "block_id",
            }
        finally:
            await client.close()
            await server_task
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_request_rejects_manual_capability_negotiation_action(self, tmp_path: Path):
        """Only connect() owns capability negotiation; request() must reject it."""
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "capability-no-dual.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        async def fake_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                assert raw_capability
                capability_request = json.loads(raw_capability)
                capability_response = (
                    json.dumps(
                        _capability_response_for(capability_request, active_actions=["tool_call"])
                    )
                    + "\n"
                )
                writer.write(capability_response.encode())
                await writer.drain()

                try:
                    raw_manual = await asyncio.wait_for(reader.readline(), timeout=0.2)
                except asyncio.TimeoutError:
                    raw_manual = b""

                if raw_manual:
                    manual_request = json.loads(raw_manual)
                    manual_response = (
                        json.dumps(
                            _capability_response_for(
                                manual_request,
                                accepted=True,
                                active_actions=["tool_call"],
                            )
                        )
                        + "\n"
                    )
                    writer.write(manual_response.encode())
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server_task = asyncio.create_task(fake_server())
        client = IPCClient(socket_path=str(sock_path))
        try:
            await client.connect()
            with pytest.raises((ValueError, RuntimeError, ConnectionError)):
                await client.request(
                    "capability_negotiation",
                    {
                        "grant_token": "manual-token",
                        "supported_actions": ["tool_call"],
                        "worker_version": "handshake-worker",
                    },
                )
        finally:
            await client.close()
            await server_task
            server_sock.close()
            sock_path.unlink(missing_ok=True)
