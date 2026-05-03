"""IPC write_artifact round-trip behavior."""

from __future__ import annotations

import asyncio
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
