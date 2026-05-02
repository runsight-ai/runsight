"""IPC capability negotiation behavior."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from isolation_ipc_helpers import (
    _make_grant_token,
    _send_raw_request_and_collect_frames,
)

# ---------------------------------------------------------------------------
# Grant token authentication and RPC allowlist contract
# ---------------------------------------------------------------------------


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
