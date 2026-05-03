"""IPC socket cleanup and disconnect behavior tests."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path

import pytest
from isolation_ipc_helpers import (
    _capability_response_for,
    _make_grant_token,
)

pytestmark = pytest.mark.real_subprocess_isolation

# ---------------------------------------------------------------------------
# Socket cleaned up on subprocess exit
# ---------------------------------------------------------------------------


class TestSocketCleanup:
    """Socket resources must be cleaned up properly."""

    def test_server_requires_prebound_socket_object(self, tmp_path: Path):
        """IPCServer owns serving, while the caller owns creating/binding the socket."""
        from runsight_core.isolation import IPCServer

        with pytest.raises(TypeError, match="socket.socket"):
            IPCServer(
                sock=str(tmp_path / "not-bound.sock"),
                handlers={},
                grant_token=_make_grant_token(),
            )

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
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                assert raw_capability
                capability_request = json.loads(raw_capability)
                capability_response = (
                    json.dumps(
                        _capability_response_for(capability_request, active_actions=["http"])
                    )
                    + "\n"
                )
                writer.write(capability_response.encode())
                await writer.drain()
                await asyncio.wait_for(reader.readline(), timeout=0.2)
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        accept_task = asyncio.create_task(accept_once())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await client.close()

            # After close, request should raise
            with pytest.raises(Exception):
                await client.request("http", {"method": "GET", "url": "http://fixture.test"})
        finally:
            accept_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Socket drop causes block failure with no reconnection
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
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                assert raw_capability
                capability_request = json.loads(raw_capability)
                capability_response = (
                    json.dumps(
                        _capability_response_for(capability_request, active_actions=["http"])
                    )
                    + "\n"
                )
                writer.write(capability_response.encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        accept_task = asyncio.create_task(accept_then_close())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()

            # Give the fake server time to accept and close
            await asyncio.sleep(0.05)

            # Request after server disconnect should fail
            with pytest.raises((ConnectionError, OSError, EOFError)):
                await client.request("http", {"method": "GET", "url": "http://fixture.test"})
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
            loop = asyncio.get_running_loop()
            while True:
                try:
                    conn, _ = await loop.sock_accept(server_sock)
                    connection_count += 1
                    reader, writer = await asyncio.open_connection(sock=conn)
                    if connection_count == 1:
                        raw_capability = await reader.readline()
                        if raw_capability:
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
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    break

        server_task = asyncio.create_task(counting_server())

        try:
            client = IPCClient(socket_path=str(sock_path))
            await client.connect()
            await asyncio.sleep(0.05)

            # First request fails due to drop
            try:
                await client.request("http", {"method": "GET", "url": "http://fixture.test"})
            except Exception:
                pass

            # Second request should also fail (no reconnect)
            try:
                await client.request("http", {"method": "GET", "url": "http://fixture.test"})
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
