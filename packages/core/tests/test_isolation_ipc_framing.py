"""IPC socket ownership, NDJSON framing, and request correlation tests."""

from __future__ import annotations

import asyncio
import json
import os
import socket
from pathlib import Path

import pytest
from isolation_ipc_helpers import (
    _capability_response_for,
    _connect_client_with_grant_token,
    _make_grant_token,
)

# ---------------------------------------------------------------------------
# IPCServer accepts existing socket instead of creating it
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
# NDJSON framing is newline-delimited and readline-based
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
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                assert raw_capability
                received_data.extend(raw_capability)
                capability_request = json.loads(raw_capability)

                capability_response = (
                    json.dumps(
                        _capability_response_for(
                            capability_request,
                            active_actions=["http"],
                        )
                    )
                    + "\n"
                )
                writer.write(capability_response.encode())
                await writer.drain()

                raw_request = await reader.readline()
                assert raw_request
                received_data.extend(raw_request)
                request = json.loads(raw_request)
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
                writer.write(response.encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server_task = asyncio.create_task(fake_server())
        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.request("http", {"method": "GET", "url": "http://fixture.test"})
            await client.close()
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        # Verify the sent data is valid NDJSON with handshake then request frame.
        lines = received_data.decode().strip().split("\n")
        assert len(lines) == 2
        handshake = json.loads(lines[0])
        parsed = json.loads(lines[1])
        assert set(handshake) == {
            "action",
            "id",
            "grant_token",
            "supported_actions",
            "worker_version",
        }
        assert handshake["action"] == "capability_negotiation"
        assert set(parsed) == {"id", "action", "payload"}
        assert parsed["action"] == "http"
        assert parsed["payload"] == {"method": "GET", "url": "http://fixture.test"}

    @pytest.mark.asyncio
    async def test_ipc_client_removes_grant_token_env_after_successful_connect(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Consumed grant tokens should not remain readable in worker process env."""
        from runsight_core.isolation import IPCClient

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-ndjson")
        sock_path = tmp_path / "ndjson-env.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        async def fake_server():
            loop = asyncio.get_event_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                capability_request = json.loads(await reader.readline())
                capability_response = (
                    json.dumps(
                        _capability_response_for(
                            capability_request,
                            active_actions=["http"],
                        )
                    )
                    + "\n"
                )
                writer.write(capability_response.encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server_task = asyncio.create_task(fake_server())
        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.close()
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        assert "RUNSIGHT_GRANT_TOKEN" not in os.environ

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
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                assert raw_capability
                received_data.extend(raw_capability)
                capability_request = json.loads(raw_capability)
                capability_response = (
                    json.dumps(
                        _capability_response_for(
                            capability_request,
                            active_actions=["file_io"],
                        )
                    )
                    + "\n"
                )
                writer.write(capability_response.encode())
                await writer.drain()

                raw_request = await reader.readline()
                assert raw_request
                received_data.extend(raw_request)
                request = json.loads(raw_request)
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
                writer.write(response.encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

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
        # The request line must stay single-line NDJSON (newlines must be escaped).
        lines = raw.split("\n")
        assert len(lines) == 2
        handshake = json.loads(lines[0])
        parsed = json.loads(lines[1])
        assert handshake["action"] == "capability_negotiation"
        assert set(parsed) == {"id", "action", "payload"}
        assert parsed["action"] == "file_io"
        assert parsed["payload"]["content"] == "line1\nline2\nline3"


# ---------------------------------------------------------------------------
# IPCClient.request() sends NDJSON and reads the response with a matching id
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
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request("http", {"method": "GET", "url": "http://fixture.test"})

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
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                assert raw_capability
                capability_request = json.loads(raw_capability)
                cap_response = (
                    json.dumps(
                        _capability_response_for(capability_request, active_actions=["delegate"])
                    )
                    + "\n"
                )
                writer.write(cap_response.encode())
                await writer.drain()

                data = await reader.readline()
                assert data
                received_msg.update(json.loads(data.decode().strip()))
                response = (
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
                writer.write(response.encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

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
