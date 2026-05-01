"""WorkflowObserver soul keyword propagation across logging, file, and composite observers."""

import logging
from unittest.mock import MagicMock

import pytest
from runsight_core.observer import (
    CompositeObserver,
    FileObserver,
    LoggingObserver,
    WorkflowObserver,
)
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_soul():
    """A minimal Soul for observer propagation tests."""
    return Soul(
        id="observer_researcher",
        kind="soul",
        name="Senior Researcher",
        role="Senior Researcher",
        system_prompt="You are a senior researcher.",
    )


@pytest.fixture
def state():
    return WorkflowState(total_cost_usd=0.05, total_tokens=1500)


# ---------------------------------------------------------------------------
# on_block_start accepts soul keyword
# ---------------------------------------------------------------------------


class TestProtocolOnBlockStartSoul:
    def test_logging_observer_on_block_start_accepts_soul(self, sample_soul, state):
        """LoggingObserver.on_block_start accepts soul keyword argument without error."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_start(
            "observer_soul_workflow", "analysis_block", "LinearBlock", soul=sample_soul
        )

    def test_logging_observer_on_block_start_soul_default_none(self):
        """LoggingObserver.on_block_start works with soul=None (default)."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_start("observer_soul_workflow", "analysis_block", "LinearBlock", soul=None)

    def test_file_observer_on_block_start_accepts_soul(self, sample_soul, tmp_path):
        """FileObserver.on_block_start accepts soul keyword argument."""
        obs = FileObserver(str(tmp_path / "observer.log"))
        obs.on_block_start(
            "observer_soul_workflow",
            "analysis_block",
            "LinearBlock",
            soul=sample_soul,
        )

    def test_composite_observer_on_block_start_forwards_soul(self, sample_soul):
        """CompositeObserver.on_block_start passes soul to all children."""
        logging_child = MagicMock()
        file_child = MagicMock()
        composite = CompositeObserver(logging_child, file_child)

        composite.on_block_start(
            "observer_soul_workflow", "analysis_block", "LinearBlock", soul=sample_soul
        )

        logging_child.on_block_start.assert_called_once_with(
            "observer_soul_workflow", "analysis_block", "LinearBlock", soul=sample_soul
        )
        file_child.on_block_start.assert_called_once_with(
            "observer_soul_workflow", "analysis_block", "LinearBlock", soul=sample_soul
        )


# ---------------------------------------------------------------------------
# on_block_complete accepts soul keyword
# ---------------------------------------------------------------------------


class TestProtocolOnBlockCompleteSoul:
    def test_logging_observer_on_block_complete_accepts_soul(self, sample_soul, state):
        """LoggingObserver.on_block_complete accepts soul keyword argument."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_complete(
            "observer_soul_workflow",
            "analysis_block",
            "LinearBlock",
            2.5,
            state,
            soul=sample_soul,
        )

    def test_logging_observer_on_block_complete_soul_default_none(self, state):
        """LoggingObserver.on_block_complete works with soul=None (default)."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_complete(
            "observer_soul_workflow", "analysis_block", "LinearBlock", 2.5, state, soul=None
        )

    def test_file_observer_on_block_complete_accepts_soul(self, sample_soul, state, tmp_path):
        """FileObserver.on_block_complete accepts soul keyword argument."""
        obs = FileObserver(str(tmp_path / "observer.log"))
        obs.on_block_complete(
            "observer_soul_workflow",
            "analysis_block",
            "LinearBlock",
            2.5,
            state,
            soul=sample_soul,
        )

    def test_composite_observer_on_block_complete_forwards_soul(self, sample_soul, state):
        """CompositeObserver.on_block_complete passes soul to all children."""
        logging_child = MagicMock()
        file_child = MagicMock()
        composite = CompositeObserver(logging_child, file_child)

        composite.on_block_complete(
            "observer_soul_workflow",
            "analysis_block",
            "LinearBlock",
            1.5,
            state,
            soul=sample_soul,
        )

        logging_child.on_block_complete.assert_called_once_with(
            "observer_soul_workflow",
            "analysis_block",
            "LinearBlock",
            1.5,
            state,
            soul=sample_soul,
        )
        file_child.on_block_complete.assert_called_once_with(
            "observer_soul_workflow",
            "analysis_block",
            "LinearBlock",
            1.5,
            state,
            soul=sample_soul,
        )


# ---------------------------------------------------------------------------
# Existing callers without soul still work
# ---------------------------------------------------------------------------


class TestObserverCallsWithoutSoul:
    def test_logging_observer_on_block_start_without_soul(self):
        """Existing callers of on_block_start without soul param still work."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_start("observer_soul_workflow", "analysis_block", "LinearBlock")

    def test_logging_observer_on_block_complete_without_soul(self, state):
        """Existing callers of on_block_complete without soul param still work."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_complete("observer_soul_workflow", "analysis_block", "LinearBlock", 1.0, state)

    def test_file_observer_on_block_start_without_soul(self, tmp_path):
        """FileObserver accepts on_block_start without soul."""
        obs = FileObserver(str(tmp_path / "observer.log"))
        obs.on_block_start("observer_soul_workflow", "analysis_block", "LinearBlock")

    def test_file_observer_on_block_complete_without_soul(self, state, tmp_path):
        """FileObserver accepts on_block_complete without soul."""
        obs = FileObserver(str(tmp_path / "observer.log"))
        obs.on_block_complete("observer_soul_workflow", "analysis_block", "LinearBlock", 1.0, state)

    def test_composite_observer_on_block_start_without_soul(self):
        """CompositeObserver accepts on_block_start without soul."""
        logging_child = MagicMock()
        composite = CompositeObserver(logging_child)
        composite.on_block_start("observer_soul_workflow", "analysis_block", "LinearBlock")

    def test_composite_observer_on_block_complete_without_soul(self, state):
        """CompositeObserver accepts on_block_complete without soul."""
        logging_child = MagicMock()
        composite = CompositeObserver(logging_child)
        composite.on_block_complete(
            "observer_soul_workflow", "analysis_block", "LinearBlock", 1.0, state
        )


# ---------------------------------------------------------------------------
# Protocol definition includes soul in signature
# ---------------------------------------------------------------------------


class TestProtocolSignature:
    def test_protocol_on_block_start_has_soul_parameter(self):
        """WorkflowObserver protocol's on_block_start declares soul parameter."""
        import inspect

        sig = inspect.signature(WorkflowObserver.on_block_start)
        assert "soul" in sig.parameters, (
            "WorkflowObserver.on_block_start must declare 'soul' parameter"
        )

    def test_protocol_on_block_complete_has_soul_parameter(self):
        """WorkflowObserver protocol's on_block_complete declares soul parameter."""
        import inspect

        sig = inspect.signature(WorkflowObserver.on_block_complete)
        assert "soul" in sig.parameters, (
            "WorkflowObserver.on_block_complete must declare 'soul' parameter"
        )

    def test_protocol_soul_parameter_is_keyword_only(self):
        """The soul parameter is keyword-only (enforced by *)."""
        import inspect

        sig_start = inspect.signature(WorkflowObserver.on_block_start)
        sig_complete = inspect.signature(WorkflowObserver.on_block_complete)

        assert sig_start.parameters["soul"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig_complete.parameters["soul"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_protocol_soul_default_is_none(self):
        """The soul parameter defaults to None."""
        import inspect

        sig_start = inspect.signature(WorkflowObserver.on_block_start)
        sig_complete = inspect.signature(WorkflowObserver.on_block_complete)

        assert sig_start.parameters["soul"].default is None
        assert sig_complete.parameters["soul"].default is None
