"""Transport-neutral IPC client configuration behavior."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError


def _encoded_config(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.b64encode(raw).decode("ascii")


def _unix_config_payload(socket_path: str = "/tmp/runsight-worker.sock") -> dict[str, Any]:
    return {
        "version": 1,
        "transport": "unix_socket",
        "grant_token": "config-grant-token",
        "heartbeat_interval_ms": 5000,
        "unix_socket": {"path": socket_path},
    }


class TestIPCClientConfigEnvironmentContract:
    def test_from_env_decodes_config_env_and_ignores_conflicting_legacy_values(self) -> None:
        from runsight_core.isolation import IPCClientConfig

        config = IPCClientConfig.from_env(
            {
                "RUNSIGHT_IPC_CONFIG_B64": _encoded_config(
                    _unix_config_payload("/tmp/config-owned.sock")
                ),
                "RUNSIGHT_IPC_SOCKET": "/tmp/legacy.sock",
                "RUNSIGHT_GRANT_TOKEN": "legacy-token",
            }
        )

        assert config.version == 1
        assert config.transport == "unix_socket"
        assert config.grant_token == "config-grant-token"
        assert config.heartbeat_interval_ms == 5000
        assert config.unix_socket.path == "/tmp/config-owned.sock"

    @pytest.mark.parametrize(
        ("env", "message"),
        [
            ({}, "RUNSIGHT_IPC_CONFIG_B64"),
            ({"RUNSIGHT_IPC_CONFIG_B64": "not base64!"}, "base64"),
            (
                {"RUNSIGHT_IPC_CONFIG_B64": base64.b64encode(b"not-json").decode("ascii")},
                "json",
            ),
            (
                {
                    "RUNSIGHT_IPC_CONFIG_B64": _encoded_config(
                        {**_unix_config_payload(), "version": 2}
                    )
                },
                "version",
            ),
            (
                {
                    "RUNSIGHT_IPC_SOCKET": "/tmp/legacy-only.sock",
                    "RUNSIGHT_GRANT_TOKEN": "legacy-token",
                },
                "RUNSIGHT_IPC_CONFIG_B64",
            ),
        ],
    )
    def test_from_env_fails_closed_without_valid_config_env(
        self, env: dict[str, str], message: str
    ) -> None:
        from runsight_core.isolation import IPCClientConfig

        with pytest.raises((ValueError, ValidationError), match=message):
            IPCClientConfig.from_env(env)


class TestIPCClientConfigShape:
    def test_unix_socket_config_requires_socket_path(self) -> None:
        from runsight_core.isolation import IPCClientConfig

        config = IPCClientConfig.model_validate(_unix_config_payload("/tmp/worker.sock"))

        assert config.version == 1
        assert config.transport == "unix_socket"
        assert config.unix_socket.path == "/tmp/worker.sock"

        invalid_payload = _unix_config_payload()
        invalid_payload.pop("unix_socket")
        with pytest.raises(ValidationError, match="unix_socket"):
            IPCClientConfig.model_validate(invalid_payload)

    def test_tcp_config_requires_host_and_port_before_factory_rejects_transport(self) -> None:
        from runsight_core.isolation import IPCClient, IPCClientConfig

        config = IPCClientConfig.model_validate(
            {
                "version": 1,
                "transport": "tcp",
                "grant_token": "tcp-token",
                "heartbeat_interval_ms": 5000,
                "tcp": {"host": "127.0.0.1", "port": 45678},
            }
        )

        assert config.transport == "tcp"
        assert config.tcp.host == "127.0.0.1"
        assert config.tcp.port == 45678

        with pytest.raises(ValueError, match="unsupported.*tcp|tcp.*unsupported"):
            IPCClient.from_config(config)

        invalid_payload = config.model_dump(mode="json")
        invalid_payload["tcp"].pop("port")
        with pytest.raises(ValidationError, match="port"):
            IPCClientConfig.model_validate(invalid_payload)

    def test_stdio_config_requires_jsonl_protocol_before_factory_rejects_transport(self) -> None:
        from runsight_core.isolation import IPCClient, IPCClientConfig

        config = IPCClientConfig.model_validate(
            {
                "version": 1,
                "transport": "stdio",
                "grant_token": "stdio-token",
                "heartbeat_interval_ms": 5000,
                "stdio": {"protocol": "jsonl"},
            }
        )

        assert config.transport == "stdio"
        assert config.stdio.protocol == "jsonl"

        with pytest.raises(ValueError, match="unsupported.*stdio|stdio.*unsupported"):
            IPCClient.from_config(config)

        invalid_payload = config.model_dump(mode="json")
        invalid_payload["stdio"]["protocol"] = "raw"
        with pytest.raises(ValidationError, match="jsonl|protocol"):
            IPCClientConfig.model_validate(invalid_payload)


class TestUnixSocketIPCTransportBinding:
    def test_prepare_returns_binding_with_encoded_client_config_only(self, tmp_path: Path) -> None:
        from runsight_core.isolation import (
            IPCClientConfig,
            UnixSocketIPCTransport,
            WorkspacePolicy,
            WorkspaceSession,
        )

        session = WorkspaceSession(
            id="session-ipc-config",
            host_root=tmp_path / "host",
            runtime_root=tmp_path / "runtime",
            runtime_workdir=tmp_path / "runtime",
        )
        session.host_root.mkdir()
        session.runtime_root.mkdir()

        transport = UnixSocketIPCTransport(socket_dir=tmp_path / "ipc")
        binding = transport.prepare(session, WorkspacePolicy())

        assert binding.client_config.version == 1
        assert binding.client_config.transport == "unix_socket"
        assert binding.client_config.grant_token
        assert binding.client_config.unix_socket.path == binding.server_endpoint.path
        assert binding.cleanup_required is True
        assert callable(binding.close)

        assert set(binding.env) == {"RUNSIGHT_IPC_CONFIG_B64"}
        assert "RUNSIGHT_IPC_SOCKET" not in binding.env
        assert "RUNSIGHT_GRANT_TOKEN" not in binding.env

        decoded = IPCClientConfig.from_env(binding.env)
        assert decoded == binding.client_config

        binding.close()
