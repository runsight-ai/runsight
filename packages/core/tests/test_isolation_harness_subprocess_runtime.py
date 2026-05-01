"""SubprocessHarness subprocess runtime isolation contracts."""

from __future__ import annotations

import os
import socket
import stat
import sys
import tempfile
from pathlib import Path

import pytest
from isolation_harness_helpers import (
    _socket_fixture_path,
)


class TestMinimalEnvironment:
    """Subprocess must receive minimal env with grant token, not API key."""

    @pytest.mark.asyncio
    async def test_subprocess_harness_importable(self):
        """SubprocessHarness can be imported from runsight_core.isolation."""
        from runsight_core.isolation import SubprocessHarness

        assert SubprocessHarness is not None

    @pytest.mark.asyncio
    async def test_spawn_env_contains_path(self):
        """Subprocess env must include PATH."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        env = harness._build_subprocess_env()

        assert "PATH" in env

    @pytest.mark.asyncio
    async def test_spawn_env_contains_grant_token(self):
        """Subprocess env must include RUNSIGHT_GRANT_TOKEN."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        env = harness._build_subprocess_env()

        assert "RUNSIGHT_GRANT_TOKEN" in env
        assert isinstance(env["RUNSIGHT_GRANT_TOKEN"], str)
        assert env["RUNSIGHT_GRANT_TOKEN"] != ""

    @pytest.mark.asyncio
    async def test_spawn_env_does_not_include_block_api_key(self):
        """Subprocess env must not include RUNSIGHT_BLOCK_API_KEY."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        env = harness._build_subprocess_env()

        assert "RUNSIGHT_BLOCK_API_KEY" not in env

    @pytest.mark.asyncio
    async def test_spawn_env_does_not_inherit_host_env(self):
        """Subprocess env must not inherit the full host environment."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        env = harness._build_subprocess_env()

        # Common env vars that should not leak through.
        for var in ("HOME", "USER", "SHELL", "DATABASE_URL", "SECRET_KEY"):
            assert var not in env, f"{var} should not be in subprocess env"

    @pytest.mark.asyncio
    async def test_spawn_env_contains_ipc_socket_path(self, tmp_path: Path):
        """Subprocess env must include RUNSIGHT_IPC_SOCKET."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        socket_path = _socket_fixture_path(tmp_path, "rs-harness-ipc.sock")
        env = harness._build_subprocess_env(socket_path=socket_path)

        assert "RUNSIGHT_IPC_SOCKET" in env
        assert env["RUNSIGHT_IPC_SOCKET"] == socket_path

    @pytest.mark.asyncio
    async def test_spawn_env_has_macos_dylib_paths(self):
        """On macOS, subprocess env includes DYLD_LIBRARY_PATH or DYLD_FALLBACK_LIBRARY_PATH."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        env = harness._build_subprocess_env()

        if sys.platform == "darwin":
            has_dylib = "DYLD_LIBRARY_PATH" in env or "DYLD_FALLBACK_LIBRARY_PATH" in env
            assert has_dylib, "macOS env must include dylib paths"

    @pytest.mark.asyncio
    async def test_spawn_env_limited_key_count(self, tmp_path: Path):
        """Subprocess env should have a small number of keys (minimal env)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        env = harness._build_subprocess_env(
            socket_path=_socket_fixture_path(tmp_path, "rs-test.sock")
        )

        # PATH + grant token + socket + maybe macOS dylib paths = at most ~5-6 keys
        assert len(env) <= 10, f"Env has too many keys ({len(env)}), should be minimal"


# ===========================================================================
# Subprocess working dir is fresh temp dir
# ===========================================================================


class TestFreshTempWorkingDir:
    """Subprocess must run in a fresh temp dir, not project root."""

    @pytest.mark.asyncio
    async def test_working_dir_is_temp_dir(self):
        """SubprocessHarness creates a fresh temp dir for the subprocess cwd."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        work_dir = harness._create_working_dir()

        assert Path(work_dir).exists()
        assert Path(work_dir).is_dir()
        # Should be under the system temp directory
        assert work_dir.startswith(tempfile.gettempdir())

        # Cleanup
        os.rmdir(work_dir)

    @pytest.mark.asyncio
    async def test_working_dir_is_not_project_root(self):
        """Working dir must not be the project root or cwd."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        work_dir = harness._create_working_dir()

        assert work_dir != os.getcwd()

        # Cleanup
        os.rmdir(work_dir)

    @pytest.mark.asyncio
    async def test_each_call_creates_unique_dir(self):
        """Each invocation creates a different temp dir."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        dir1 = harness._create_working_dir()
        dir2 = harness._create_working_dir()

        assert dir1 != dir2

        # Cleanup
        os.rmdir(dir1)
        os.rmdir(dir2)


# ===========================================================================
# Socket created by SubprocessHarness, mode 0600, random path
# ===========================================================================


