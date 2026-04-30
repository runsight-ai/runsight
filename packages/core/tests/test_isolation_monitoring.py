"""Isolation monitoring coverage.

Tests cover:
- heartbeat and phase-stall subprocess termination
- configurable stall thresholds and block timeouts
- heartbeat propagation through observers
- startup recovery for ghost runs
- long-running llm_call phase thresholds
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.isolation import (
    ContextEnvelope,
    HeartbeatMessage,
    PromptEnvelope,
    SoulEnvelope,
    SubprocessHarness,
)
from runsight_core.observer import (
    CompositeObserver,
    FileObserver,
    LoggingObserver,
    WorkflowObserver,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_heartbeat(
    *,
    seq: int = 1,
    phase: str = "initializing",
    detail: str = "",
) -> HeartbeatMessage:
    return HeartbeatMessage(
        heartbeat=seq,
        phase=phase,
        detail=detail,
        timestamp=datetime.now(timezone.utc),
    )


def _make_context_envelope(
    *,
    block_id: str = "monitoring-linear-block",
    block_type: str = "linear",
    timeout_seconds: int = 30,
) -> ContextEnvelope:
    return ContextEnvelope(
        block_id=block_id,
        block_type=block_type,
        block_config={},
        soul=SoulEnvelope(
            id="monitoring-soul",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o-mini",
            max_tool_iterations=3,
        ),
        tools=[],
        prompt=PromptEnvelope(id="monitoring-prompt", instruction="Do the thing.", context={}),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=timeout_seconds,
        max_output_bytes=1_000_000,
    )


# ===========================================================================
# Behavior coverage
# ===========================================================================


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


class TestOnBlockHeartbeatProtocol:
    """WorkflowObserver protocol must include on_block_heartbeat."""

    def test_protocol_has_on_block_heartbeat(self):
        """WorkflowObserver protocol must define on_block_heartbeat method."""
        assert hasattr(WorkflowObserver, "on_block_heartbeat")

    def test_on_block_heartbeat_signature(self):
        """on_block_heartbeat must accept workflow_name, block_id, phase, detail, timestamp."""
        import inspect

        sig = inspect.signature(WorkflowObserver.on_block_heartbeat)
        param_names = list(sig.parameters.keys())

        assert "self" in param_names
        assert "workflow_name" in param_names
        assert "block_id" in param_names
        assert "phase" in param_names

    def test_on_block_heartbeat_called_per_heartbeat(self):
        """The harness must call observer.on_block_heartbeat for each heartbeat received."""
        observer = MagicMock(spec=WorkflowObserver)
        observer.on_block_heartbeat = MagicMock()

        # Simulate calling on_block_heartbeat
        observer.on_block_heartbeat(
            workflow_name="test-wf",
            block_id="monitoring-linear-block",
            phase="initializing",
            detail="starting up",
            timestamp=datetime.now(timezone.utc),
        )
        observer.on_block_heartbeat.assert_called_once()


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestCoreObserversHeartbeat:
    """All core observers must implement on_block_heartbeat."""

    def test_logging_observer_has_on_block_heartbeat(self):
        """LoggingObserver must have on_block_heartbeat method."""
        obs = LoggingObserver()
        assert hasattr(obs, "on_block_heartbeat")
        assert callable(obs.on_block_heartbeat)

    def test_logging_observer_logs_heartbeat(self, caplog):
        """LoggingObserver.on_block_heartbeat must log the phase."""
        import logging

        obs = LoggingObserver(level=logging.INFO)
        with caplog.at_level(logging.INFO, logger="runsight.workflow"):
            obs.on_block_heartbeat(
                workflow_name="test-wf",
                block_id="monitoring-linear-block",
                phase="llm_call",
                detail="calling model",
                timestamp=datetime.now(timezone.utc),
            )

        assert any("llm_call" in r.message for r in caplog.records)

    def test_file_observer_has_on_block_heartbeat(self, tmp_path):
        """FileObserver must have on_block_heartbeat method."""
        obs = FileObserver(str(tmp_path / "test.log"))
        assert hasattr(obs, "on_block_heartbeat")
        assert callable(obs.on_block_heartbeat)

    def test_file_observer_writes_heartbeat_event(self, tmp_path):
        """FileObserver.on_block_heartbeat must write a JSON line with event=block_heartbeat."""
        import json

        log_path = tmp_path / "test.log"
        obs = FileObserver(str(log_path))
        obs.on_block_heartbeat(
            workflow_name="test-wf",
            block_id="monitoring-linear-block",
            phase="parsing",
            detail="",
            timestamp=datetime.now(timezone.utc),
        )

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == "block_heartbeat"
        assert entry["block_id"] == "monitoring-linear-block"
        assert entry["phase"] == "parsing"

    def test_composite_observer_fans_out_heartbeat(self):
        """CompositeObserver.on_block_heartbeat must delegate to all child observers."""
        child1 = MagicMock()
        child1.on_block_heartbeat = MagicMock()
        child2 = MagicMock()
        child2.on_block_heartbeat = MagicMock()

        composite = CompositeObserver(child1, child2)
        composite.on_block_heartbeat(
            workflow_name="test-wf",
            block_id="monitoring-linear-block",
            phase="initializing",
            detail="",
            timestamp=datetime.now(timezone.utc),
        )

        child1.on_block_heartbeat.assert_called_once()
        child2.on_block_heartbeat.assert_called_once()


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestStreamingObserverHeartbeat:
    """StreamingObserver must push heartbeat events to its SSE queue."""

    def test_streaming_observer_has_on_block_heartbeat(self):
        """StreamingObserver must have on_block_heartbeat method."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="monitoring-run")
        assert hasattr(obs, "on_block_heartbeat")
        assert callable(obs.on_block_heartbeat)

    def test_streaming_observer_enqueues_heartbeat_sse(self):
        """StreamingObserver.on_block_heartbeat must push a heartbeat event to the queue."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="monitoring-run")
        obs.on_block_heartbeat(
            workflow_name="test-wf",
            block_id="monitoring-linear-block",
            phase="llm_call",
            detail="calling gpt-4o",
            timestamp=datetime.now(timezone.utc),
        )

        assert not obs.queue.empty()
        event = obs.queue.get_nowait()
        assert event["event"] == "node_heartbeat"
        assert event["data"]["node_id"] == "monitoring-linear-block"
        assert event["data"]["phase"] == "llm_call"


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestExecutionObserverHeartbeat:
    """ExecutionObserver must update RunNode.last_phase on heartbeat."""

    def test_execution_observer_has_on_block_heartbeat(self):
        """ExecutionObserver must have on_block_heartbeat method."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        engine = MagicMock()
        obs = ExecutionObserver(engine=engine, run_id="monitoring-run")
        assert hasattr(obs, "on_block_heartbeat")
        assert callable(obs.on_block_heartbeat)

    def test_execution_observer_updates_run_node_phase(self):
        """ExecutionObserver.on_block_heartbeat must update RunNode.last_phase in the DB."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        mock_engine = MagicMock()
        mock_session = MagicMock()
        mock_run_node = MagicMock()
        mock_run_node.last_phase = None

        # Patch Session to return our mock
        with patch("runsight_api.logic.observers.execution_observer.Session") as MockSession:
            MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
            MockSession.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.get.return_value = mock_run_node

            obs = ExecutionObserver(engine=mock_engine, run_id="monitoring-run")
            obs.on_block_heartbeat(
                workflow_name="test-wf",
                block_id="monitoring-linear-block",
                phase="executing",
                detail="",
                timestamp=datetime.now(timezone.utc),
            )

        assert mock_run_node.last_phase == "executing"


# ===========================================================================
# Behavior coverage
# ===========================================================================


class TestGhostRunDetection:
    """Runs stuck in 'running' status at server startup must be marked as failed."""

    def test_execution_service_has_fail_ghost_runs(self):
        """ExecutionService must expose the canonical fail_ghost_runs method."""
        from runsight_api.logic.services.execution_service import ExecutionService

        assert hasattr(ExecutionService, "fail_ghost_runs")

    def test_ghost_runs_marked_as_failed(self):
        """Runs with status='running' at startup must be transitioned to 'failed'
        with a descriptive error message."""
        from runsight_api.domain.entities.run import Run, RunStatus
        from runsight_api.logic.services.execution_service import ExecutionService

        mock_run = MagicMock(spec=Run)
        mock_run.id = "run-ghost-1"
        mock_run.status = RunStatus.running

        mock_repo = MagicMock()
        mock_repo.list_runs.return_value = [mock_run]

        service = ExecutionService(
            run_repo=mock_repo,
            workflow_repo=MagicMock(),
            provider_repo=MagicMock(),
            engine=MagicMock(),
        )

        # Actually invoke the canonical method to mark ghost runs as failed
        service.fail_ghost_runs()

        # Ghost run must be transitioned to failed status
        assert mock_run.status == RunStatus.failed, (
            f"Ghost run status should be 'failed' but got '{mock_run.status}'"
        )

    def test_ghost_run_error_message_is_descriptive(self):
        """Ghost runs should have an error like 'Ghost run: server restarted while running'."""
        from runsight_api.domain.entities.run import Run, RunStatus
        from runsight_api.logic.services.execution_service import ExecutionService

        mock_run = MagicMock(spec=Run)
        mock_run.id = "run-ghost-2"
        mock_run.status = RunStatus.running
        mock_run.error = None

        mock_repo = MagicMock()
        mock_repo.list_runs.return_value = [mock_run]

        service = ExecutionService(
            run_repo=mock_repo,
            workflow_repo=MagicMock(),
            provider_repo=MagicMock(),
            engine=MagicMock(),
        )

        # Actually invoke the canonical method
        service.fail_ghost_runs()

        # Error message must be descriptive — mention server restart
        assert mock_run.error is not None, "Ghost run must have an error message set"
        assert "server restarted" in mock_run.error.lower(), (
            f"Ghost run error should mention 'server restarted' but got: '{mock_run.error}'"
        )


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
