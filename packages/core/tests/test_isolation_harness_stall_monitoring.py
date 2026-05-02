"""Subprocess harness stall and timeout monitoring behavior."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
from isolation_monitoring_helpers import (
    _make_context_envelope,
    _make_heartbeat,
)
from runsight_core.isolation import (
    SubprocessHarness,
)


class TestHeartbeatStallKill:
    """No heartbeat within timeout window must terminate the subprocess."""

    @pytest.mark.asyncio
    async def test_no_heartbeat_triggers_kill(self):
        """If the subprocess sends no heartbeats within the heartbeat timeout,
        _monitor_heartbeats must return True (killed) and terminate the process."""
        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            heartbeat_timeout=0.1,  # 100ms for fast test
        )

        # Fake process that never writes to stderr
        proc = MagicMock()
        proc.returncode = None
        proc.stderr = AsyncMock()
        proc.stderr.readline = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.terminate = MagicMock()

        killed = await harness._monitor_heartbeats(proc, timeout=0.1)

        assert killed is True
        proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_regular_heartbeats_keep_process_alive(self):
        """If heartbeats arrive within the timeout, the process is not killed."""
        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            heartbeat_timeout=1.0,
        )

        hb = _make_heartbeat(seq=1, phase="initializing")
        hb_line = hb.model_dump_json().encode() + b"\n"

        call_count = 0

        async def readline_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return hb_line
            return b""  # EOF — process exited normally

        proc = MagicMock()
        proc.returncode = None
        proc.stderr = AsyncMock()
        proc.stderr.readline = AsyncMock(side_effect=readline_side_effect)
        proc.terminate = MagicMock()

        result = await harness._monitor_heartbeats(proc, timeout=1.0)

        assert result is True  # EOF detected

        # EOF returns True (process gone), but terminate should NOT be called
        # because the exit was clean (no timeout)
        proc.terminate.assert_not_called()


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestPhaseStallKill:
    """Subprocess stuck in the same phase beyond threshold must be killed."""

    @pytest.mark.asyncio
    async def test_phase_stall_detected_and_kills(self):
        """HeartbeatTracker.is_stalled returns True when a phase exceeds its timeout,
        and the harness kills the subprocess."""
        from runsight_core.isolation.harness import HeartbeatTracker

        tracker = HeartbeatTracker(phase_timeout=0.05)  # 50ms

        hb = _make_heartbeat(phase="parsing")
        tracker.update(hb)

        # Wait beyond the threshold
        await asyncio.sleep(0.1)

        assert tracker.is_stalled is True

    @pytest.mark.asyncio
    async def test_phase_change_resets_stall_timer(self):
        """Changing to a new phase resets the stall timer."""
        from runsight_core.isolation.harness import HeartbeatTracker

        tracker = HeartbeatTracker(phase_timeout=0.05)

        tracker.update(_make_heartbeat(phase="parsing"))
        await asyncio.sleep(0.04)  # Almost at threshold

        # Phase change should reset
        tracker.update(_make_heartbeat(phase="executing"))
        await asyncio.sleep(0.02)

        assert tracker.is_stalled is False

    @pytest.mark.asyncio
    async def test_monitor_kills_on_phase_stall(self):
        """The harness monitor loop must detect phase stalls and kill the process.
        This requires the monitor to use the HeartbeatTracker and per-phase thresholds."""
        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            heartbeat_timeout=5.0,  # Long — so we don't trigger heartbeat stall
            phase_timeout=0.05,  # Short phase stall threshold
        )

        # Heartbeats arriving on time but always same phase
        hb = _make_heartbeat(phase="stuck_phase")
        hb_line = hb.model_dump_json().encode() + b"\n"

        call_count = 0

        async def readline_with_delay():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.02)  # Heartbeats arrive every 20ms
            if call_count > 10:
                return b""  # Safety exit
            return hb_line

        proc = MagicMock()
        proc.returncode = None
        proc.stderr = AsyncMock()
        proc.stderr.readline = AsyncMock(side_effect=readline_with_delay)
        proc.terminate = MagicMock()

        # The harness should detect phase stall and kill
        killed = await harness._monitor_heartbeats(proc, timeout=5.0)

        assert killed is True
        proc.terminate.assert_called()


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestStallThresholdsConfigurable:
    """Per-phase stall thresholds must be configurable via YAML block config."""

    def test_heartbeat_tracker_accepts_per_phase_thresholds(self):
        """HeartbeatTracker must accept a dict of per-phase thresholds,
        not just a single phase_timeout float."""
        from runsight_core.isolation.harness import HeartbeatTracker

        thresholds = {"parsing": 10, "llm_call": 120, "executing": 60}
        tracker = HeartbeatTracker(stall_thresholds=thresholds)

        assert tracker.stall_thresholds == thresholds

    def test_per_phase_threshold_used_for_stall_detection(self):
        """The tracker must use the specific phase threshold, not a global one."""
        from runsight_core.isolation.harness import HeartbeatTracker

        thresholds = {"fast_phase": 1, "slow_phase": 1000}
        tracker = HeartbeatTracker(stall_thresholds=thresholds)

        tracker.update(_make_heartbeat(phase="slow_phase"))
        # Even if we wait a bit, slow_phase has a 1000s threshold
        assert tracker.is_stalled is False

    def test_default_threshold_for_unknown_phase(self):
        """Phases not in stall_thresholds use the default phase_timeout."""
        from runsight_core.isolation.harness import HeartbeatTracker

        tracker = HeartbeatTracker(
            phase_timeout=0.01,  # Very short default
            stall_thresholds={"known_phase": 1000},
        )

        tracker.update(_make_heartbeat(phase="unknown_phase"))
        # unknown_phase uses the default 0.01s — should stall quickly
        import time

        time.sleep(0.05)
        assert tracker.is_stalled is True

    def test_harness_passes_stall_thresholds_to_tracker(self):
        """SubprocessHarness must pass stall_thresholds from block config
        to the HeartbeatTracker it creates."""
        thresholds = {"parsing": 10, "llm_call": 120}
        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            stall_thresholds=thresholds,
        )

        tracker = harness._create_heartbeat_tracker()
        assert tracker.stall_thresholds == thresholds


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestTimeoutSecondsConfigurable:
    """Per-block timeout_seconds from YAML, default 300s."""

    def test_base_block_def_default_timeout_is_300(self):
        """BaseBlockDef.timeout_seconds defaults to 300."""
        from runsight_core.yaml.schema import BaseBlockDef

        # Cannot instantiate BaseBlockDef directly (it's abstract via type field)
        assert BaseBlockDef.model_fields["timeout_seconds"].default == 300

    def test_context_envelope_carries_timeout(self):
        """ContextEnvelope.timeout_seconds must reflect the block's configured timeout."""
        envelope = _make_context_envelope(timeout_seconds=600)
        assert envelope.timeout_seconds == 600

    def test_harness_default_timeout_is_300(self):
        """SubprocessHarness default timeout_seconds is 300."""
        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        assert harness._timeout_seconds == 300


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestLlmCallPhaseNoStall:
    """llm_call phase at 90s must NOT trigger stall when default threshold is 120s."""

    def test_llm_call_90s_no_stall(self):
        """With default stall_thresholds, llm_call phase at 90s should NOT be stalled."""
        from runsight_core.isolation.harness import HeartbeatTracker

        # Default stall_thresholds should have llm_call >= 120s
        default_thresholds = {"llm_call": 120}
        tracker = HeartbeatTracker(stall_thresholds=default_thresholds)

        tracker.update(_make_heartbeat(phase="llm_call"))

        # Simulate 90 seconds elapsed by manipulating the internal timer
        tracker._phase_started_at = time.monotonic() - 90

        assert tracker.is_stalled is False, (
            "llm_call at 90s should NOT be stalled (threshold is 120s)"
        )


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestLlmCallPhaseStall:
    """llm_call phase at 130s must trigger stall when default threshold is 120s."""

    def test_llm_call_130s_triggers_stall(self):
        """With default stall_thresholds, llm_call phase at 130s must be stalled."""
        from runsight_core.isolation.harness import HeartbeatTracker

        default_thresholds = {"llm_call": 120}
        tracker = HeartbeatTracker(stall_thresholds=default_thresholds)

        tracker.update(_make_heartbeat(phase="llm_call"))

        # Simulate 130 seconds elapsed
        tracker._phase_started_at = time.monotonic() - 130

        assert tracker.is_stalled is True, "llm_call at 130s MUST be stalled (threshold is 120s)"

    @pytest.mark.asyncio
    async def test_llm_call_stall_kills_subprocess(self):
        """When llm_call phase exceeds threshold, the harness must kill the subprocess."""
        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            heartbeat_timeout=5.0,
            phase_timeout=60.0,
            stall_thresholds={"llm_call": 0.05},  # 50ms for fast test
        )

        hb = _make_heartbeat(phase="llm_call")
        hb_line = hb.model_dump_json().encode() + b"\n"

        call_count = 0

        async def readline_same_phase():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.02)
            if call_count > 10:
                return b""
            return hb_line

        proc = MagicMock()
        proc.returncode = None
        proc.stderr = AsyncMock()
        proc.stderr.readline = AsyncMock(side_effect=readline_same_phase)
        proc.terminate = MagicMock()

        killed = await harness._monitor_heartbeats(proc, timeout=5.0)

        assert killed is True
        proc.terminate.assert_called()