class TestSocketCreation:
    """SubprocessHarness creates and binds the socket (not IPCServer)."""

    @pytest.mark.asyncio
    async def test_create_socket_returns_bound_socket(self):
        """_create_socket returns a bound Unix socket object."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        sock, sock_path = harness._create_socket()

        try:
            assert isinstance(sock, socket.socket)
            assert sock.family == socket.AF_UNIX
            assert Path(sock_path).exists()
        finally:
            sock.close()
            Path(sock_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_socket_path_is_random(self):
        """Socket path must be random (different each call)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        _, path1 = harness._create_socket()
        _, path2 = harness._create_socket()

        try:
            assert path1 != path2
        finally:
            Path(path1).unlink(missing_ok=True)
            Path(path2).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_socket_path_format(self):
        """Socket path follows the harness temp-socket prefix pattern."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        sock, sock_path = harness._create_socket()

        try:
            assert Path(sock_path).name.startswith("rs-")
            assert sock_path.endswith(".sock")
            # Must be under 104 bytes (macOS AF_UNIX limit)
            assert len(sock_path.encode()) < 104
        finally:
            sock.close()
            Path(sock_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_socket_permissions_0600(self):
        """Socket file must have mode 0600 (owner read/write only)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        sock, sock_path = harness._create_socket()

        try:
            mode = os.stat(sock_path).st_mode
            # Check only the permission bits
            perm = stat.S_IMODE(mode)
            assert perm == 0o600, f"Socket permissions should be 0600, got {oct(perm)}"
        finally:
            sock.close()
            Path(sock_path).unlink(missing_ok=True)


# ===========================================================================
# ContextEnvelope contains only YAML-declared scoped data
# ===========================================================================


class TestContextScoping:
    """ContextEnvelope must contain only declaration-governed scoped data."""

    @pytest.mark.asyncio
    async def test_linear_block_uses_declared_inputs_not_previous_block_type_scope(self):
        """LinearBlock scoping follows declared inputs, not previous_block_id."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        state = WorkflowState(
            results={
                "previous-linear-block": BlockResult(output="first result"),
                "harness-block": BlockResult(output='{"summary": "declared", "secret": "hidden"}'),
            },
            shared_memory={"global_key": "global_value"},
        )

        block_config = {
            "block_id": "target-linear-block",
            "block_type": "linear",
            "soul_ref": "test",
            "previous_block_id": "previous-linear-block",
            "inputs": {"summary": {"from": "harness-block.summary"}},
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "harness-block" in envelope.scoped_results
        assert "previous-linear-block" not in envelope.scoped_results
        assert envelope.inputs == {"summary": "declared"}
        assert "hidden" not in envelope.model_dump_json()

    @pytest.mark.asyncio
    async def test_gate_block_gets_eval_key_as_internal_declared_context(self):
        """GateBlock scoping is represented as governed internal content input."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        state = WorkflowState(
            results={
                "eval-block": BlockResult(output="eval output"),
                "other-block": BlockResult(output="other output"),
            }
        )

        block_config = {
            "block_id": "quality-gate-block",
            "block_type": "gate",
            "eval_key": "eval-block",
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "eval-block" in envelope.scoped_results
        assert "other-block" not in envelope.scoped_results
        assert envelope.inputs == {"content": "eval output"}

    @pytest.mark.asyncio
    async def test_synthesize_block_gets_input_block_ids_as_internal_declared_context(self):
        """SynthesizeBlock input_block_ids are governed internal inputs."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        state = WorkflowState(
            results={
                "source-alpha-block": BlockResult(output="a output"),
                "source-beta-block": BlockResult(output="b output"),
                "source-gamma-block": BlockResult(output="c output"),
            }
        )

        block_config = {
            "block_id": "summary-synthesis-block",
            "block_type": "synthesize",
            "input_block_ids": ["source-alpha-block", "source-gamma-block"],
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "source-alpha-block" in envelope.scoped_results
        assert "source-gamma-block" in envelope.scoped_results
        assert "source-beta-block" not in envelope.scoped_results
        assert envelope.inputs == {
            "source-alpha-block": "a output",
            "source-gamma-block": "c output",
        }

    @pytest.mark.asyncio
    async def test_declared_namespace_inputs_replace_legacy_context_scope(self):
        """YAML inputs/access replace legacy context_scope serialization."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        state = WorkflowState(
            results={
                "declared-source-block": BlockResult(output="x"),
                "legacy-context-block": BlockResult(output="y"),
                "legacy-secret-block": BlockResult(output="z"),
            },
            shared_memory={
                "allowed_key": "allowed_val",
                "secret_key": "secret_val",
            },
        )

        block_config = {
            "block_id": "declared-input-block",
            "block_type": "linear",
            "inputs": {
                "x": {"from": "declared-source-block"},
                "allowed": {"from": "shared_memory.allowed_key"},
            },
            "context_scope": {
                "results": ["legacy-context-block", "legacy-secret-block"],
                "shared_memory": ["secret_key"],
            },
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "declared-source-block" in envelope.scoped_results
        assert "legacy-secret-block" not in envelope.scoped_results
        assert "legacy-context-block" not in envelope.scoped_results
        assert "allowed_key" in envelope.scoped_shared_memory
        assert "secret_key" not in envelope.scoped_shared_memory
        assert envelope.inputs == {"x": "x", "allowed": "allowed_val"}

    @pytest.mark.asyncio
    async def test_raw_access_block_config_is_rejected_while_default_remains_declared(
        self,
    ):
        """Raw harness configs must reject access while the implicit default stays declared."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        state = WorkflowState()

        declared_envelope = harness._build_context_envelope(
            state=state,
            block_config={
                "block_id": "harness-block",
                "block_type": "linear",
            },
        )
        assert declared_envelope.access == "declared"

        with pytest.raises(ValueError, match=r"access.*unsupported|all-access is no longer"):
            harness._build_context_envelope(
                state=state,
                block_config={
                    "block_id": "harness-block",
                    "block_type": "linear",
                    "access": "declared",
                },
            )


# ===========================================================================
# Timeout enforced by terminating the subprocess
# ===========================================================================
