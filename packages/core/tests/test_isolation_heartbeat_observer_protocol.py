"""Isolation heartbeat observer protocol behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
from runsight_core.observer import (
    CompositeObserver,
    FileObserver,
    LoggingObserver,
    WorkflowObserver,
)


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
