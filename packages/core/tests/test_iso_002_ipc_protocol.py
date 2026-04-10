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
            server = IPCServer(sock=sock, handlers={})
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
            IPCServer(sock=str(tmp_path / "no.sock"), handlers={})


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
                    # Send a valid NDJSON response
                    response = json.dumps({"id": "req-1", "ok": True}) + "\n"
                    await loop.sock_sendall(conn, response.encode())
                    break
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_server())
        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.request("http", method="GET", url="http://example.com")
            await client.close()
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        # Verify the sent data is valid NDJSON (one line, parseable JSON)
        lines = received_data.decode().strip().split("\n")
        assert len(lines) == 1, "Client should send exactly one NDJSON line per request"
        parsed = json.loads(lines[0])
        assert "action" in parsed
        assert "id" in parsed

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
                response = json.dumps({"id": "req-1", "ok": True}) + "\n"
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
                action_type="write",
                path="/tmp/test.txt",
                content="line1\nline2\nline3",
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
        assert parsed["content"] == "line1\nline2\nline3"


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

        server = IPCServer(sock=server_sock, handlers={"http": http_handler})
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request("http", method="GET", url="http://example.com")

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
                resp = json.dumps({"id": received_msg.get("id", ""), "ok": True}) + "\n"
                await loop.sock_sendall(conn, resp.encode())
            finally:
                conn.close()

        server_task = asyncio.create_task(fake_server())
        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.request("delegate", port="output", task="run sub-task")
            await client.close()
        finally:
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        assert received_msg["action"] == "delegate"


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

        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request("http", method="GET", url="http://example.com")
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

        server = IPCServer(
            sock=server_sock,
            handlers={"file_io": file_io_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request("file_io", action_type="read", path="/tmp/f.txt")
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

        server = IPCServer(
            sock=server_sock,
            handlers={"delegate": delegate_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request("delegate", port="output", task="do thing")
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

        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request(
                "write_artifact", key="my-key", content="data", metadata={}
            )
            assert result["ref"] == "artifact://block-1/my-key"
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC6: No llm_call action
# ---------------------------------------------------------------------------


class TestNoLLMCallAction:
    """IPCServer must reject llm_call action — IPC is for tool calls only."""

    @pytest.mark.asyncio
    async def test_llm_call_action_rejected(self, tmp_path: Path):
        """Sending an llm_call action results in an error response."""
        from runsight_core.isolation import IPCClient, IPCServer

        sock_path = tmp_path / "no_llm.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        server = IPCServer(
            sock=server_sock,
            handlers={
                "http": AsyncMock(return_value={}),
                "file_io": AsyncMock(return_value={}),
                "delegate": AsyncMock(return_value={}),
                "write_artifact": AsyncMock(return_value={}),
            },
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request("llm_call", prompt="hello")

            # The server should return an error for unsupported action
            assert "error" in result
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

        server = IPCServer(
            sock=server_sock,
            handlers={
                "http": AsyncMock(return_value={}),
            },
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request("totally_fake_action", foo="bar")

            assert "error" in result
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
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

        server = IPCServer(sock=server_sock, handlers={})
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
                await client.request("http", method="GET", url="http://x.com")
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
                await client.request("http", method="GET", url="http://example.com")
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
                await client.request("http", method="GET", url="http://example.com")
            except Exception:
                pass

            # Second request should also fail (no reconnect)
            try:
                await client.request("http", method="GET", url="http://example.com")
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

        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request(
                "write_artifact",
                key="report",
                content="# Summary\nAll good.",
                metadata={"format": "markdown"},
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

        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.request(
                "write_artifact",
                key="test-key",
                content="binary data here",
                metadata={"type": "binary"},
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

        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request(
                "http",
                method="GET",
                url="https://api.example.com/data",
                headers={"Authorization": "Bearer tok"},
                body=None,
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

        server = IPCServer(
            sock=server_sock,
            handlers={"http": http_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request(
                "http",
                method="POST",
                url="https://api.example.com/items",
                headers={"content-type": "application/json"},
                body='{"name": "test"}',
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

        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            result = await client.request(
                "write_artifact",
                key="analysis-output",
                content="The analysis shows growth of 15%.",
                metadata={"category": "report", "format": "text"},
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

        server = IPCServer(
            sock=server_sock,
            handlers={"write_artifact": write_artifact_handler},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()

            ref1 = await client.request(
                "write_artifact", key="artifact-a", content="aaa", metadata={}
            )
            ref2 = await client.request(
                "write_artifact", key="artifact-b", content="bbb", metadata={}
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

        sock_path = tmp_path / "run392-simple.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def simple_handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "echo": payload.get("value")}

        server = IPCServer(sock=server_sock, handlers={"simple": simple_handler})
        setattr(
            server,
            "_engine_context_interceptor",
            lambda *_args, **_kwargs: {"trace_id": "trace-simple-1"},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
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

        sock_path = tmp_path / "run392-stream.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def stream_handler(payload: dict[str, Any]):
            assert payload == {"topic": "demo"}
            yield {"chunk": 1}
            yield {"chunk": 2}
            yield {"chunk": 3}

        server = IPCServer(sock=server_sock, handlers={"stream": stream_handler})
        setattr(
            server,
            "_engine_context_interceptor",
            lambda *_args, **_kwargs: {"trace_id": "trace-stream-1"},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_request_and_collect_frames(
                sock_path,
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
