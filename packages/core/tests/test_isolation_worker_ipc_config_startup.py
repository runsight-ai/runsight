"""Worker startup uses encoded IPC config rather than legacy env discovery."""

from __future__ import annotations

import ast
import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from isolation_worker_helpers import (
    make_context_envelope,
    parse_result_envelope,
    run_worker_subprocess,
    worker_socket_path,
)

pytestmark = pytest.mark.real_subprocess_isolation


def _encoded_config(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.b64encode(raw).decode("ascii")


def _unix_config_env(socket_path: str) -> dict[str, str]:
    return {
        "RUNSIGHT_IPC_CONFIG_B64": _encoded_config(
            {
                "version": 1,
                "transport": "unix_socket",
                "grant_token": "config-worker-token",
                "heartbeat_interval_ms": 5000,
                "unix_socket": {"path": socket_path},
            }
        )
    }


class _LegacyEnvReadVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.offenders: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "environ"
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "os"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in {"RUNSIGHT_GRANT_TOKEN", "RUNSIGHT_IPC_SOCKET"}
        ):
            self.offenders.append(f"os.environ.get({node.args[0].value!r})")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if (
            isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "os"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value in {"RUNSIGHT_GRANT_TOKEN", "RUNSIGHT_IPC_SOCKET"}
        ):
            self.offenders.append(f"os.environ[{node.slice.value!r}]")
        self.generic_visit(node)


class TestWorkerIPCConfigStartupBoundary:
    def test_worker_source_does_not_read_legacy_ipc_or_grant_env_vars(self) -> None:
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        visitor = _LegacyEnvReadVisitor()
        visitor.visit(ast.parse(source_file.read_text(encoding="utf-8")))

        assert visitor.offenders == []

    def test_legacy_only_env_fails_closed_before_worker_uses_socket_discovery(self) -> None:
        envelope = make_context_envelope(block_type="nonexistent_block_type_xyz")

        result = run_worker_subprocess(
            envelope,
            {
                "RUNSIGHT_GRANT_TOKEN": "legacy-token",
                "RUNSIGHT_IPC_SOCKET": worker_socket_path("legacy-only"),
            },
            omit=("RUNSIGHT_IPC_CONFIG_B64",),
        )

        assert result.returncode == 1
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for missing config env"
        result_env = parse_result_envelope(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_IPC_CONFIG_B64" in result_env.error

    @pytest.mark.parametrize(
        "legacy_env",
        [
            {},
            {
                "RUNSIGHT_GRANT_TOKEN": "legacy-env-token",
                "RUNSIGHT_IPC_SOCKET": "/tmp/legacy-worker.sock",
            },
        ],
        ids=["without-legacy-env", "with-conflicting-legacy-env"],
    )
    def test_worker_execution_constructs_ipc_client_from_decoded_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        legacy_env: dict[str, str],
    ) -> None:
        from runsight_core.block_io import BlockOutput
        from runsight_core.isolation import worker

        envelope = make_context_envelope(block_type="assertion")
        config_socket_path = str(tmp_path / "config.sock")
        observed_configs: list[Any] = []
        direct_constructor_calls: list[dict[str, Any]] = []
        stdout = io.StringIO()

        class ConfigOnlyIPCClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                direct_constructor_calls.append({"args": args, "kwargs": kwargs})
                raise AssertionError("worker execution must use IPCClient.from_config")

            @classmethod
            def from_config(cls, config: object) -> "ConfigOnlyIPCClient":
                observed_configs.append(config)
                client = object.__new__(cls)
                client.config = config
                return client

            async def connect(self) -> SimpleNamespace:
                return SimpleNamespace(accepted=True, error=None)

            async def close(self) -> None:
                return None

        class FakeBlock:
            async def execute(self, _ctx: object) -> BlockOutput:
                return BlockOutput(output="ok", exit_handle="done")

        worker._heartbeat_stop.clear()
        monkeypatch.setattr(worker, "_emit_heartbeat", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(worker, "_heartbeat_loop", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(worker.isolation_ipc, "IPCClient", ConfigOnlyIPCClient)
        monkeypatch.setattr(
            worker._proxies,
            "create_tool_stubs",
            lambda _tools, *, ipc_client: [],
        )
        monkeypatch.setattr(
            worker._proxies,
            "create_runner",
            lambda *, model_name, ipc_client: object(),
        )
        monkeypatch.setattr(
            worker._support,
            "reconstruct_soul",
            lambda soul, *, resolved_tools: soul,
        )
        monkeypatch.setattr(
            worker._support,
            "build_scoped_state",
            lambda _envelope: SimpleNamespace(conversation_histories={}),
        )
        monkeypatch.setattr(worker._support, "_create_block", lambda *_args: FakeBlock())
        monkeypatch.setattr(worker.sys, "stdin", io.StringIO(envelope.model_dump_json()))
        monkeypatch.setattr(worker.sys, "stdout", stdout)
        monkeypatch.delenv("RUNSIGHT_GRANT_TOKEN", raising=False)
        monkeypatch.delenv("RUNSIGHT_IPC_SOCKET", raising=False)
        for key, value in legacy_env.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv(
            "RUNSIGHT_IPC_CONFIG_B64",
            _unix_config_env(config_socket_path)["RUNSIGHT_IPC_CONFIG_B64"],
        )

        with pytest.raises(SystemExit) as exit_info:
            worker.main()

        assert exit_info.value.code == 0
        result_env = parse_result_envelope(stdout.getvalue())
        assert result_env.error is None
        assert direct_constructor_calls == []
        assert len(observed_configs) == 1

        config = observed_configs[0]
        assert config.grant_token == "config-worker-token"
        assert config.unix_socket.path == config_socket_path
        assert config.transport == "unix_socket"
