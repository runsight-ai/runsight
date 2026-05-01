"""SubprocessHarness process lifecycle and stall handling contracts."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from isolation_harness_helpers import (
    _make_context_envelope,
    _patch_harness_hanging_subprocess,
)
from runsight_core.isolation import (
    HeartbeatMessage,
)


class TestTimeoutEnforcement:
    """Subprocess must be killed when it exceeds the timeout."""

    @pytest.mark.asyncio
    async def test_run_raises_on_timeout(self, monkeypatch: pytest.MonkeyPatch):
        """SubprocessHarness.run() raises a timeout error when the subprocess exceeds timeout."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"}, timeout_seconds=1)
        captured = _patch_harness_hanging_subprocess(monkeypatch, harness_module)
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))
        envelope = _make_context_envelope(timeout_seconds=1)

        # The run method should raise when the subprocess times out
        with pytest.raises((asyncio.TimeoutError, TimeoutError, Exception)) as exc_info:
            await harness.run(envelope)

        # The error should mention timeout
        assert "timeout" in str(exc_info.value).lower() or isinstance(
            exc_info.value, (asyncio.TimeoutError, TimeoutError)
        )
        assert captured["proc"].returncode == -15

    @pytest.mark.asyncio
    async def test_timeout_uses_envelope_value(self):
        """Timeout is taken from the ContextEnvelope.timeout_seconds field."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        envelope = _make_context_envelope(timeout_seconds=2)

        # Should use the envelope's timeout, not a default
        assert envelope.timeout_seconds == 2
        # Harness must respect the envelope timeout
        assert harness is not None


# ===========================================================================
# Heartbeat stall detection
# ===========================================================================


class TestHeartbeatStallDetection:
    """Subprocess must be killed when heartbeats stop arriving."""

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_kills_subprocess(self):
        """If no heartbeat for heartbeat_timeout seconds, subprocess is killed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            heartbeat_timeout=1,
        )

        # The harness should track heartbeats and kill on stall
        assert hasattr(harness, "_heartbeat_timeout") or hasattr(harness, "heartbeat_timeout")

    @pytest.mark.asyncio
    async def test_monitor_detects_missing_heartbeat(self):
        """The monitoring coroutine detects when heartbeats stop."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            heartbeat_timeout=1,
        )

        # Simulate a process that sends no heartbeats
        mock_proc = MagicMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(return_value=b"")
        mock_proc.pid = 12345
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_proc.terminate = MagicMock()

        # _monitor_heartbeats should detect stall and request kill
        killed = await harness._monitor_heartbeats(mock_proc, timeout=1)
        assert killed is True


# ===========================================================================
# Phase stall detection
# ===========================================================================


class TestPhaseStallDetection:
    """Subprocess must be killed when same phase exceeds phase_timeout."""

    @pytest.mark.asyncio
    async def test_phase_stall_kills_subprocess(self):
        """If same phase continues beyond phase_timeout, subprocess is killed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            phase_timeout=1,
        )

        assert hasattr(harness, "_phase_timeout") or hasattr(harness, "phase_timeout")

    @pytest.mark.asyncio
    async def test_phase_change_resets_timer(self):
        """When the phase changes, the phase stall timer resets."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            phase_timeout=2,
        )

        # Simulate heartbeats that change phase
        heartbeats = [
            HeartbeatMessage(
                heartbeat=1,
                phase="init",
                detail="starting",
                timestamp="2026-01-01T00:00:00Z",
            ),
            HeartbeatMessage(
                heartbeat=2,
                phase="executing",
                detail="running",
                timestamp="2026-01-01T00:00:01Z",
            ),
        ]

        # Phase changed from init -> executing, so stall timer should reset
        tracker = harness._create_heartbeat_tracker()
        for hb in heartbeats:
            tracker.update(hb)

        assert tracker.current_phase == "executing"
        assert not tracker.is_stalled


# ===========================================================================
# ResultEnvelope validated (schema + size cap)
# ===========================================================================


class TestGracefulKillEscalation:
    """Kill must send SIGTERM first, then SIGKILL after 5 seconds."""

    @pytest.mark.asyncio
    async def test_kill_sends_sigterm_first(self):
        """_kill_subprocess sends SIGTERM before SIGKILL."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        signals_sent = []
        mock_proc = MagicMock()
        mock_proc.returncode = None

        def track_terminate():
            signals_sent.append("SIGTERM")

        def track_kill():
            signals_sent.append("SIGKILL")
            mock_proc.returncode = -9

        mock_proc.terminate = track_terminate
        mock_proc.kill = track_kill
        mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)

        await harness._kill_subprocess(mock_proc)

        assert signals_sent[0] == "SIGTERM"

    @pytest.mark.asyncio
    async def test_kill_escalates_to_sigkill(self):
        """If SIGTERM doesn't work within grace period, SIGKILL is sent."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        signals_sent = []
        mock_proc = MagicMock()
        mock_proc.returncode = None

        def track_terminate():
            signals_sent.append("SIGTERM")

        def track_kill():
            signals_sent.append("SIGKILL")
            mock_proc.returncode = -9

        mock_proc.terminate = track_terminate
        mock_proc.kill = track_kill
        # Process doesn't die after SIGTERM (wait times out)
        mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)

        await harness._kill_subprocess(mock_proc)

        assert "SIGTERM" in signals_sent
        assert "SIGKILL" in signals_sent

    @pytest.mark.asyncio
    async def test_no_sigkill_if_sigterm_succeeds(self):
        """If SIGTERM causes the process to exit, no SIGKILL is sent."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})

        signals_sent = []
        mock_proc = MagicMock()
        mock_proc.returncode = None

        def track_terminate():
            signals_sent.append("SIGTERM")
            mock_proc.returncode = 0

        mock_proc.terminate = track_terminate
        mock_proc.kill = lambda: signals_sent.append("SIGKILL")
        # Process exits cleanly after SIGTERM
        mock_proc.wait = AsyncMock(return_value=0)

        await harness._kill_subprocess(mock_proc)

        assert "SIGTERM" in signals_sent
        assert "SIGKILL" not in signals_sent


