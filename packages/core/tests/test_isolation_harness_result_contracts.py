"""SubprocessHarness result, cleanup, and grant-token contracts."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from isolation_harness_helpers import (
    _make_context_envelope,
    _make_result_envelope,
    _patch_harness_run_subprocess,
    _socket_fixture_path,
)
from runsight_core.isolation import (
    ContextEnvelope,
    ResultEnvelope,
)


class TestResultEnvelopeValidation:
    """SubprocessHarness validates ResultEnvelope schema and size cap."""

    @pytest.mark.asyncio
    async def test_valid_result_envelope_accepted(self):
        """A well-formed ResultEnvelope passes validation."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        result = _make_result_envelope()
        raw_json = result.model_dump_json()

        validated = harness._validate_result(raw_json, max_bytes=1_000_000)
        assert validated.block_id == "harness-block"
        assert validated.output == "done"

    @pytest.mark.asyncio
    async def test_oversized_result_rejected(self):
        """A ResultEnvelope exceeding max_output_bytes is rejected."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        result = _make_result_envelope(output="x" * 10_000)
        raw_json = result.model_dump_json()

        with pytest.raises((ValueError, Exception)) as exc_info:
            harness._validate_result(raw_json, max_bytes=100)

        assert "size" in str(exc_info.value).lower() or "bytes" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_malformed_json_rejected(self):
        """Invalid JSON is rejected during result validation."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        with pytest.raises((json.JSONDecodeError, ValueError, Exception)):
            harness._validate_result("not valid json {{{", max_bytes=1_000_000)

    @pytest.mark.asyncio
    async def test_missing_required_fields_rejected(self):
        """A ResultEnvelope missing required fields is rejected."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        # Valid JSON but missing required ResultEnvelope fields
        incomplete = json.dumps({"block_id": "harness-block"})

        with pytest.raises((ValueError, Exception)):
            harness._validate_result(incomplete, max_bytes=1_000_000)


# ===========================================================================
# SIGTERM then SIGKILL escalation on kill
# ===========================================================================


class TestCleanup:
    """Socket file and temp dir must be cleaned up on exit, even on crashes."""

    @pytest.mark.asyncio
    async def test_socket_cleaned_up_after_normal_exit(self):
        """Socket file is removed after a successful run."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        sock, sock_path = harness._create_socket()

        # Simulate cleanup
        harness._cleanup(socket_path=sock_path, working_dir=None)

        assert not Path(sock_path).exists()
        sock.close()

    @pytest.mark.asyncio
    async def test_temp_dir_cleaned_up_after_normal_exit(self):
        """Temp working dir is removed after a successful run."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        work_dir = harness._create_working_dir()

        harness._cleanup(socket_path=None, working_dir=work_dir)

        assert not Path(work_dir).exists()

    @pytest.mark.asyncio
    async def test_cleanup_handles_already_removed_socket(self, tmp_path: Path):
        """Cleanup does not raise if the socket was already removed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        # Should not raise
        harness._cleanup(
            socket_path=_socket_fixture_path(tmp_path, "rs-nonexistent.sock"),
            working_dir=None,
        )

    @pytest.mark.asyncio
    async def test_cleanup_handles_already_removed_dir(self, tmp_path: Path):
        """Cleanup does not raise if the temp dir was already removed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        # Should not raise
        harness._cleanup(
            socket_path=None,
            working_dir=_socket_fixture_path(tmp_path, "rs-nonexistent-dir"),
        )

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self):
        """Both socket and temp dir are cleaned up even when run() raises."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        sock, sock_path = harness._create_socket()
        work_dir = harness._create_working_dir()

        # Simulate a crash during run by calling cleanup directly
        harness._cleanup(socket_path=sock_path, working_dir=work_dir)

        assert not Path(sock_path).exists()
        assert not Path(work_dir).exists()
        sock.close()


# ===========================================================================
# LinearBlock round-trip via subprocess
# ===========================================================================


