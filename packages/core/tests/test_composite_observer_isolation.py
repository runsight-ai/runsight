"""CompositeObserver error isolation behavior.

Verifies that when one observer raises, other observers still fire,
and a warning is logged with the failing observer's class name.
"""

import logging
from unittest.mock import MagicMock

from runsight_core.observer import CompositeObserver
from runsight_core.state import WorkflowState


class BrokenObserver:
    """Observer that raises on every method call."""

    def on_workflow_start(self, workflow_name, state):
        raise RuntimeError("BrokenObserver.on_workflow_start exploded")

    def on_block_start(self, workflow_name, block_id, block_type):
        raise RuntimeError("BrokenObserver.on_block_start exploded")

    def on_block_complete(self, workflow_name, block_id, block_type, duration_s, state):
        raise RuntimeError("BrokenObserver.on_block_complete exploded")

    def on_block_error(self, workflow_name, block_id, block_type, duration_s, error):
        raise RuntimeError("BrokenObserver.on_block_error exploded")

    def on_workflow_complete(self, workflow_name, state, duration_s):
        raise RuntimeError("BrokenObserver.on_workflow_complete exploded")

    def on_workflow_error(self, workflow_name, error, duration_s):
        raise RuntimeError("BrokenObserver.on_workflow_error exploded")


class TestCompositeObserverIsolation:
    """Each observer call isolates failures so one observer cannot block others."""

    def test_on_workflow_start_first_fails_second_fires(self):
        broken = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken, good)

        state = WorkflowState()
        composite.on_workflow_start("observer_workflow", state)

        good.on_workflow_start.assert_called_once_with("observer_workflow", state)

    def test_on_block_start_first_fails_second_fires(self):
        broken = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken, good)

        composite.on_block_start("observer_workflow", "observer_block", "LinearBlock")

        good.on_block_start.assert_called_once_with(
            "observer_workflow", "observer_block", "LinearBlock"
        )

    def test_on_block_complete_first_fails_second_fires(self):
        broken = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken, good)

        state = WorkflowState()
        composite.on_block_complete(
            "observer_workflow", "observer_block", "LinearBlock", 1.5, state
        )

        good.on_block_complete.assert_called_once_with(
            "observer_workflow", "observer_block", "LinearBlock", 1.5, state
        )

    def test_on_block_error_first_fails_second_fires(self):
        broken = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken, good)

        err = ValueError("original error")
        composite.on_block_error("observer_workflow", "observer_block", "LinearBlock", 2.0, err)

        good.on_block_error.assert_called_once_with(
            "observer_workflow", "observer_block", "LinearBlock", 2.0, err
        )

    def test_on_workflow_complete_first_fails_second_fires(self):
        broken = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken, good)

        state = WorkflowState()
        composite.on_workflow_complete("observer_workflow", state, 5.0)

        good.on_workflow_complete.assert_called_once_with("observer_workflow", state, 5.0)

    def test_on_workflow_error_first_fails_second_fires(self):
        broken = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken, good)

        err = RuntimeError("workflow boom")
        composite.on_workflow_error("observer_workflow", err, 3.0)

        good.on_workflow_error.assert_called_once_with("observer_workflow", err, 3.0)


class TestCompositeObserverWarningLogged:
    """Observer failures log a warning with the observer class name."""

    def test_warning_includes_class_name(self, caplog):
        broken = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken, good)

        state = WorkflowState()
        with caplog.at_level(logging.WARNING):
            composite.on_workflow_start("observer_workflow", state)

        assert "BrokenObserver" in caplog.text

    def test_warning_includes_class_name_on_block_start(self, caplog):
        broken = BrokenObserver()
        composite = CompositeObserver(broken)

        with caplog.at_level(logging.WARNING):
            composite.on_block_start("observer_workflow", "observer_block", "LinearBlock")

        assert "BrokenObserver" in caplog.text

    def test_warning_logged_for_each_failing_observer(self, caplog):
        """Each failing observer produces its own warning."""
        broken1 = BrokenObserver()
        broken2 = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken1, broken2, good)

        state = WorkflowState()
        with caplog.at_level(logging.WARNING):
            composite.on_workflow_start("observer_workflow", state)

        # Two warnings, one per broken observer
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 2


class TestCompositeObserverMultipleFailures:
    """All healthy observers fire even if multiple observers fail."""

    def test_all_observers_fire_even_if_multiple_fail(self):
        broken1 = BrokenObserver()
        broken2 = BrokenObserver()
        good = MagicMock()
        composite = CompositeObserver(broken1, broken2, good)

        state = WorkflowState()
        composite.on_workflow_start("observer_workflow", state)

        good.on_workflow_start.assert_called_once_with("observer_workflow", state)

    def test_middle_observer_fails_last_still_fires(self):
        good1 = MagicMock()
        broken = BrokenObserver()
        good2 = MagicMock()
        composite = CompositeObserver(good1, broken, good2)

        composite.on_block_start("observer_workflow", "observer_block", "GateBlock")

        good1.on_block_start.assert_called_once_with(
            "observer_workflow", "observer_block", "GateBlock"
        )
        good2.on_block_start.assert_called_once_with(
            "observer_workflow", "observer_block", "GateBlock"
        )

    def test_all_six_methods_survive_broken_observer(self):
        """Smoke test: every on_* method tolerates a broken observer without raising."""
        broken = BrokenObserver()
        composite = CompositeObserver(broken)
        state = WorkflowState()
        err = ValueError("test")

        # None of these should raise
        composite.on_workflow_start("observer_workflow", state)
        composite.on_block_start("observer_workflow", "observer_block", "T")
        composite.on_block_complete("observer_workflow", "observer_block", "T", 1.0, state)
        composite.on_block_error("observer_workflow", "observer_block", "T", 1.0, err)
        composite.on_workflow_complete("observer_workflow", state, 1.0)
        composite.on_workflow_error("observer_workflow", err, 1.0)
