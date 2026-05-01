"""IPC artifact and HTTP round-trip tests."""

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

# ---------------------------------------------------------------------------
# write_artifact writes to engine-side ArtifactStore and returns ref
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
            await _connect_client_with_grant_token(client, grant_token)
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
            await _connect_client_with_grant_token(client, grant_token)
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
# Integration test — HTTP tool round-trip through IPC
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


class TestWriteArtifactRoundTrip:
    """Integration: client sends write_artifact, server stores it, client gets ref."""

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
            await _connect_client_with_grant_token(client, grant_token)
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
            await _connect_client_with_grant_token(client, grant_token)

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
