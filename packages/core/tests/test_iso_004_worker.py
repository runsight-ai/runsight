"""
Failing tests for RUN-399: ISO-004 — Worker entry point (subprocess main loop).

Tests cover every AC item:
1.  LiteLLMClient direct LLM calls
2.  IPCClient for tools only
3.  Heartbeat with phase on stderr
4.  Errors in ResultEnvelope
5.  fit_to_budget local
6.  Stateful history round-trips
7.  Zero workflow/observer/api imports
8.  Missing RUNSIGHT_BLOCK_API_KEY env var: exit 1 with clear error
9.  Missing RUNSIGHT_IPC_SOCKET env var: exit 1 with clear error
10. Exit 0/1
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    HeartbeatMessage,
    ResultEnvelope,
    SoulEnvelope,
    TaskEnvelope,
    ToolDefEnvelope,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context_envelope(**overrides) -> ContextEnvelope:
    """Build a minimal valid ContextEnvelope for test purposes."""
    defaults = dict(
        block_id="blk_1",
        block_type="linear",
        block_config={},
        soul=SoulEnvelope(
            id="soul_1",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o",
            max_tool_iterations=5,
        ),
        tools=[],
        task=TaskEnvelope(
            id="task_1",
            instruction="Say hello",
            context={},
        ),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=30,
        max_output_bytes=1_000_000,
    )
    defaults.update(overrides)
    return ContextEnvelope(**defaults)


def _run_worker(
    envelope: ContextEnvelope,
    env_extra: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess:
    """Invoke the worker as a subprocess, piping the envelope via stdin."""
    env = os.environ.copy()
    # Defaults for required env vars
    env.setdefault("RUNSIGHT_BLOCK_API_KEY", "test-key-123")
    env.setdefault("RUNSIGHT_IPC_SOCKET", "/tmp/test_ipc.sock")
    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        [sys.executable, "-m", "runsight_core.isolation.worker"],
        input=envelope.model_dump_json(),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


# ==============================================================================
# AC1: LiteLLMClient direct LLM calls — worker uses LiteLLMClient, not IPC
# ==============================================================================


class TestWorkerUsesLiteLLMClient:
    """The worker must use LiteLLMClient directly for LLM calls."""

    def test_worker_module_importable(self):
        """runsight_core.isolation.worker can be imported."""
        import runsight_core.isolation.worker  # noqa: F401

    def test_worker_creates_litellm_client_with_api_key(self):
        """Worker creates LiteLLMClient with RUNSIGHT_BLOCK_API_KEY."""
        from runsight_core.isolation.worker import create_llm_client

        client = create_llm_client(model_name="gpt-4o", api_key="test-key")
        # The client should be a LiteLLMClient with the given api_key
        from runsight_core.llm.client import LiteLLMClient

        assert isinstance(client, LiteLLMClient)
        assert client.api_key == "test-key"

    def test_worker_creates_runner_with_litellm_client(self):
        """Worker creates RunsightTeamRunner with the correct model and key."""
        from runsight_core.isolation.worker import create_runner

        runner = create_runner(model_name="gpt-4o", api_key="test-key")
        from runsight_core.runner import RunsightTeamRunner

        assert isinstance(runner, RunsightTeamRunner)


# ==============================================================================
# AC2: IPCClient for tools only — tools are IPC stubs, not real implementations
# ==============================================================================


class TestWorkerIPCToolStubs:
    """Tools must be routed through IPCClient, not executed locally."""

    def test_worker_creates_tool_stubs_from_envelope(self):
        """Worker converts ToolDefEnvelope list into IPC-backed tool stubs."""
        from runsight_core.isolation.worker import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(source="http", config={"url": "https://example.com"}, exits=["done"]),
        ]
        stubs = create_tool_stubs(tool_defs, socket_path="/tmp/test.sock")
        assert len(stubs) == 1

    def test_tool_stubs_are_callable(self):
        """Each tool stub must be callable (used as a tool function)."""
        from runsight_core.isolation.worker import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(source="http", config={"url": "https://example.com"}, exits=["done"]),
        ]
        stubs = create_tool_stubs(tool_defs, socket_path="/tmp/test.sock")
        assert callable(stubs[0])


# ==============================================================================
# AC3: Heartbeat with phase on stderr
# ==============================================================================


class TestWorkerHeartbeat:
    """Worker must emit heartbeat JSON lines on stderr with phase info."""

    def test_heartbeat_emitted_on_stderr(self):
        """Running the worker produces heartbeat lines on stderr."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
        stderr_lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
        # At least one heartbeat should appear
        heartbeats = []
        for line in stderr_lines:
            try:
                data = json.loads(line)
                if "heartbeat" in data:
                    heartbeats.append(data)
            except json.JSONDecodeError:
                continue
        assert len(heartbeats) >= 1, (
            f"Expected at least 1 heartbeat on stderr, got: {result.stderr}"
        )

    def test_heartbeat_contains_phase(self):
        """Each heartbeat must include a 'phase' field."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
        stderr_lines = result.stderr.strip().splitlines()
        for line in stderr_lines:
            try:
                data = json.loads(line)
                if "heartbeat" in data:
                    assert "phase" in data, f"Heartbeat missing 'phase': {data}"
                    assert isinstance(data["phase"], str)
                    break
            except json.JSONDecodeError:
                continue
        else:
            pytest.fail(f"No heartbeat found on stderr: {result.stderr}")

    def test_heartbeat_validates_as_heartbeat_message(self):
        """Each heartbeat line on stderr must validate as HeartbeatMessage."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
        stderr_lines = result.stderr.strip().splitlines()
        found = False
        for line in stderr_lines:
            try:
                data = json.loads(line)
                if "heartbeat" in data:
                    hb = HeartbeatMessage.model_validate(data)
                    assert hb.phase is not None
                    found = True
                    break
            except json.JSONDecodeError:
                continue
        assert found, f"No valid HeartbeatMessage on stderr: {result.stderr}"