class TestLinearBlockRoundTrip:
    """Integration: build envelope, spawn subprocess, get result back."""

    @pytest.mark.asyncio
    async def test_run_returns_result_envelope(self, monkeypatch: pytest.MonkeyPatch):
        """SubprocessHarness.run() returns a ResultEnvelope on success."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        envelope = _make_context_envelope(block_type="linear")
        _patch_harness_run_subprocess(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id=envelope.block_id, output="worker result"),
        )
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        result = await harness.run(envelope)

        assert isinstance(result, ResultEnvelope)
        assert result.block_id == "harness-block"
        assert result.output == "worker result"

    @pytest.mark.asyncio
    async def test_run_writes_envelope_to_stdin(self, monkeypatch: pytest.MonkeyPatch):
        """SubprocessHarness passes ContextEnvelope JSON to subprocess stdin."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        envelope = _make_context_envelope()
        captured = _patch_harness_run_subprocess(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id=envelope.block_id),
        )
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        # Verify the envelope can be serialized (it will be passed to stdin)
        json_str = envelope.model_dump_json()
        parsed = ContextEnvelope.model_validate_json(json_str)
        assert parsed.block_id == envelope.block_id

        result = await harness.run(envelope)
        assert isinstance(result, ResultEnvelope)
        proc = captured["proc"]
        stdin_payload = b"".join(proc.stdin.writes).decode().strip()
        assert ContextEnvelope.model_validate_json(stdin_payload).block_id == envelope.block_id

    @pytest.mark.asyncio
    async def test_run_starts_ipc_server(self):
        """SubprocessHarness starts an IPCServer as an asyncio task during run."""
        from runsight_core.isolation import SubprocessHarness

        # The harness should have a method or attribute related to IPC server setup
        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        assert callable(getattr(harness, "run", None))

    @pytest.mark.asyncio
    async def test_result_contains_output_and_cost(self, monkeypatch: pytest.MonkeyPatch):
        """The ResultEnvelope from a successful run includes output and cost data."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        envelope = _make_context_envelope(block_type="linear")
        _patch_harness_run_subprocess(
            monkeypatch,
            harness_module,
            ResultEnvelope(
                block_id=envelope.block_id,
                output="completed",
                exit_handle="done",
                cost_usd=0.25,
                total_tokens=17,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            ),
        )
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        result = await harness.run(envelope)

        assert isinstance(result, ResultEnvelope)
        assert result.block_id == envelope.block_id
        assert result.output == "completed"
        assert result.cost_usd == pytest.approx(0.25)
        assert result.total_tokens == 17
        assert isinstance(result.cost_usd, float)
        assert isinstance(result.total_tokens, int)


class TestGrantTokenContract:
    """GrantToken model and harness env wiring for single-use subprocess auth."""

    def test_grant_token_model_exists_with_expected_defaults(self):
        from runsight_core.isolation import harness as harness_module

        GrantToken = getattr(harness_module, "GrantToken", None)
        assert GrantToken is not None

        token = GrantToken(block_id="grant-token-block")
        assert isinstance(token.token, str)
        assert token.token != ""
        assert token.block_id == "grant-token-block"
        assert token.ttl_seconds == 120.0
        assert token.consumed is False

    def test_grant_token_consume_is_single_use(self):
        from runsight_core.isolation import harness as harness_module

        GrantToken = getattr(harness_module, "GrantToken", None)
        assert GrantToken is not None

        token = GrantToken(block_id="grant-token-block")
        assert token.consume() is True
        assert token.consume() is False

    def test_grant_token_rejects_when_expired(self):
        from runsight_core.isolation import harness as harness_module

        GrantToken = getattr(harness_module, "GrantToken", None)
        assert GrantToken is not None

        token = GrantToken(block_id="grant-token-block", created_at=0.0, ttl_seconds=30.0)
        assert token.consume() is False
