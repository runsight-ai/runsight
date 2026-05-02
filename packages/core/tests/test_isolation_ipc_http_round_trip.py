"""IPC HTTP round-trip behavior."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path

import pytest
from isolation_ipc_helpers import (
    _connect_client_with_grant_token,
    _make_grant_token,
)

pytestmark = pytest.mark.real_subprocess_isolation

# ---------------------------------------------------------------------------
# write_artifact writes to engine-side ArtifactStore and returns ref
# ---------------------------------------------------------------------------


class TestHTTPRoundTrip:
    """Integration: client sends http action, server dispatches, client gets response."""

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
            assert params["url"] == "https://api.fixture.test/data"
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
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request(
                "http",
                {
                    "method": "GET",
                    "url": "https://api.fixture.test/data",
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
            await _connect_client_with_grant_token(client, grant_token)
            result = await client.request(
                "http",
                {
                    "method": "POST",
                    "url": "https://api.fixture.test/items",
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
# Integration test — write_artifact round-trip through IPC
# ---------------------------------------------------------------------------