# ==============================================================================
# AC4: Errors in ResultEnvelope
# ==============================================================================


class TestWorkerErrorsInResultEnvelope:
    """Errors must be captured in ResultEnvelope with error + error_type."""

    def test_error_produces_result_envelope_on_stdout(self):
        """When execution fails, stdout still contains a valid ResultEnvelope."""
        # Use an invalid block_type to trigger an error
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on error"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert result_env.error_type is not None

    def test_error_result_has_block_id(self):
        """Error ResultEnvelope preserves the block_id from the context."""
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        result_env = ResultEnvelope.model_validate_json(result.stdout.strip())
        assert result_env.block_id == "blk_1"


# ==============================================================================
# AC5: fit_to_budget local
# ==============================================================================


class TestWorkerFitToBudget:
    """Worker must apply fit_to_budget locally for context windowing."""

    def test_worker_imports_fit_to_budget(self):
        """Worker module uses fit_to_budget from runsight_core.memory.budget."""
        from runsight_core.isolation.worker import build_budgeted_history

        # The function should exist and be callable
        assert callable(build_budgeted_history)

    def test_long_history_is_trimmed(self):
        """Conversation history exceeding budget is trimmed before execution."""
        from runsight_core.isolation.worker import build_budgeted_history

        # Create a long conversation history
        long_history = [{"role": "user", "content": f"Message {i} " * 500} for i in range(50)]
        trimmed = build_budgeted_history(
            model="gpt-4o",
            system_prompt="You test things.",
            instruction="Say hello",
            conversation_history=long_history,
        )
        # Budget should trim — result must be shorter than input
        assert len(trimmed) < len(long_history)


# ==============================================================================
# AC6: Stateful history round-trips
# ==============================================================================


