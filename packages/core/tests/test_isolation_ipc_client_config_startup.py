"""IPC client construction from transport config."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.real_subprocess_isolation


def _unix_config_payload(socket_path: str) -> dict[str, Any]:
    return {
        "version": 1,
        "transport": "unix_socket",
        "grant_token": "config-owned-token",
        "heartbeat_interval_ms": 5000,
        "unix_socket": {"path": socket_path},
    }


def _accepted(capability_response: object) -> bool:
    if isinstance(capability_response, dict):
        return bool(capability_response["accepted"])
    return bool(capability_response.accepted)


def _error(capability_response: object) -> str | None:
    if isinstance(capability_response, dict):
        return capability_response.get("error")
    return capability_response.error


class TestIPCClientFactoryFromConfig:
    @pytest.mark.asyncio
    async def test_from_config_uses_unix_socket_path_and_grant_token_from_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runsight_core.isolation import IPCClient, IPCClientConfig

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "legacy-env-token")

        sock_path = tmp_path / "config-client.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        observed_first_frame: dict[str, Any] = {}

        async def fake_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=0.5)
                assert raw
                observed_first_frame.update(json.loads(raw))
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": observed_first_frame.get("id", ""),
                                "done": True,
                                "accepted": True,
                                "active_actions": ["tool_call"],
                                "engine_context": {},
                                "error": None,
                            }
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        config = IPCClientConfig.model_validate(_unix_config_payload(str(sock_path)))
        server_task = asyncio.create_task(fake_server())
        client = IPCClient.from_config(config)

        try:
            capability_response = await client.connect()

            assert observed_first_frame["action"] == "capability_negotiation"
            assert observed_first_frame["grant_token"] == "config-owned-token"
            assert observed_first_frame["grant_token"] != "legacy-env-token"
            assert _accepted(capability_response) is True
            assert _error(capability_response) is None
        finally:
            await client.close()
            await server_task
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_from_config_surfaces_rejected_capability_response_for_bad_config_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from runsight_core.isolation import IPCClient, IPCClientConfig

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "legacy-env-token")

        sock_path = tmp_path / "config-client-rejected.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        observed_first_frame: dict[str, Any] = {}

        async def fake_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=0.5)
                assert raw
                observed_first_frame.update(json.loads(raw))
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": observed_first_frame.get("id", ""),
                                "done": True,
                                "accepted": False,
                                "active_actions": [],
                                "engine_context": {},
                                "error": "grant token rejected",
                            }
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        payload = _unix_config_payload(str(sock_path))
        payload["grant_token"] = "bad-config-token"
        config = IPCClientConfig.model_validate(payload)
        server_task = asyncio.create_task(fake_server())
        client = IPCClient.from_config(config)

        try:
            capability_response = await client.connect()

            assert observed_first_frame["action"] == "capability_negotiation"
            assert observed_first_frame["grant_token"] == "bad-config-token"
            assert observed_first_frame["grant_token"] != "legacy-env-token"
            assert _accepted(capability_response) is False
            assert _error(capability_response) == "grant token rejected"
        finally:
            await client.close()
            await server_task
            server_sock.close()
            sock_path.unlink(missing_ok=True)
