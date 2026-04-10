"""
Failing tests for RUN-393: ISO-002 — IPC protocol (Unix socket server + IPCClient).

Tests cover every AC item:
1.  NDJSON framing (newline-delimited JSON, readline-based)
2.  IPCServer dispatches: http, file_io, delegate, write_artifact
3.  IPCServer accepts existing socket (does not create it)
4.  IPCClient.request() sends NDJSON, reads response with matching id
5.  Socket cleaned up on subprocess exit
6.  No llm_call action
7.  write_artifact writes to engine-side ArtifactStore, returns ref
8.  Socket drop causes block failure (no reconnection)
9.  Integration test: HTTP tool round-trip through IPC
10. Integration test: write_artifact round-trip through IPC
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest


async def _send_raw_request_and_collect_frames(
    socket_path: Path,
    request: dict[str, Any],
    *,
    max_frames: int = 10,
) -> list[dict[str, Any]]:
    """Send one NDJSON request and collect response frames until done or timeout."""
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        line = json.dumps(request, separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

        frames: list[dict[str, Any]] = []
        for _ in range(max_frames):
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=0.2)
            except asyncio.TimeoutError:
                break
            if not raw:
                break
            frames.append(json.loads(raw))
            if frames[-1].get("done") is True:
                break
        return frames
    finally:
        writer.close()
        await writer.wait_closed()


def _make_grant_token(*, block_id: str = "test-block"):
    from runsight_core.isolation import ipc as ipc_module

    GrantToken = getattr(ipc_module, "GrantToken", None)
    assert GrantToken is not None
    return GrantToken(block_id=block_id)


async def _authenticate_client_with_grant_token(client, grant_token) -> dict[str, Any]:
    auth_result = await client.request(
        "capability_negotiation",
        {"grant_token": grant_token.token},
    )
    assert isinstance(auth_result, dict)
    assert auth_result.get("authenticated") is True
    return auth_result


async def _raw_authenticate_with_grant_token(socket_path: Path, grant_token) -> dict[str, Any]:
    frames = await _send_raw_request_and_collect_frames(
        socket_path,
        {
            "id": "req-auth-1",
            "action": "capability_negotiation",
            "payload": {"grant_token": grant_token.token},
        },
    )
    assert len(frames) == 1
    assert frames[0]["done"] is True
    assert frames[0]["error"] is None
    return frames[0]


async def _send_raw_authenticated_request_and_collect_frames(
    socket_path: Path,
    grant_token,
    request: dict[str, Any],
    *,
    max_frames: int = 10,
) -> list[dict[str, Any]]:
    """Authenticate and send one NDJSON request on the same connection."""
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        auth_line = (
            json.dumps(
                {
                    "id": "req-auth-1",
                    "action": "capability_negotiation",
                    "payload": {"grant_token": grant_token.token},
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        writer.write(auth_line.encode())
        await writer.drain()

        auth_raw = await asyncio.wait_for(reader.readline(), timeout=0.2)
        assert auth_raw
        auth_frame = json.loads(auth_raw)
        assert auth_frame["done"] is True
        assert auth_frame["error"] is None

        line = json.dumps(request, separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

        frames: list[dict[str, Any]] = []
        for _ in range(max_frames):
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=0.2)
            except asyncio.TimeoutError:
                break
            if not raw:
                break
            frames.append(json.loads(raw))
            if frames[-1].get("done") is True:
                break
        return frames
    finally:
        writer.close()
        await writer.wait_closed()


# ---------------------------------------------------------------------------
# AC3: IPCServer accepts existing socket (does not create it)
# ---------------------------------------------------------------------------


class TestIPCServerAcceptsExistingSocket:
    """IPCServer must accept an already-bound socket, not create one."""

    @pytest.mark.asyncio
    async def test_ipc_server_importable(self):
        """IPCServer can be imported from runsight_core.isolation."""
        from runsight_core.isolation import IPCServer

        assert IPCServer is not None

    @pytest.mark.asyncio
    async def test_ipc_server_does_not_create_socket(self, tmp_path: Path):
        """IPCServer does not create or bind the socket itself."""
        from runsight_core.isolation import IPCServer

        sock_path = tmp_path / "test.sock"
        # Socket does NOT exist yet — server should accept an existing one,
        # not create it. We pass a pre-bound socket object.
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(sock_path))
            sock.listen(1)
            server = IPCServer(sock=sock, handlers={}, grant_token=_make_grant_token())
            # The server should wrap the existing socket, not create a new file
            assert sock_path.exists()
            assert server is not None
        finally:
            sock.close()
            if sock_path.exists():
                sock_path.unlink()

    @pytest.mark.asyncio
    async def test_ipc_server_raises_on_raw_path_string(self, tmp_path: Path):
        """IPCServer should require a socket object, not a path string."""
        from runsight_core.isolation import IPCServer

        with pytest.raises((TypeError, ValueError)):
            IPCServer(
                sock=str(tmp_path / "no.sock"),
                handlers={},
                grant_token=_make_grant_token(),
            )


# ---------------------------------------------------------------------------
# AC1: NDJSON framing (newline-delimited JSON, readline-based)
# ---------------------------------------------------------------------------


class TestNDJSONFraming:
    """Messages are NDJSON: one JSON object per line, terminated by newline."""

    @pytest.mark.asyncio
    async def test_ipc_client_sends_ndjson_line(self, tmp_path: Path):
        """IPCClient.request() sends a single JSON line terminated by newline."""
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "ndjson.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        received_data = bytearray()

        async def fake_server():
            loop = asyncio.get_event_loop()
            conn, _ = await loop.sock_accept(server_sock)
            try:
                while True:
                    chunk = await loop.sock_recv(conn, 4096)
                    if not chunk:
                        break
                    received_data.extend(chunk)
                    request = json.loads(chunk.decode().strip())
                    # Send a valid IPCResponseFrame
                    response = (
                        json.dumps(
                            {
                                "id": request["id"],
                                "done": True,
                                "payload": {"ok": True},
                                "engine_context": None,
                                "error": None,
                            }
                        )
                        + "\n"
                    )
                    await loop.sock_sendall(conn, response.encode())
                    break
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_server())
        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.request("http", {"method": "GET", "url": "http://example.com"})
            await client.close()
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        # Verify the sent data is valid NDJSON (one line, parseable JSON)
        lines = received_data.decode().strip().split("\n")
        assert len(lines) == 1, "Client should send exactly one NDJSON line per request"
        parsed = json.loads(lines[0])
        assert set(parsed) == {"id", "action", "payload"}
        assert parsed["action"] == "http"
        assert parsed["payload"] == {"method": "GET", "url": "http://example.com"}

    @pytest.mark.asyncio
    async def test_ndjson_messages_are_single_line(self, tmp_path: Path):
        """Each NDJSON message must not contain embedded newlines."""
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "singleline.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        received_data = bytearray()

        async def fake_server():
            loop = asyncio.get_event_loop()
            conn, _ = await loop.sock_accept(server_sock)
            try:
                chunk = await loop.sock_recv(conn, 4096)
                received_data.extend(chunk)
                request = json.loads(chunk.decode().strip())
                response = (
                    json.dumps(
                        {
                            "id": request["id"],
                            "done": True,
                            "payload": {"ok": True},
                            "engine_context": None,
                            "error": None,
                        }
                    )
                    + "\n"
                )
                await loop.sock_sendall(conn, response.encode())
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_server())
        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            # Send a request with content that might tempt multi-line
            await client.request(
                "file_io",
                {
                    "action_type": "write",
                    "path": "/tmp/test.txt",
                    "content": "line1\nline2\nline3",
                },
            )
            await client.close()
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        raw = received_data.decode().strip()
        # The entire message must be one line (newlines in content must be escaped)
        lines = raw.split("\n")
        assert len(lines) == 1, "NDJSON message with embedded newlines must escape them"
        parsed = json.loads(lines[0])
        assert set(parsed) == {"id", "action", "payload"}
        assert parsed["action"] == "file_io"
        assert parsed["payload"]["content"] == "line1\nline2\nline3"


# ---------------------------------------------------------------------------
# AC4: IPCClient.request() sends NDJSON, reads response with matching id
# ---------------------------------------------------------------------------


class TestIPCClientRequestResponseCorrelation:
    """IPCClient.request() must correlate responses by id."""

    @pytest.mark.asyncio
    async def test_ipc_client_importable(self):
        """IPCClient can be imported from runsight_core.isolation."""
        from runsight_core.isolation import IPCClient

        assert IPCClient is not None

    @pytest.mark.asyncio
    async def test_ipc_client_reads_env_var_for_socket_path(self):
        """IPCClient uses RUNSIGHT_IPC_SOCKET env var for socket path."""
        from runsight_core.isolation import IPCClient

        client = IPCClient(socket_path="/tmp/test_ipc.sock")
        assert client is not None

    @pytest.mark.asyncio
    async def test_request_returns_response_with_matching_id(self, tmp_path: Path):
        """IPCClient.request() returns the response whose id matches the request id."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "corr.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def http_handler(params: dict) -> dict:
            return {"status_code": 200, "body": "ok", "headers": {}}

        grant_token = _make_grant_token(block_id="corr")
        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
            result = await client.request("http", {"method": "GET", "url": "http://example.com"})

            assert isinstance(result, dict)
            assert result["status_code"] == 200
            assert result["body"] == "ok"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_request_includes_action_field(self, tmp_path: Path):
        """Each request sent by IPCClient includes an 'action' field."""
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "action.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        received_msg = {}

        async def fake_server():
            loop = asyncio.get_event_loop()
            conn, _ = await loop.sock_accept(server_sock)
            try:
                data = await loop.sock_recv(conn, 4096)
                received_msg.update(json.loads(data.decode().strip()))
                resp = (
                    json.dumps(
                        {
                            "id": received_msg.get("id", ""),
                            "done": True,
                            "payload": {"ok": True},
                            "engine_context": None,
                            "error": None,
                        }
                    )
                    + "\n"
                )
                await loop.sock_sendall(conn, resp.encode())
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_server())
        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.request("delegate", {"port": "output", "task": "run sub-task"})
            await client.close()
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        assert set(received_msg) == {"id", "action", "payload"}
        assert received_msg["action"] == "delegate"
        assert received_msg["payload"] == {"port": "output", "task": "run sub-task"}