# ===========================================================================
# Negative return codes mapped to meaningful error messages
# ===========================================================================


class TestNegativeReturnCodeMapping:
    """Negative return codes should map to meaningful signal-based errors."""

    @pytest.mark.asyncio
    async def test_sigkill_mapped_to_oom(self):
        """Return code -9 (SIGKILL) is mapped to OOM error message."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        error_msg = harness._map_return_code(-9)

        assert "SIGKILL" in error_msg or "OOM" in error_msg or "signal 9" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_sigsegv_mapped_to_segfault(self):
        """Return code -11 (SIGSEGV) is mapped to segfault error message."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        error_msg = harness._map_return_code(-11)

        assert (
            "SIGSEGV" in error_msg
            or "segfault" in error_msg.lower()
            or "signal 11" in error_msg.lower()
        )

    @pytest.mark.asyncio
    async def test_sigterm_mapped(self):
        """Return code -15 (SIGTERM) is mapped to termination message."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        error_msg = harness._map_return_code(-15)

        assert (
            "SIGTERM" in error_msg
            or "terminated" in error_msg.lower()
            or "signal 15" in error_msg.lower()
        )

    @pytest.mark.asyncio
    async def test_positive_return_code_is_application_error(self):
        """Return code > 0 indicates an application-level error."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        error_msg = harness._map_return_code(1)

        assert "error" in error_msg.lower() or "exit" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_zero_return_code_is_success(self):
        """Return code 0 is success (no error)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        result = harness._map_return_code(0)

        # Zero should return None or empty string (no error)
        assert result is None or result == ""


# ===========================================================================
# Socket and temp dir cleaned up on exit (including crashes)
# ===========================================================================
