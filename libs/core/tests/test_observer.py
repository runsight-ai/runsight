"""Tests for WorkflowObserver protocol and built-in implementations."""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


from runsight_core.observer import (
    WorkflowObserver,
    LoggingObserver,
    FileObserver,
    CompositeObserver,
)
from runsight_core.state import WorkflowState


class TestLoggingObserver:
    def test_on_workflow_start(self, caplog):
        obs = LoggingObserver(level=logging.INFO)
        state = WorkflowState()
        with caplog.at_level(logging.INFO, logger="runsight.workflow"):
            obs.on_workflow_start("test_wf", state)
        assert "test_wf" in caplog.text
        assert "Workflow started" in caplog.text

    def test_on_block_complete_includes_cost(self, caplog):
        obs = LoggingObserver(level=logging.INFO)
        state = WorkflowState(total_cost_usd=0.05, total_tokens=1500)
        with caplog.at_level(logging.INFO, logger="runsight.workflow"):
            obs.on_block_complete("test_wf", "block1", "LinearBlock", 2.5, state)
        assert "block1" in caplog.text
        assert "2.5s" in caplog.text
        assert "$0.0500" in caplog.text

    def test_on_block_error_logs_error_level(self, caplog):
        obs = LoggingObserver(level=logging.INFO)
        err = ValueError("something broke")
        with caplog.at_level(logging.ERROR, logger="runsight.workflow"):
            obs.on_block_error("test_wf", "block1", "GateBlock", 1.0, err)
        assert "block1" in caplog.text
        assert "something broke" in caplog.text


class TestFileObserver:
    def test_writes_json_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test.log")
            obs = FileObserver(log_path)

            state = WorkflowState()
            obs.on_workflow_start("test_wf", state)
            obs.on_block_start("test_wf", "b1", "LinearBlock")

            lines = Path(log_path).read_text().strip().split("\n")
            assert len(lines) == 2

            event1 = json.loads(lines[0])
            assert event1["event"] == "workflow_start"
            assert event1["workflow"] == "test_wf"
            assert "ts" in event1

            event2 = json.loads(lines[1])
            assert event2["event"] == "block_start"
            assert event2["block_id"] == "b1"

    def test_truncates_on_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test.log")
            Path(log_path).write_text("old content\n")

            FileObserver(log_path)
            assert Path(log_path).read_text() == ""

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "deep" / "nested" / "test.log")
            obs = FileObserver(log_path)
            obs.on_workflow_start("wf", WorkflowState())
            assert Path(log_path).exists()

    def test_block_complete_includes_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test.log")
            obs = FileObserver(log_path)

            state = WorkflowState(total_cost_usd=0.123, total_tokens=5000)
            obs.on_block_complete("wf", "b1", "DebateBlock", 3.14, state)

            line = Path(log_path).read_text().strip()
            event = json.loads(line)
            assert event["duration_s"] == 3.14
            assert event["cost_usd"] == 0.123
            assert event["tokens"] == 5000


class TestCompositeObserver:
    def test_delegates_to_all(self):
        obs1 = MagicMock()
        obs2 = MagicMock()
        composite = CompositeObserver(obs1, obs2)

        state = WorkflowState()
        composite.on_workflow_start("wf", state)

        obs1.on_workflow_start.assert_called_once_with("wf", state)
        obs2.on_workflow_start.assert_called_once_with("wf", state)

    def test_delegates_block_events(self):
        obs1 = MagicMock()
        composite = CompositeObserver(obs1)

        composite.on_block_start("wf", "b1", "LinearBlock")
        obs1.on_block_start.assert_called_once_with("wf", "b1", "LinearBlock")

        state = WorkflowState()
        composite.on_block_complete("wf", "b1", "LinearBlock", 1.0, state)
        obs1.on_block_complete.assert_called_once_with("wf", "b1", "LinearBlock", 1.0, state)

        err = ValueError("fail")
        composite.on_block_error("wf", "b1", "LinearBlock", 1.0, err)
        obs1.on_block_error.assert_called_once_with("wf", "b1", "LinearBlock", 1.0, err)


class TestWorkflowObserverProtocol:
    def test_logging_observer_is_workflow_observer(self):
        assert isinstance(LoggingObserver(), WorkflowObserver)

    def test_file_observer_is_workflow_observer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            obs = FileObserver(str(Path(tmpdir) / "test.log"))
            assert isinstance(obs, WorkflowObserver)

    def test_composite_observer_is_workflow_observer(self):
        assert isinstance(CompositeObserver(), WorkflowObserver)
