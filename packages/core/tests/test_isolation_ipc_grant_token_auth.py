"""IPC grant-token authentication behavior."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from isolation_ipc_helpers import (
    _send_raw_request_and_collect_frames,
)

pytestmark = pytest.mark.real_subprocess_isolation

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
