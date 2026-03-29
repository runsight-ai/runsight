"""Red tests for RUN-313: WorkflowObserver protocol extension — soul parameter.

Tests target the `soul` keyword argument on `on_block_start` and `on_block_complete`
across WorkflowObserver protocol, LoggingObserver, FileObserver, and CompositeObserver.

All tests should FAIL until the implementation exists.
"""

import logging
import tempfile
from pathlib import Path
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
    """A minimal Soul for testing."""
    return Soul(
        id="researcher_v1",
        role="Senior Researcher",
        system_prompt="You are a senior researcher.",
        model_name="gpt-4o",
    )


@pytest.fixture
def state():
    return WorkflowState(total_cost_usd=0.05, total_tokens=1500)


# ---------------------------------------------------------------------------
# 1. Protocol extension — on_block_start accepts soul kwarg
# ---------------------------------------------------------------------------


class TestProtocolOnBlockStartSoul:
    def test_logging_observer_on_block_start_accepts_soul(self, sample_soul, state):
        """LoggingObserver.on_block_start accepts soul keyword argument without error."""
        obs = LoggingObserver(level=logging.INFO)
        # Must not raise TypeError for unexpected keyword argument 'soul'
        obs.on_block_start("test_wf", "block_a", "LinearBlock", soul=sample_soul)

    def test_logging_observer_on_block_start_soul_default_none(self):
        """LoggingObserver.on_block_start works with soul=None (default)."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_start("test_wf", "block_a", "LinearBlock", soul=None)

    def test_file_observer_on_block_start_accepts_soul(self, sample_soul):
        """FileObserver.on_block_start accepts soul keyword argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            obs = FileObserver(str(Path(tmpdir) / "test.log"))
            obs.on_block_start("test_wf", "block_a", "LinearBlock", soul=sample_soul)

    def test_composite_observer_on_block_start_forwards_soul(self, sample_soul):
        """CompositeObserver.on_block_start passes soul to all children."""
        child1 = MagicMock()
        child2 = MagicMock()
        composite = CompositeObserver(child1, child2)

        composite.on_block_start("wf", "b1", "LinearBlock", soul=sample_soul)

        child1.on_block_start.assert_called_once_with("wf", "b1", "LinearBlock", soul=sample_soul)
        child2.on_block_start.assert_called_once_with("wf", "b1", "LinearBlock", soul=sample_soul)


# ---------------------------------------------------------------------------
# 2. Protocol extension — on_block_complete accepts soul kwarg
# ---------------------------------------------------------------------------


class TestProtocolOnBlockCompleteSoul:
    def test_logging_observer_on_block_complete_accepts_soul(self, sample_soul, state):
        """LoggingObserver.on_block_complete accepts soul keyword argument."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_complete("test_wf", "block_a", "LinearBlock", 2.5, state, soul=sample_soul)

    def test_logging_observer_on_block_complete_soul_default_none(self, state):
        """LoggingObserver.on_block_complete works with soul=None (default)."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_complete("test_wf", "block_a", "LinearBlock", 2.5, state, soul=None)

    def test_file_observer_on_block_complete_accepts_soul(self, sample_soul, state):
        """FileObserver.on_block_complete accepts soul keyword argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            obs = FileObserver(str(Path(tmpdir) / "test.log"))
            obs.on_block_complete("test_wf", "block_a", "LinearBlock", 2.5, state, soul=sample_soul)

    def test_composite_observer_on_block_complete_forwards_soul(self, sample_soul, state):
        """CompositeObserver.on_block_complete passes soul to all children."""
        child1 = MagicMock()
        child2 = MagicMock()
        composite = CompositeObserver(child1, child2)

        composite.on_block_complete("wf", "b1", "LinearBlock", 1.5, state, soul=sample_soul)

        child1.on_block_complete.assert_called_once_with(
            "wf", "b1", "LinearBlock", 1.5, state, soul=sample_soul
        )
        child2.on_block_complete.assert_called_once_with(
            "wf", "b1", "LinearBlock", 1.5, state, soul=sample_soul
        )


# ---------------------------------------------------------------------------
# 3. Backward compatibility — existing callers without soul still work
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_logging_observer_on_block_start_without_soul(self):
        """Existing callers of on_block_start without soul param still work."""
        obs = LoggingObserver(level=logging.INFO)
        # Old call signature — must still work (soul defaults to None)
        obs.on_block_start("wf", "b1", "LinearBlock")

    def test_logging_observer_on_block_complete_without_soul(self, state):
        """Existing callers of on_block_complete without soul param still work."""
        obs = LoggingObserver(level=logging.INFO)
        obs.on_block_complete("wf", "b1", "LinearBlock", 1.0, state)

    def test_file_observer_on_block_start_without_soul(self):
        """FileObserver backward compat — on_block_start without soul."""
        with tempfile.TemporaryDirectory() as tmpdir:
            obs = FileObserver(str(Path(tmpdir) / "test.log"))
            obs.on_block_start("wf", "b1", "LinearBlock")

    def test_file_observer_on_block_complete_without_soul(self, state):
        """FileObserver backward compat — on_block_complete without soul."""
        with tempfile.TemporaryDirectory() as tmpdir:
            obs = FileObserver(str(Path(tmpdir) / "test.log"))
            obs.on_block_complete("wf", "b1", "LinearBlock", 1.0, state)

    def test_composite_observer_on_block_start_without_soul(self):
        """CompositeObserver backward compat — on_block_start without soul."""
        child = MagicMock()
        composite = CompositeObserver(child)
        composite.on_block_start("wf", "b1", "LinearBlock")

    def test_composite_observer_on_block_complete_without_soul(self, state):
        """CompositeObserver backward compat — on_block_complete without soul."""
        child = MagicMock()
        composite = CompositeObserver(child)
        composite.on_block_complete("wf", "b1", "LinearBlock", 1.0, state)


# ---------------------------------------------------------------------------
# 4. Protocol definition includes soul in signature
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
        """The soul parameter defaults to None for backward compatibility."""
        import inspect

        sig_start = inspect.signature(WorkflowObserver.on_block_start)
        sig_complete = inspect.signature(WorkflowObserver.on_block_complete)

        assert sig_start.parameters["soul"].default is None
        assert sig_complete.parameters["soul"].default is None
