"""IPC grant-token authentication and capability handshake tests."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from isolation_ipc_helpers import (
    _capability_response_for,
    _make_grant_token,
    _send_raw_request_and_collect_frames,
)

# ---------------------------------------------------------------------------
# Grant token authentication and RPC allowlist contract
# ---------------------------------------------------------------------------


class TestGrantTokenAuthAndAllowlist:
    """Grant-token auth and allowlist-based action control for IPC server."""

    def test_rpc_allowlist_includes_llm_and_capability_actions(self):
        from runsight_core.isolation import ipc as ipc_module
        from runsight_core.isolation.ipc_models import RPC_ALLOWLIST

        allowlist = RPC_ALLOWLIST
        assert allowlist is not None
        assert {
            "llm_call",
            "tool_call",
            "http",
            "file_io",
            "capability_negotiation",
        }.issubset(set(allowlist))

        blocked_actions = getattr(ipc_module, "BLOCKED_ACTIONS", None)
        assert blocked_actions is None or "llm_call" not in blocked_actions

    @pytest.mark.asyncio
    async def test_ipc_server_without_grant_token_does_not_allow_unauthenticated_mode(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer

        sock_path = tmp_path / "auth-no-bypass.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        handler_called = False

        async def simple_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_called
            handler_called = True
            return {"status": "ok"}

        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "auth-no-bypass-request-1",
                    "action": "simple",
                    "payload": {"value": 1},
                },
            )
            assert handler_called is False
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] is None
            assert "auth" in (frames[0]["error"] or "").lower()
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected_before_handler_executes(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation.ipc_models import GrantToken

        grant = GrantToken(block_id="auth-block")

        sock_path = tmp_path / "auth-unauthorized.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        handler_called = False

        async def http_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_called
            handler_called = True
            return {"status_code": 200}

        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
            grant_token=grant,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "auth-unauthorized-request-1",
                    "action": "http",
                    "payload": {"method": "GET", "url": "https://fixture.test"},
                },
            )
            assert handler_called is False
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] is None
            assert "auth" in (frames[0]["error"] or "").lower()
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_second_connection_with_same_token_is_rejected(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation.ipc_models import GrantToken

        grant = GrantToken(block_id="auth-block")

        sock_path = tmp_path / "auth-consume.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        server = IPCServer(
            sock=server_sock,
            handlers={"http": AsyncMock(return_value={"ok": True})},
            grant_token=grant,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            first_frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "auth-request-1",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["http", "tool_call"],
                    "worker_version": "auth-worker",
                },
            )
            assert len(first_frames) == 1
            first_frame = first_frames[-1]
            assert set(first_frame) == {
                "id",
                "done",
                "accepted",
                "active_actions",
                "engine_context",
                "error",
            }
            assert first_frame["done"] is True
            assert first_frame["accepted"] is True
            assert first_frame["active_actions"] == ["http"]
            assert first_frame["error"] is None

            second_frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "auth-request-2",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["http", "tool_call"],
                    "worker_version": "auth-worker",
                },
            )
            second_frame = second_frames[-1]
            assert set(second_frame) == {
                "id",
                "done",
                "accepted",
                "active_actions",
                "engine_context",
                "error",
            }
            assert second_frame["done"] is True
            assert second_frame["accepted"] is False
            assert second_frame["active_actions"] == []
            assert "rejected" in (second_frame["error"] or "").lower()
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_expired_grant_token_is_rejected(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation.ipc_models import GrantToken

        grant = GrantToken(block_id="auth-block", created_at=0.0, ttl_seconds=30.0)

        sock_path = tmp_path / "auth-expired.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        server = IPCServer(
            sock=server_sock,
            handlers={"http": AsyncMock(return_value={"ok": True})},
            grant_token=grant,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "auth-expired-request-1",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["http"],
                    "worker_version": "auth-worker",
                },
            )
            assert len(frames) == 1
            frame = frames[0]
            assert set(frame) == {
                "id",
                "done",
                "accepted",
                "active_actions",
                "engine_context",
                "error",
            }
            assert frame["done"] is True
            assert frame["accepted"] is False
            assert frame["active_actions"] == []
            assert "rejected" in (frame["error"] or "").lower()
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


class TestCapabilityNegotiationProtocol:
    """Dedicated capability handshake models and startup flow."""

    def test_capability_request_model_exists_with_dedicated_fields(self):
        from runsight_core.isolation.ipc_models import CapabilityRequest

        assert set(CapabilityRequest.model_fields) == {
            "action",
            "id",
            "grant_token",
            "supported_actions",
            "worker_version",
        }
        request = CapabilityRequest(
            grant_token="handshake-grant",
            supported_actions=["llm_call", "tool_call", "http"],
            worker_version="handshake-worker",
        )
        assert request.action == "capability_negotiation"
        assert "payload" not in CapabilityRequest.model_fields

    def test_capability_response_model_exists_with_dedicated_fields(self):
        from runsight_core.isolation.ipc_models import CapabilityResponse

        assert set(CapabilityResponse.model_fields) == {
            "id",
            "done",
            "accepted",
            "active_actions",
            "engine_context",
            "error",
        }

    @pytest.mark.asyncio
    async def test_handshake_returns_active_actions_intersection_and_initial_context(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer

        grant = _make_grant_token(block_id="capability-handshake-block")
        sock_path = tmp_path / "capability-handshake.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        server = IPCServer(
            sock=server_sock,
            handlers={
                "llm_call": AsyncMock(return_value={"output": "ok"}),
                "tool_call": AsyncMock(return_value={"output": "ok"}),
                "http": AsyncMock(return_value={"status_code": 200}),
            },
            grant_token=grant,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "capability-request-1",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["llm_call", "tool_call", "http"],
                    "worker_version": "handshake-worker",
                },
            )
            assert len(frames) == 1
            frame = frames[0]
            assert set(frame) == {
                "id",
                "done",
                "accepted",
                "active_actions",
                "engine_context",
                "error",
            }
            assert frame["id"] == "capability-request-1"
            assert frame["done"] is True
            assert frame["accepted"] is True
            assert frame["active_actions"] == ["llm_call", "tool_call", "http"]
            assert frame["error"] is None
            assert set(frame["engine_context"]) >= {
                "budget_remaining_usd",
                "trace_id",
                "run_id",
                "block_id",
            }
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_invalid_grant_token_returns_rejected_capability_response(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer

        grant = _make_grant_token(block_id="capability-invalid-block")
        sock_path = tmp_path / "capability-invalid.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        server = IPCServer(
            sock=server_sock,
            handlers={"llm_call": AsyncMock(return_value={"output": "ok"})},
            grant_token=grant,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "capability-invalid-request",
                    "action": "capability_negotiation",
                    "grant_token": "wrong-token",
                    "supported_actions": ["llm_call"],
                    "worker_version": "handshake-worker",
                },
            )
            assert len(frames) == 1
            frame = frames[0]
            assert set(frame) == {
                "id",
                "done",
                "accepted",
                "active_actions",
                "engine_context",
                "error",
            }
            assert frame["done"] is True
            assert frame["accepted"] is False
            assert frame["active_actions"] == []
            assert frame["error"] is not None
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_legacy_payload_style_capability_request_is_rejected(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer

        grant = _make_grant_token(block_id="capability-no-shim-block")
        sock_path = tmp_path / "capability-no-shim.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        server = IPCServer(
            sock=server_sock,
            handlers={"tool_call": AsyncMock(return_value={"output": "ok"})},
            grant_token=grant,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "capability-legacy-request",
                    "action": "capability_negotiation",
                    "payload": {
                        "grant_token": grant.token,
                        "supported_actions": ["tool_call"],
                        "worker_version": "legacy-worker",
                    },
                },
            )
            assert len(frames) == 1
            frame = frames[0]
            assert set(frame) == {
                "id",
                "done",
                "accepted",
                "active_actions",
                "engine_context",
                "error",
            }
            assert frame["done"] is True
            assert frame["accepted"] is False
            assert frame["active_actions"] == []
            assert frame["error"] is not None
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


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
