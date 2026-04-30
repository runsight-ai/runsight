"""IPC server dispatch and RPC action tests."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from isolation_ipc_helpers import (
    _connect_client_with_grant_token,
    _make_grant_token,
)

# ---------------------------------------------------------------------------
# IPCServer dispatches http, file_io, delegate, and write_artifact actions
# ---------------------------------------------------------------------------


class TestIPCServerDispatches:
    """IPCServer must dispatch to the correct handler based on the action field."""

    @pytest.mark.asyncio
    async def test_dispatches_http_action(self, tmp_path: Path):
        """IPCServer dispatches 'http' action to its http handler."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "dispatch_http.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        http_called = False

        async def http_handler(params: dict) -> dict:
            nonlocal http_called
            http_called = True
            return {"status_code": 200, "body": "response", "headers": {}}

        grant_token = _make_grant_token(block_id="dispatch-http")
        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request("http", {"method": "GET", "url": "http://example.com"})
            assert http_called
            assert result["status_code"] == 200
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_dispatches_file_io_action(self, tmp_path: Path):
        """IPCServer dispatches 'file_io' action to its file_io handler."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "dispatch_fio.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def file_io_handler(params: dict) -> dict:
            return {"content": "file contents here"}

        grant_token = _make_grant_token(block_id="dispatch-fileio")
        server = IPCServer(
            sock=server_sock,
            handlers={"file_io": file_io_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request("file_io", {"action_type": "read", "path": "/tmp/f.txt"})
            assert result["content"] == "file contents here"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_dispatches_delegate_action(self, tmp_path: Path):
        """IPCServer dispatches 'delegate' action to its delegate handler."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "dispatch_del.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def delegate_handler(params: dict) -> dict:
            return {"ok": True}

        grant_token = _make_grant_token(block_id="dispatch-delegate")
        server = IPCServer(
            sock=server_sock,
            handlers={"delegate": delegate_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request("delegate", {"port": "output", "task": "do thing"})
            assert result["ok"] is True
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_dispatches_write_artifact_action(self, tmp_path: Path):
        """IPCServer dispatches 'write_artifact' action to its write_artifact handler."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "dispatch_wa.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def write_artifact_handler(params: dict) -> dict:
            return {"ref": "artifact://block-1/my-key"}

        grant_token = _make_grant_token(block_id="dispatch-artifact")
        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request(
                "write_artifact", {"key": "my-key", "content": "data", "metadata": {}}
            )
            assert result["ref"] == "artifact://block-1/my-key"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# RPC action allowlist
# ---------------------------------------------------------------------------


class TestRPCActions:
    """IPCServer should dispatch allowed actions and reject unknown actions."""

    @pytest.mark.asyncio
    async def test_llm_call_action_dispatched_when_handler_registered(self, tmp_path: Path):
        """llm_call is dispatchable when explicitly registered in handlers."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "llm_allowed.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        llm_called = False

        async def llm_handler(params: dict[str, Any]) -> dict[str, Any]:
            nonlocal llm_called
            llm_called = True
            return {"output": f"completion for {params['prompt']}"}

        grant_token = _make_grant_token(block_id="llm-allowed")
        server = IPCServer(
            sock=server_sock,
            handlers={
                "llm_call": llm_handler,
            },
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request("llm_call", {"prompt": "hello"})

            assert llm_called is True
            assert result == {"output": "completion for hello"}
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_unknown_action_rejected(self, tmp_path: Path):
        """Sending an unknown action results in an error response."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "unknown_act.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        grant_token = _make_grant_token(block_id="unknown-action")
        server = IPCServer(
            sock=server_sock,
            handlers={
                "http": AsyncMock(return_value={}),
            },
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request("totally_fake_action", {"foo": "bar"})

            assert "error" in result
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)