class TestWorkerStatefulHistory:
    """Worker must return updated conversation_history in ResultEnvelope."""

    def test_result_envelope_contains_conversation_history(self):
        """ResultEnvelope includes conversation_history from execution."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert isinstance(result_env.conversation_history, list)

    def test_input_history_is_carried_forward(self):
        """History provided in ContextEnvelope is included in the output."""
        prior_history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        envelope = _make_context_envelope(conversation_history=prior_history)
        result = _run_worker(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        result_env = ResultEnvelope.model_validate_json(stdout)
        # Output history should contain at least the input messages
        assert len(result_env.conversation_history) >= len(prior_history)


# ==============================================================================
# AC7: Zero workflow/observer/api imports
# ==============================================================================


class TestWorkerImportBoundary:
    """Worker must NOT import runsight_core.workflow, observer, or api modules."""

    def test_no_workflow_import(self):
        """Worker source must not import runsight_core.workflow."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.workflow" not in source, (
            "Worker must not import runsight_core.workflow"
        )

    def test_no_observer_import(self):
        """Worker source must not import runsight_core.observer."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.observer" not in source, (
            "Worker must not import runsight_core.observer"
        )

    def test_no_api_import(self):
        """Worker source must not import runsight_api."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_api" not in source, "Worker must not import runsight_api"

    def test_no_sqlmodel_import(self):
        """Worker source must not import sqlmodel."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "sqlmodel" not in source, "Worker must not import sqlmodel"


# ==============================================================================
# AC8: Missing RUNSIGHT_BLOCK_API_KEY → exit 1 with clear error
# ==============================================================================


class TestWorkerMissingApiKey:
    """Missing RUNSIGHT_BLOCK_API_KEY must exit 1 with error in ResultEnvelope."""

    def test_missing_api_key_exits_nonzero(self):
        """Worker exits with code 1 when RUNSIGHT_BLOCK_API_KEY is absent."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_BLOCK_API_KEY", None)
        env_override["RUNSIGHT_IPC_SOCKET"] = "/tmp/test.sock"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope, not just a Python traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for missing API key"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None

    def test_missing_api_key_has_error_in_result(self):
        """ResultEnvelope on stdout describes the missing API key."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_BLOCK_API_KEY", None)
        env_override["RUNSIGHT_IPC_SOCKET"] = "/tmp/test.sock"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on env error"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_BLOCK_API_KEY" in result_env.error


# ==============================================================================
# AC9: Missing RUNSIGHT_IPC_SOCKET → exit 1 with clear error
# ==============================================================================


class TestWorkerMissingIpcSocket:
    """Missing RUNSIGHT_IPC_SOCKET must exit 1 with error in ResultEnvelope."""

    def test_missing_ipc_socket_exits_nonzero(self):
        """Worker exits with code 1 when RUNSIGHT_IPC_SOCKET is absent."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_IPC_SOCKET", None)
        env_override["RUNSIGHT_BLOCK_API_KEY"] = "test-key"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope, not just a Python traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for missing IPC socket"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None

    def test_missing_ipc_socket_has_error_in_result(self):
        """ResultEnvelope on stdout describes the missing IPC socket."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_IPC_SOCKET", None)
        env_override["RUNSIGHT_BLOCK_API_KEY"] = "test-key"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on env error"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_IPC_SOCKET" in result_env.error


# ==============================================================================
# AC10: Exit 0 on success, exit 1 on error
# ==============================================================================


class TestWorkerExitCodes:
    """Worker must exit 0 on success and 1 on error."""

    def test_error_exits_with_code_1(self):
        """An error during execution produces exit code 1."""
        # Invalid block type should cause an error
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        assert result.returncode == 1, (
            f"Expected exit 1 on error, got {result.returncode}. "
            f"stdout={result.stdout}, stderr={result.stderr}"
        )
        # Must produce a proper ResultEnvelope, not a raw Python traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for error exit"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None

    def test_result_envelope_on_stdout_for_any_exit(self):
        """Regardless of exit code, stdout must contain a valid ResultEnvelope."""
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        # Must parse as valid ResultEnvelope
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.block_id == "blk_1"


# ==============================================================================
# AC3 supplement: stdin → ContextEnvelope parsing
# ==============================================================================


class TestWorkerEnvelopeParsing:
    """Worker must read stdin and parse as ContextEnvelope."""

    def test_parse_context_envelope_from_json(self):
        """Worker has a function to parse ContextEnvelope from JSON string."""
        from runsight_core.isolation.worker import parse_context_envelope

        envelope = _make_context_envelope()
        parsed = parse_context_envelope(envelope.model_dump_json())
        assert isinstance(parsed, ContextEnvelope)
        assert parsed.block_id == "blk_1"

    def test_invalid_json_produces_error_result(self):
        """Malformed JSON input yields exit 1 with error in ResultEnvelope."""
        env = os.environ.copy()
        env["RUNSIGHT_BLOCK_API_KEY"] = "test-key"
        env["RUNSIGHT_IPC_SOCKET"] = "/tmp/test.sock"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input="this is not json",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope with error info, not a raw traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for invalid JSON"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None


# ==============================================================================
# Soul reconstruction from SoulEnvelope
# ==============================================================================


class TestWorkerSoulReconstruction:
    """Worker must reconstruct a Soul primitive from SoulEnvelope."""

    def test_reconstruct_soul_from_envelope(self):
        """Worker converts SoulEnvelope to a runsight_core.primitives.Soul."""
        from runsight_core.isolation.worker import reconstruct_soul

        soul_env = SoulEnvelope(
            id="soul_1",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o",
            max_tool_iterations=5,
        )
        soul = reconstruct_soul(soul_env)
        from runsight_core.primitives import Soul

        assert isinstance(soul, Soul)
        assert soul.id == "soul_1"
        assert soul.role == "Tester"
        assert soul.system_prompt == "You test things."
        assert soul.model_name == "gpt-4o"
        assert soul.max_tool_iterations == 5


# ==============================================================================
# Scoped WorkflowState construction
# ==============================================================================


class TestWorkerScopedState:
    """Worker must construct a scoped WorkflowState from envelope data."""

    def test_build_scoped_state(self):
        """Worker builds a WorkflowState from scoped_results and shared_memory."""
        from runsight_core.isolation.worker import build_scoped_state

        envelope = _make_context_envelope(
            scoped_results={"prev_block": {"output": "hello", "exit_handle": "done"}},
            scoped_shared_memory={"key": "value"},
            conversation_history=[{"role": "user", "content": "hi"}],
        )
        state = build_scoped_state(envelope)
        from runsight_core.state import WorkflowState

        assert isinstance(state, WorkflowState)
        assert "key" in state.shared_memory
        assert state.current_task is not None
        assert state.current_task.instruction == "Say hello"
