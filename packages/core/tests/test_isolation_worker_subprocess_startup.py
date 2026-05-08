"""Isolation worker subprocess startup, stderr, exit, and envelope contracts."""

from __future__ import annotations

import json

import pytest
from isolation_worker_helpers import (
    make_context_envelope,
    parse_result_envelope,
    run_worker_subprocess,
)
from runsight_core.isolation.envelope import ContextEnvelope, HeartbeatMessage, ResultEnvelope

pytestmark = pytest.mark.real_subprocess_isolation


class TestWorkerHeartbeat:
    """Worker must emit heartbeat JSON lines on stderr with phase info."""

    def test_heartbeat_emitted_on_stderr(self):
        """Running the worker produces heartbeat lines on stderr."""
        envelope = make_context_envelope()
        result = run_worker_subprocess(envelope)
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
        envelope = make_context_envelope()
        result = run_worker_subprocess(envelope)
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
        envelope = make_context_envelope()
        result = run_worker_subprocess(envelope)
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


class TestWorkerErrorsInResultEnvelope:
    """Errors must be captured in ResultEnvelope with error + error_type."""

    def test_error_produces_result_envelope_on_stdout(self):
        """When execution fails, stdout still contains a valid ResultEnvelope."""
        # Use an invalid block_type to trigger an error
        envelope = make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = run_worker_subprocess(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on error"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert result_env.error_type is not None

    def test_error_result_has_block_id(self):
        """Error ResultEnvelope preserves the block_id from the context."""
        envelope = make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = run_worker_subprocess(envelope)
        result_env = ResultEnvelope.model_validate_json(result.stdout.strip())
        assert result_env.block_id == "worker_block"


class TestWorkerMissingIpcConfig:
    """Missing RUNSIGHT_IPC_CONFIG_B64 must exit 1 with error in ResultEnvelope."""

    def test_missing_ipc_config_exits_nonzero(self):
        """Worker exits with code 1 when RUNSIGHT_IPC_CONFIG_B64 is absent."""
        envelope = make_context_envelope()
        result = run_worker_subprocess(
            envelope,
            omit=("RUNSIGHT_IPC_CONFIG_B64",),
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope, not just a Python traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for missing IPC config"
        result_env = parse_result_envelope(stdout)
        assert result_env.error is not None

    def test_missing_ipc_config_has_error_in_result(self):
        """ResultEnvelope on stdout describes the missing IPC config."""
        envelope = make_context_envelope()
        result = run_worker_subprocess(
            envelope,
            omit=("RUNSIGHT_IPC_CONFIG_B64",),
        )
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on env error"
        result_env = parse_result_envelope(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_IPC_CONFIG_B64" in result_env.error


class TestWorkerExitCodes:
    """Worker must exit 0 on success and 1 on error."""

    def test_error_exits_with_code_1(self):
        """An error during execution produces exit code 1."""
        # Invalid block type should cause an error
        envelope = make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = run_worker_subprocess(envelope)
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
        envelope = make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = run_worker_subprocess(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        # Must parse as valid ResultEnvelope
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.block_id == "worker_block"


class TestWorkerEnvelopeParsing:
    """Worker must read stdin and parse as ContextEnvelope."""

    def test_parse_context_envelope_from_json(self):
        """Worker has a function to parse ContextEnvelope from JSON string."""
        from runsight_core.isolation.worker_support import parse_context_envelope

        envelope = make_context_envelope()
        parsed = parse_context_envelope(envelope.model_dump_json())
        assert isinstance(parsed, ContextEnvelope)
        assert parsed.block_id == "worker_block"

    def test_invalid_json_produces_error_result(self):
        """Malformed JSON input yields exit 1 with error in ResultEnvelope."""
        result = run_worker_subprocess(
            input_text="this is not json",
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope with error info, not a raw traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for invalid JSON"
        result_env = parse_result_envelope(stdout)
        assert result_env.error is not None