# ---------------------------------------------------------------------------
# AC2: IPCServer dispatches: http, file_io, delegate, write_artifact
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
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
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
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
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
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
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
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
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
# AC6: RPC action allowlist
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
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
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
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
            result = await client.request("totally_fake_action", {"foo": "bar"})

            assert "error" in result
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# RUN-398: Grant token authentication + RPC allowlist contract
# ---------------------------------------------------------------------------


class TestRUN398GrantTokenAuthAndAllowlist:
    """Grant-token auth and allowlist-based action control for IPC server."""

    def test_rpc_allowlist_includes_llm_and_capability_actions(self):
        from runsight_core.isolation import ipc as ipc_module

        allowlist = getattr(ipc_module, "RPC_ALLOWLIST", None)
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

        sock_path = tmp_path / "run398-no-bypass.sock"
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
                    "id": "req-398-no-bypass-1",
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
        from runsight_core.isolation import ipc as ipc_module

        GrantToken = getattr(ipc_module, "GrantToken", None)
        assert GrantToken is not None
        grant = GrantToken(block_id="block-398")

        sock_path = tmp_path / "run398-unauth.sock"
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
                    "id": "req-398-unauth-1",
                    "action": "http",
                    "payload": {"method": "GET", "url": "https://example.com"},
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
        from runsight_core.isolation import ipc as ipc_module

        GrantToken = getattr(ipc_module, "GrantToken", None)
        assert GrantToken is not None
        grant = GrantToken(block_id="block-398")

        sock_path = tmp_path / "run398-consume.sock"
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
                    "id": "req-398-auth-1",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["http", "tool_call"],
                    "worker_version": "worker-398",
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
                    "id": "req-398-auth-2",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["http", "tool_call"],
                    "worker_version": "worker-398",
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
            assert "consumed" in (second_frame["error"] or "").lower()
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_expired_grant_token_is_rejected(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import ipc as ipc_module

        GrantToken = getattr(ipc_module, "GrantToken", None)
        assert GrantToken is not None
        grant = GrantToken(block_id="block-398", created_at=0.0, ttl_seconds=30.0)

        sock_path = tmp_path / "run398-expired.sock"
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
                    "id": "req-398-expired-1",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["http"],
                    "worker_version": "worker-398",
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
            assert "expired" in (frame["error"] or "").lower()
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


class TestRUN396CapabilityNegotiationProtocol:
    """RUN-396: dedicated capability handshake models and startup flow."""

    def test_capability_request_model_exists_with_dedicated_fields(self):
        from runsight_core.isolation import ipc as ipc_module

        CapabilityRequest = getattr(ipc_module, "CapabilityRequest", None)
        assert CapabilityRequest is not None

        assert set(CapabilityRequest.model_fields) == {
            "action",
            "id",
            "grant_token",
            "supported_actions",
            "worker_version",
        }
        request = CapabilityRequest(
            grant_token="grant-396",
            supported_actions=["llm_call", "tool_call", "http"],
            worker_version="worker-396",
        )
        assert request.action == "capability_negotiation"
        assert "payload" not in CapabilityRequest.model_fields

    def test_capability_response_model_exists_with_dedicated_fields(self):
        from runsight_core.isolation import ipc as ipc_module

        CapabilityResponse = getattr(ipc_module, "CapabilityResponse", None)
        assert CapabilityResponse is not None

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

        grant = _make_grant_token(block_id="run-396-handshake")
        sock_path = tmp_path / "run396-handshake.sock"
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
                    "id": "req-396-cap-1",
                    "action": "capability_negotiation",
                    "grant_token": grant.token,
                    "supported_actions": ["llm_call", "tool_call", "http"],
                    "worker_version": "worker-396",
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
            assert frame["id"] == "req-396-cap-1"
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

        grant = _make_grant_token(block_id="run-396-invalid")
        sock_path = tmp_path / "run396-invalid.sock"
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
                    "id": "req-396-cap-invalid",
                    "action": "capability_negotiation",
                    "grant_token": "wrong-token",
                    "supported_actions": ["llm_call"],
                    "worker_version": "worker-396",
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

        grant = _make_grant_token(block_id="run-396-no-shim")
        sock_path = tmp_path / "run396-no-shim.sock"
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
                    "id": "req-396-legacy-1",
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


class TestRUN396IPCClientConnectHandshake:
    """RUN-396: IPCClient.connect performs startup capability negotiation."""

    @pytest.mark.asyncio
    async def test_connect_sends_capability_request_and_returns_capability_response(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "run396-client-connect.sock"
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
                                "trace_id": "trace-396",
                                "run_id": "run-396",
                                "block_id": "block-396",
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


# ---------------------------------------------------------------------------
# AC5: Socket cleaned up on subprocess exit
# ---------------------------------------------------------------------------


class TestSocketCleanup:
    """Socket resources must be cleaned up properly."""

    @pytest.mark.asyncio
    async def test_server_shutdown_releases_socket(self, tmp_path: Path):
        """After IPCServer.shutdown(), the socket is no longer accepting connections."""
        from runsight_core.isolation import IPCServer

        sock_path = tmp_path / "cleanup.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        server = IPCServer(sock=server_sock, handlers={}, grant_token=_make_grant_token())
        server_task = asyncio.create_task(server.serve())

        await server.shutdown()
        server_task.cancel()

        # After shutdown, new connections should fail
        test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            with pytest.raises((ConnectionRefusedError, OSError)):
                test_sock.connect(str(sock_path))
        finally:
            test_sock.close()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_client_close_releases_resources(self, tmp_path: Path):
        """After IPCClient.close(), internal resources are released."""
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "client_close.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        async def accept_once():
            loop = asyncio.get_event_loop()
            conn, _ = await loop.sock_accept(server_sock)
            # Hold connection until closed
            try:
                await loop.sock_recv(conn, 4096)
            except Exception:
                pass
            finally:
                conn.close()

        accept_task = asyncio.create_task(accept_once())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.close()

            # After close, request should raise
            with pytest.raises(Exception):
                await client.request("http", {"method": "GET", "url": "http://x.com"})
        finally:
            accept_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC8: Socket drop causes block failure (no reconnection)
# ---------------------------------------------------------------------------


class TestSocketDropFailure:
    """When the socket drops, the client must fail — no reconnection attempts."""

    @pytest.mark.asyncio
    async def test_client_raises_on_server_disconnect(self, tmp_path: Path):
        """IPCClient raises an error when the server disconnects mid-session."""
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "drop.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        async def accept_then_close():
            loop = asyncio.get_event_loop()
            conn, _ = await loop.sock_accept(server_sock)
            # Accept connection then immediately close it (simulating crash)
            conn.close()

        accept_task = asyncio.create_task(accept_then_close())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()

            # Give the fake server time to accept and close
            await asyncio.sleep(0.05)

            # Request after server disconnect should fail
            with pytest.raises((ConnectionError, OSError, EOFError)):
                await client.request("http", {"method": "GET", "url": "http://example.com"})
        finally:
            accept_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_no_automatic_reconnection(self, tmp_path: Path):
        """After a socket drop, IPCClient does NOT attempt to reconnect."""
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "no_reconn.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        connection_count = 0

        async def counting_server():
            nonlocal connection_count
            loop = asyncio.get_event_loop()
            while True:
                try:
                    conn, _ = await loop.sock_accept(server_sock)
                    connection_count += 1
                    conn.close()  # Immediately drop
                except Exception:
                    break

        server_task = asyncio.create_task(counting_server())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await asyncio.sleep(0.05)

            # First request fails due to drop
            try:
                await client.request("http", {"method": "GET", "url": "http://example.com"})
            except Exception:
                pass

            # Second request should also fail (no reconnect)
            try:
                await client.request("http", {"method": "GET", "url": "http://example.com"})
            except Exception:
                pass

            await asyncio.sleep(0.05)

            # Only one connection should have been made (the initial one)
            assert connection_count == 1, (
                f"Expected exactly 1 connection (no reconnect), got {connection_count}"
            )
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC7: write_artifact writes to engine-side ArtifactStore, returns ref
# ---------------------------------------------------------------------------


class TestWriteArtifactReturnsRef:
    """write_artifact action must store content and return a ref string."""

    @pytest.mark.asyncio
    async def test_write_artifact_returns_ref_string(self, tmp_path: Path):
        """write_artifact handler returns a dict containing 'ref'."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "artifact_ref.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        stored_artifacts: dict[str, dict] = {}

        async def write_artifact_handler(params: dict) -> dict:
            key = params["key"]
            stored_artifacts[key] = {
                "content": params["content"],
                "metadata": params.get("metadata", {}),
            }
            return {"ref": f"artifact://{key}"}

        grant_token = _make_grant_token(block_id="artifact-ref")
        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
            result = await client.request(
                "write_artifact",
                {
                    "key": "report",
                    "content": "# Summary\nAll good.",
                    "metadata": {"format": "markdown"},
                },
            )

            assert "ref" in result
            assert isinstance(result["ref"], str)
            assert "report" in result["ref"]
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_write_artifact_handler_receives_key_content_metadata(self, tmp_path: Path):
        """write_artifact handler receives key, content, and metadata params."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "artifact_params.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        received_params: dict = {}

        async def write_artifact_handler(params: dict) -> dict:
            received_params.update(params)
            return {"ref": "artifact://test-key"}

        grant_token = _make_grant_token(block_id="artifact-params")
        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
            await client.request(
                "write_artifact",
                {
                    "key": "test-key",
                    "content": "binary data here",
                    "metadata": {"type": "binary"},
                },
            )

            assert received_params["key"] == "test-key"
            assert received_params["content"] == "binary data here"
            assert received_params["metadata"] == {"type": "binary"}
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC9: Integration test — HTTP tool round-trip through IPC
# ---------------------------------------------------------------------------


class TestHTTPRoundTrip:
    """End-to-end: client sends http action, server dispatches, client gets response."""

    @pytest.mark.asyncio
    async def test_http_get_round_trip(self, tmp_path: Path):
        """Full round-trip: http GET request -> handler -> response with status/body/headers."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "http_rt.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def http_handler(params: dict) -> dict:
            assert params["method"] == "GET"
            assert params["url"] == "https://api.example.com/data"
            return {
                "status_code": 200,
                "body": '{"items": [1, 2, 3]}',
                "headers": {"content-type": "application/json"},
            }

        grant_token = _make_grant_token(block_id="http-get")
        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
            result = await client.request(
                "http",
                {
                    "method": "GET",
                    "url": "https://api.example.com/data",
                    "headers": {"Authorization": "Bearer tok"},
                    "body": None,
                },
            )

            assert result["status_code"] == 200
            assert result["body"] == '{"items": [1, 2, 3]}'
            assert result["headers"]["content-type"] == "application/json"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_http_post_round_trip(self, tmp_path: Path):
        """Full round-trip: http POST with body -> handler -> 201 response."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "http_post_rt.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def http_handler(params: dict) -> dict:
            assert params["method"] == "POST"
            assert params["body"] == '{"name": "test"}'
            return {
                "status_code": 201,
                "body": '{"id": "abc-123"}',
                "headers": {},
            }

        grant_token = _make_grant_token(block_id="http-post")
        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
            result = await client.request(
                "http",
                {
                    "method": "POST",
                    "url": "https://api.example.com/items",
                    "headers": {"content-type": "application/json"},
                    "body": '{"name": "test"}',
                },
            )

            assert result["status_code"] == 201
            body = json.loads(result["body"])
            assert body["id"] == "abc-123"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC10: Integration test — write_artifact round-trip through IPC
# ---------------------------------------------------------------------------


class TestWriteArtifactRoundTrip:
    """End-to-end: client sends write_artifact, server stores it, client gets ref."""

    @pytest.mark.asyncio
    async def test_write_artifact_full_round_trip(self, tmp_path: Path):
        """Full round-trip: write_artifact -> handler stores content -> ref returned."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "wa_rt.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        artifact_store: dict[str, dict] = {}

        async def write_artifact_handler(params: dict) -> dict:
            key = params["key"]
            artifact_store[key] = {
                "content": params["content"],
                "metadata": params.get("metadata", {}),
            }
            return {"ref": f"artifact://block-x/{key}"}

        grant_token = _make_grant_token(block_id="wa-rt")
        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)
            result = await client.request(
                "write_artifact",
                {
                    "key": "analysis-output",
                    "content": "The analysis shows growth of 15%.",
                    "metadata": {"category": "report", "format": "text"},
                },
            )

            # Client gets a ref back
            assert result["ref"] == "artifact://block-x/analysis-output"

            # Server-side store has the content
            assert "analysis-output" in artifact_store
            assert artifact_store["analysis-output"]["content"] == (
                "The analysis shows growth of 15%."
            )
            assert artifact_store["analysis-output"]["metadata"]["category"] == "report"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_multiple_artifacts_stored_independently(self, tmp_path: Path):
        """Multiple write_artifact calls store independently and return unique refs."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "wa_multi.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        artifact_store: dict[str, dict] = {}

        async def write_artifact_handler(params: dict) -> dict:
            key = params["key"]
            artifact_store[key] = {"content": params["content"]}
            return {"ref": f"artifact://{key}"}

        grant_token = _make_grant_token(block_id="wa-multi")
        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await _authenticate_client_with_grant_token(client, grant_token)

            ref1 = await client.request(
                "write_artifact", {"key": "artifact-a", "content": "aaa", "metadata": {}}
            )
            ref2 = await client.request(
                "write_artifact", {"key": "artifact-b", "content": "bbb", "metadata": {}}
            )

            assert ref1["ref"] != ref2["ref"]
            assert len(artifact_store) == 2
            assert artifact_store["artifact-a"]["content"] == "aaa"
            assert artifact_store["artifact-b"]["content"] == "bbb"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# RUN-392: IPCFrame protocol + NDJSON streaming
# ---------------------------------------------------------------------------


class TestRUN392IPCFrameModels:
    """Typed request/response frame models define the IPC contract."""

    def test_ipc_request_has_id_action_payload_and_forbids_engine_context(self):
        from pydantic import ValidationError
        from runsight_core.isolation import ipc as ipc_module

        IPCRequest = getattr(ipc_module, "IPCRequest", None)
        assert IPCRequest is not None, "IPCRequest model must exist"

        assert set(IPCRequest.model_fields) == {"id", "action", "payload"}

        req = IPCRequest(id="req-1", action="http", payload={"url": "https://example.com"})
        assert req.id == "req-1"
        assert req.action == "http"
        assert req.payload == {"url": "https://example.com"}

        with pytest.raises(ValidationError):
            IPCRequest(
                id="req-2",
                action="http",
                payload={"url": "https://example.com"},
                engine_context={"trace_id": "forbidden"},
            )

    def test_ipc_response_frame_has_complete_contract(self):
        from runsight_core.isolation import ipc as ipc_module

        IPCResponseFrame = getattr(ipc_module, "IPCResponseFrame", None)
        assert IPCResponseFrame is not None, "IPCResponseFrame model must exist"

        assert set(IPCResponseFrame.model_fields) == {
            "id",
            "done",
            "payload",
            "engine_context",
            "error",
        }

        frame = IPCResponseFrame(
            id="req-1",
            done=False,
            payload={"chunk": "A"},
            engine_context={"trace_id": "t-1"},
            error=None,
        )
        assert frame.done is False
        assert frame.payload == {"chunk": "A"}
        assert frame.engine_context == {"trace_id": "t-1"}
        assert frame.error is None


class TestRUN392ServerStreamingFrames:
    """IPCServer must emit response frames for both simple and streaming handlers."""

    @pytest.mark.asyncio
    async def test_simple_handler_returns_single_done_frame_with_engine_context(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class TraceInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["trace_id"] = "trace-simple-1"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(TraceInterceptor())

        sock_path = tmp_path / "run392-simple.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def simple_handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "echo": payload.get("value")}

        grant_token = _make_grant_token(block_id="run392-simple")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-simple-1",
                    "action": "simple",
                    "payload": {"value": 123},
                },
            )
            assert len(frames) == 1
            assert frames[0]["id"] == "req-simple-1"
            assert frames[0]["done"] is True
            assert frames[0]["payload"] == {"status": "ok", "echo": 123}
            assert frames[0]["engine_context"] == {"trace_id": "trace-simple-1"}
            assert frames[0]["error"] is None
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_stream_handler_returns_three_non_final_frames_and_one_final(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class TraceInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["trace_id"] = "trace-stream-1"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(TraceInterceptor())

        sock_path = tmp_path / "run392-stream.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def stream_handler(payload: dict[str, Any]):
            assert payload == {"topic": "demo"}
            yield {"chunk": 1}
            yield {"chunk": 2}
            yield {"chunk": 3}

        grant_token = _make_grant_token(block_id="run392-stream")
        server = IPCServer(
            sock=server_sock,
            handlers={"stream": stream_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-stream-1",
                    "action": "stream",
                    "payload": {"topic": "demo"},
                },
                max_frames=8,
            )
            assert len(frames) == 4
            assert [frame["done"] for frame in frames] == [False, False, False, True]
            assert [frame["payload"] for frame in frames[:-1]] == [
                {"chunk": 1},
                {"chunk": 2},
                {"chunk": 3},
            ]
            assert frames[-1]["payload"] is None
            assert all(
                frame["engine_context"] == {"trace_id": "trace-stream-1"} for frame in frames
            )
            assert all(frame["error"] is None for frame in frames)
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


class TestRUN392IPCClientFrameConsumption:
    """IPCClient must consume streamed frames through request/request_stream APIs."""

    def test_request_signature_has_no_legacy_var_keyword_params(self):
        """Public API is frame-first: request(action, payload) without flattened kwargs."""
        import inspect

        from runsight_core.isolation import IPCClient

        params = inspect.signature(IPCClient.request).parameters.values()
        assert all(param.kind is not inspect.Parameter.VAR_KEYWORD for param in params)

    @pytest.mark.asyncio
    async def test_request_returns_payload_from_final_done_frame(self, tmp_path: Path):
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "run392-client-final.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        async def fake_stream_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            try:
                _ = await loop.sock_recv(conn, 4096)
                for frame in [
                    {
                        "id": "ignored",
                        "done": False,
                        "payload": {"chunk": 1},
                        "engine_context": {"trace_id": "c1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": True,
                        "payload": {"final": "result"},
                        "engine_context": {"trace_id": "c1"},
                        "error": None,
                    },
                ]:
                    await loop.sock_sendall(conn, (json.dumps(frame) + "\n").encode())
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_stream_server())
        client = IPCClient(socket_path=str(sock_path))
        try:
            await client.connect()
            result = await client.request("http", {"url": "https://example.com"})
            assert result == {"final": "result"}
        finally:
            await client.close()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# RUN-393: InterceptorRegistry chain-of-responsibility for IPC messages
# ---------------------------------------------------------------------------


class TestRUN393InterceptorRegistryContract:
    """Interceptor registry applies request/response/stream hooks in deterministic order."""

    def test_interceptor_registry_and_protocol_symbols_exist(self):
        from runsight_core.isolation import ipc as ipc_module

        assert getattr(ipc_module, "IPCInterceptor", None) is not None
        assert getattr(ipc_module, "InterceptorRegistry", None) is not None

    @pytest.mark.asyncio
    async def test_on_request_starts_with_fresh_empty_context(self):
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        observed: list[dict[str, Any]] = []

        class BudgetLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                observed.append(dict(engine_context))
                assert action == "http"
                assert payload == {"url": "https://example.com"}
                engine_context["budget_remaining_usd"] = 12.5
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        class ObserverLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                observed.append(dict(engine_context))
                engine_context["trace_id"] = "trace-393"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(BudgetLikeInterceptor())
        registry.register(ObserverLikeInterceptor())

        context = await registry.run_on_request("http", {"url": "https://example.com"}, {})
        assert observed[0] == {}
        assert observed[1] == {"budget_remaining_usd": 12.5}
        assert context == {
            "budget_remaining_usd": 12.5,
            "trace_id": "trace-393",
        }

    @pytest.mark.asyncio
    async def test_request_forward_response_reverse_and_chunk_forward_order(self):
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        call_order: list[str] = []

        class BudgetLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("budget.request")
                engine_context["budget"] = "set"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("budget.response")
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                call_order.append("budget.chunk")
                return engine_context

        class ObserverLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("observer.request")
                engine_context["observer"] = "set"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("observer.response")
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                call_order.append("observer.chunk")
                return engine_context

        registry.register(BudgetLikeInterceptor())
        registry.register(ObserverLikeInterceptor())

        context: dict[str, Any] = {}
        context = await registry.run_on_request("delegate", {"task": "do work"}, context)
        context = await registry.run_on_stream_chunk("delegate", {"chunk": 1}, context)
        context = await registry.run_on_response("delegate", {"final": "ok"}, context)

        assert call_order == [
            "budget.request",
            "observer.request",
            "budget.chunk",
            "observer.chunk",
            "observer.response",
            "budget.response",
        ]
        assert context == {"budget": "set", "observer": "set"}

    @pytest.mark.asyncio
    async def test_empty_registry_is_passthrough(self):
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        ctx: dict[str, Any] = {}
        after_request = await registry.run_on_request("http", {"url": "x"}, ctx)
        after_chunk = await registry.run_on_stream_chunk("http", {"chunk": "a"}, after_request)
        after_response = await registry.run_on_response("http", {"status": 200}, after_chunk)
        assert after_response == {}


class TestRUN393IPCServerRegistryIntegration:
    """IPCServer should run registry hooks around handler execution for all frame types."""

    @pytest.mark.asyncio
    async def test_simple_handler_runs_registry_and_emits_final_engine_context(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class TestInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                if action == "capability_negotiation":
                    return engine_context
                assert engine_context == {}
                engine_context["request_seen"] = action
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                if action == "capability_negotiation":
                    return engine_context
                engine_context["response_status"] = payload["status"]
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(TestInterceptor())

        sock_path = tmp_path / "run393-simple.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        handler_called = False

        async def simple_handler(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_called
            handler_called = True
            return {"status": "ok", "echo": payload["value"]}

        grant_token = _make_grant_token(block_id="run393-simple")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-simple-1",
                    "action": "simple",
                    "payload": {"value": 7},
                },
            )
            assert handler_called is True
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] == {"status": "ok", "echo": 7}
            assert frames[0]["engine_context"] == {
                "request_seen": "simple",
                "response_status": "ok",
            }
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_private_engine_context_interceptor_does_not_mutate_context_without_registry_register(
        self, tmp_path: Path
    ):
        """Only explicit InterceptorRegistry.register() may mutate engine_context."""
        from runsight_core.isolation import IPCServer

        sock_path = tmp_path / "run393-no-shim.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def simple_handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "echo": payload.get("value")}

        grant_token = _make_grant_token(block_id="run393-no-shim")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
            grant_token=grant_token,
        )
        setattr(
            server,
            "_engine_context_interceptor",
            lambda *_args, **_kwargs: {"trace_id": "legacy-shim"},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-no-shim-1",
                    "action": "simple",
                    "payload": {"value": 42},
                },
            )
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] == {"status": "ok", "echo": 42}
            assert frames[0]["engine_context"] == {}
            assert "trace_id" not in frames[0]["engine_context"]
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_stream_handler_runs_chunk_hook_per_chunk(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        chunk_indices: list[int] = []

        class TestInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["chunk_count"] = 0
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["response_seen"] = True
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                chunk_indices.append(chunk["index"])
                engine_context["chunk_count"] += 1
                return engine_context

        registry.register(TestInterceptor())

        sock_path = tmp_path / "run393-stream.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def stream_handler(payload: dict[str, Any]):
            yield {"index": 1, "value": "A"}
            yield {"index": 2, "value": "B"}
            yield {"index": 3, "value": "C"}

        grant_token = _make_grant_token(block_id="run393-stream")
        server = IPCServer(
            sock=server_sock,
            handlers={"stream": stream_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-stream-1",
                    "action": "stream",
                    "payload": {"topic": "demo"},
                },
                max_frames=8,
            )
            assert chunk_indices == [1, 2, 3]
            assert [frame["done"] for frame in frames] == [False, False, False, True]
            assert frames[-1]["engine_context"] == {
                "chunk_count": 3,
                "response_seen": True,
            }
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_budget_killed_in_on_request_short_circuits_handler(self, tmp_path: Path):
        from runsight_core.budget_enforcement import BudgetKilledException
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class KillSwitchInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                if action == "capability_negotiation":
                    return engine_context
                raise BudgetKilledException(
                    scope="workflow",
                    block_id=None,
                    limit_kind="cost_usd",
                    limit_value=10.0,
                    actual_value=12.0,
                )

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(KillSwitchInterceptor())

        sock_path = tmp_path / "run393-killed.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        handler_called = False

        async def should_not_run(_payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_called
            handler_called = True
            return {"status": "unexpected"}

        grant_token = _make_grant_token(block_id="run393-killed")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": should_not_run},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-kill-1",
                    "action": "simple",
                    "payload": {"value": "blocked"},
                },
            )
            assert handler_called is False
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] is None
            assert frames[0]["error"] is not None
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_subprocess_sent_engine_context_is_rejected_and_never_reaches_registry(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import ipc as ipc_module

        InterceptorRegistry = getattr(ipc_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        on_request_calls = 0

        class SpyInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                nonlocal on_request_calls
                on_request_calls += 1
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(SpyInterceptor())

        sock_path = tmp_path / "run393-tamper.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def simple_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok"}

        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
            registry=registry,
            grant_token=_make_grant_token(block_id="run393-tamper"),
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
                {
                    "id": "req-393-tamper-1",
                    "action": "simple",
                    "payload": {"value": 1},
                    "engine_context": {"subprocess_injected": True},
                },
            )
            assert on_request_calls == 0
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] is None
            assert "invalid request frame" in (frames[0]["error"] or "")
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_request_stream_yields_only_non_final_payloads(self, tmp_path: Path):
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "run392-client-stream.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        async def fake_stream_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            try:
                _ = await loop.sock_recv(conn, 4096)
                for frame in [
                    {
                        "id": "ignored",
                        "done": False,
                        "payload": {"chunk": "A"},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": False,
                        "payload": {"chunk": "B"},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": False,
                        "payload": {"chunk": "C"},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": True,
                        "payload": {"final": True},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                ]:
                    await loop.sock_sendall(conn, (json.dumps(frame) + "\n").encode())
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_stream_server())
        client = IPCClient(socket_path=str(sock_path))
        try:
            await client.connect()
            chunks = []
            async for payload in client.request_stream("delegate", {"task": "demo"}):
                chunks.append(payload)
            assert chunks == [{"chunk": "A"}, {"chunk": "B"}, {"chunk": "C"}]
        finally:
            await client.close()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)
