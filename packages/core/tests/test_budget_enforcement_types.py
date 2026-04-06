"""
Failing tests for RUN-710: BudgetKilledException + BudgetWarningEvent +
BudgetKillEvent + _active_budget ContextVar.

Foundation ticket for the RUN-708 budget enforcement epic.

Tests cover:
- Module importability: runsight_core.budget_enforcement exists
- BudgetKilledException is a subclass of Exception
- BudgetKilledException carries scope, block_id, limit_kind, limit_value, actual_value
- str(exc) produces a human-readable message for scope="block" and scope="workflow"
- BudgetKilledException can be raised and caught normally
- BudgetWarningEvent is a valid Pydantic BaseModel with correct fields
- BudgetKillEvent is a valid Pydantic BaseModel with correct fields
- _active_budget ContextVar defined with default=None
"""

from __future__ import annotations

import contextvars

import pytest
from pydantic import BaseModel

# ===========================================================================
# 1. Module importability
# ===========================================================================


class TestModuleImportability:
    """budget_enforcement.py is importable from runsight_core."""

    def test_budget_enforcement_module_importable(self):
        """Importing budget_enforcement should not raise."""
        from runsight_core import budget_enforcement  # noqa: F401

    def test_budget_killed_exception_importable(self):
        """BudgetKilledException should be importable."""
        from runsight_core.budget_enforcement import BudgetKilledException  # noqa: F401

    def test_budget_warning_event_importable(self):
        """BudgetWarningEvent should be importable."""
        from runsight_core.budget_enforcement import BudgetWarningEvent  # noqa: F401

    def test_budget_kill_event_importable(self):
        """BudgetKillEvent should be importable."""
        from runsight_core.budget_enforcement import BudgetKillEvent  # noqa: F401

    def test_active_budget_contextvar_importable(self):
        """_active_budget ContextVar should be importable."""
        from runsight_core.budget_enforcement import _active_budget  # noqa: F401


# ===========================================================================
# 2. BudgetKilledException — class hierarchy
# ===========================================================================


class TestBudgetKilledExceptionHierarchy:
    """BudgetKilledException must be a subclass of Exception."""

    def test_is_exception_subclass(self):
        from runsight_core.budget_enforcement import BudgetKilledException

        assert issubclass(BudgetKilledException, Exception)

    def test_is_not_base_exception_directly(self):
        """It should subclass Exception, not just BaseException."""
        from runsight_core.budget_enforcement import BudgetKilledException

        # This confirms it participates in normal except Exception handling
        assert issubclass(BudgetKilledException, Exception)


# ===========================================================================
# 3. BudgetKilledException — attributes
# ===========================================================================


class TestBudgetKilledExceptionAttributes:
    """BudgetKilledException carries scope, block_id, limit_kind, limit_value, actual_value."""

    def _make_block_exc(self):
        from runsight_core.budget_enforcement import BudgetKilledException

        return BudgetKilledException(
            scope="block",
            block_id="research",
            limit_kind="cost_usd",
            limit_value=0.50,
            actual_value=0.62,
        )

    def _make_workflow_exc(self):
        from runsight_core.budget_enforcement import BudgetKilledException

        return BudgetKilledException(
            scope="workflow",
            block_id=None,
            limit_kind="timeout",
            limit_value=300.0,
            actual_value=312.5,
        )

    def test_scope_attribute_block(self):
        exc = self._make_block_exc()
        assert exc.scope == "block"

    def test_scope_attribute_workflow(self):
        exc = self._make_workflow_exc()
        assert exc.scope == "workflow"

    def test_block_id_attribute(self):
        exc = self._make_block_exc()
        assert exc.block_id == "research"

    def test_block_id_none_for_workflow(self):
        exc = self._make_workflow_exc()
        assert exc.block_id is None

    def test_limit_kind_cost_usd(self):
        exc = self._make_block_exc()
        assert exc.limit_kind == "cost_usd"

    def test_limit_kind_timeout(self):
        exc = self._make_workflow_exc()
        assert exc.limit_kind == "timeout"

    def test_limit_kind_token_cap(self):
        from runsight_core.budget_enforcement import BudgetKilledException

        exc = BudgetKilledException(
            scope="block",
            block_id="summarize",
            limit_kind="token_cap",
            limit_value=10000.0,
            actual_value=12345.0,
        )
        assert exc.limit_kind == "token_cap"

    def test_limit_value_attribute(self):
        exc = self._make_block_exc()
        assert exc.limit_value == 0.50

    def test_actual_value_attribute(self):
        exc = self._make_block_exc()
        assert exc.actual_value == 0.62


# ===========================================================================
# 4. BudgetKilledException — str() representation
# ===========================================================================


class TestBudgetKilledExceptionStr:
    """str(exc) produces a human-readable message."""

    def test_block_scope_str_contains_block_name(self):
        """
        Given scope="block", block_id="research"
        When str(exc) is evaluated
        Then message contains "block 'research'"
        """
        from runsight_core.budget_enforcement import BudgetKilledException

        exc = BudgetKilledException(
            scope="block",
            block_id="research",
            limit_kind="cost_usd",
            limit_value=0.50,
            actual_value=0.62,
        )
        msg = str(exc)
        assert "block 'research'" in msg

    def test_block_scope_str_contains_values(self):
        """
        Acceptance scenario:
        Given BudgetKilledException(scope="block", block_id="research",
              limit_kind="cost_usd", limit_value=0.50, actual_value=0.62)
        When str(exc) is evaluated
        Then message contains "cost_usd=0.6200 > cap=0.5000"
        """
        from runsight_core.budget_enforcement import BudgetKilledException

        exc = BudgetKilledException(
            scope="block",
            block_id="research",
            limit_kind="cost_usd",
            limit_value=0.50,
            actual_value=0.62,
        )
        msg = str(exc)
        assert "cost_usd=0.6200 > cap=0.5000" in msg

    def test_workflow_scope_str_contains_workflow(self):
        """
        Given scope="workflow"
        When str(exc) is evaluated
        Then message contains "workflow"
        """
        from runsight_core.budget_enforcement import BudgetKilledException

        exc = BudgetKilledException(
            scope="workflow",
            block_id=None,
            limit_kind="timeout",
            limit_value=300.0,
            actual_value=312.5,
        )
        msg = str(exc)
        assert "workflow" in msg

    def test_workflow_scope_str_contains_limit_values(self):
        from runsight_core.budget_enforcement import BudgetKilledException

        exc = BudgetKilledException(
            scope="workflow",
            block_id=None,
            limit_kind="timeout",
            limit_value=300.0,
            actual_value=312.5,
        )
        msg = str(exc)
        assert "timeout" in msg
        assert "312.5" in msg or "312.50" in msg

    def test_str_is_nonempty(self):
        from runsight_core.budget_enforcement import BudgetKilledException

        exc = BudgetKilledException(
            scope="block",
            block_id="x",
            limit_kind="token_cap",
            limit_value=1000.0,
            actual_value=1500.0,
        )
        assert len(str(exc)) > 0


# ===========================================================================
# 5. BudgetKilledException — raise/catch
# ===========================================================================


class TestBudgetKilledExceptionRaiseCatch:
    """Exception can be raised and caught normally."""

    def test_raise_and_catch_with_pytest_raises(self):
        from runsight_core.budget_enforcement import BudgetKilledException

        with pytest.raises(BudgetKilledException) as exc_info:
            raise BudgetKilledException(
                scope="block",
                block_id="research",
                limit_kind="cost_usd",
                limit_value=0.50,
                actual_value=0.62,
            )
        assert exc_info.value.scope == "block"
        assert exc_info.value.block_id == "research"
        assert exc_info.value.limit_value == 0.50

    def test_catchable_as_exception(self):
        """Can be caught by a bare 'except Exception' clause."""
        from runsight_core.budget_enforcement import BudgetKilledException

        caught = False
        try:
            raise BudgetKilledException(
                scope="workflow",
                block_id=None,
                limit_kind="timeout",
                limit_value=60.0,
                actual_value=75.0,
            )
        except Exception:
            caught = True
        assert caught


# ===========================================================================
# 6. BudgetWarningEvent — Pydantic model
# ===========================================================================


class TestBudgetWarningEvent:
    """BudgetWarningEvent is a valid Pydantic BaseModel with correct fields."""

    def test_is_pydantic_base_model(self):
        from runsight_core.budget_enforcement import BudgetWarningEvent

        assert issubclass(BudgetWarningEvent, BaseModel)

    def test_instantiation_block_scope(self):
        from runsight_core.budget_enforcement import BudgetWarningEvent

        evt = BudgetWarningEvent(
            scope="block",
            block_id="research",
            limit_kind="cost_usd",
            pct_used=0.85,
            current_value=0.425,
            cap_value=0.50,
            workflow_name="my-workflow",
        )
        assert evt.scope == "block"
        assert evt.block_id == "research"
        assert evt.limit_kind == "cost_usd"
        assert evt.pct_used == 0.85
        assert evt.current_value == 0.425
        assert evt.cap_value == 0.50
        assert evt.workflow_name == "my-workflow"

    def test_instantiation_workflow_scope(self):
        from runsight_core.budget_enforcement import BudgetWarningEvent

        evt = BudgetWarningEvent(
            scope="workflow",
            block_id=None,
            limit_kind="timeout",
            pct_used=0.90,
            current_value=270.0,
            cap_value=300.0,
            workflow_name="pipeline-v2",
        )
        assert evt.scope == "workflow"
        assert evt.block_id is None

    def test_block_id_defaults_to_none(self):
        """block_id should default to None when not provided."""
        from runsight_core.budget_enforcement import BudgetWarningEvent

        evt = BudgetWarningEvent(
            scope="workflow",
            limit_kind="token_cap",
            pct_used=0.75,
            current_value=7500.0,
            cap_value=10000.0,
            workflow_name="test",
        )
        assert evt.block_id is None

    def test_has_all_required_fields(self):
        from runsight_core.budget_enforcement import BudgetWarningEvent

        fields = BudgetWarningEvent.model_fields
        expected = {
            "scope",
            "block_id",
            "limit_kind",
            "pct_used",
            "current_value",
            "cap_value",
            "workflow_name",
        }
        assert expected == set(fields.keys())

    def test_scope_literal_values(self):
        """scope must accept 'block' and 'workflow'."""
        from runsight_core.budget_enforcement import BudgetWarningEvent

        for scope_val in ("block", "workflow"):
            evt = BudgetWarningEvent(
                scope=scope_val,
                limit_kind="cost_usd",
                pct_used=0.5,
                current_value=1.0,
                cap_value=2.0,
                workflow_name="w",
            )
            assert evt.scope == scope_val

    def test_limit_kind_literal_values(self):
        """limit_kind must accept 'timeout', 'cost_usd', 'token_cap'."""
        from runsight_core.budget_enforcement import BudgetWarningEvent

        for kind in ("timeout", "cost_usd", "token_cap"):
            evt = BudgetWarningEvent(
                scope="block",
                block_id="b1",
                limit_kind=kind,
                pct_used=0.5,
                current_value=1.0,
                cap_value=2.0,
                workflow_name="w",
            )
            assert evt.limit_kind == kind


# ===========================================================================
# 7. BudgetKillEvent — Pydantic model
# ===========================================================================


class TestBudgetKillEvent:
    """BudgetKillEvent is a valid Pydantic BaseModel with correct fields."""

    def test_is_pydantic_base_model(self):
        from runsight_core.budget_enforcement import BudgetKillEvent

        assert issubclass(BudgetKillEvent, BaseModel)

    def test_instantiation_block_scope(self):
        from runsight_core.budget_enforcement import BudgetKillEvent

        evt = BudgetKillEvent(
            scope="block",
            block_id="research",
            limit_kind="cost_usd",
            current_value=0.62,
            cap_value=0.50,
            workflow_name="my-workflow",
        )
        assert evt.scope == "block"
        assert evt.block_id == "research"
        assert evt.limit_kind == "cost_usd"
        assert evt.current_value == 0.62
        assert evt.cap_value == 0.50
        assert evt.workflow_name == "my-workflow"

    def test_instantiation_workflow_scope(self):
        from runsight_core.budget_enforcement import BudgetKillEvent

        evt = BudgetKillEvent(
            scope="workflow",
            block_id=None,
            limit_kind="timeout",
            current_value=312.5,
            cap_value=300.0,
            workflow_name="pipeline-v2",
        )
        assert evt.scope == "workflow"
        assert evt.block_id is None

    def test_block_id_defaults_to_none(self):
        """block_id should default to None when not provided."""
        from runsight_core.budget_enforcement import BudgetKillEvent

        evt = BudgetKillEvent(
            scope="workflow",
            limit_kind="token_cap",
            current_value=12000.0,
            cap_value=10000.0,
            workflow_name="test",
        )
        assert evt.block_id is None

    def test_has_all_required_fields(self):
        from runsight_core.budget_enforcement import BudgetKillEvent

        fields = BudgetKillEvent.model_fields
        expected = {
            "scope",
            "block_id",
            "limit_kind",
            "current_value",
            "cap_value",
            "workflow_name",
        }
        assert expected == set(fields.keys())

    def test_kill_event_has_no_pct_used(self):
        """BudgetKillEvent should NOT have pct_used (that's only on BudgetWarningEvent)."""
        from runsight_core.budget_enforcement import BudgetKillEvent

        fields = BudgetKillEvent.model_fields
        assert "pct_used" not in fields

    def test_scope_literal_values(self):
        """scope must accept 'block' and 'workflow'."""
        from runsight_core.budget_enforcement import BudgetKillEvent

        for scope_val in ("block", "workflow"):
            evt = BudgetKillEvent(
                scope=scope_val,
                limit_kind="cost_usd",
                current_value=1.0,
                cap_value=2.0,
                workflow_name="w",
            )
            assert evt.scope == scope_val

    def test_limit_kind_literal_values(self):
        """limit_kind must accept 'timeout', 'cost_usd', 'token_cap'."""
        from runsight_core.budget_enforcement import BudgetKillEvent

        for kind in ("timeout", "cost_usd", "token_cap"):
            evt = BudgetKillEvent(
                scope="block",
                block_id="b1",
                limit_kind=kind,
                current_value=1.0,
                cap_value=2.0,
                workflow_name="w",
            )
            assert evt.limit_kind == kind


# ===========================================================================
# 8. _active_budget ContextVar
# ===========================================================================


class TestActiveBudgetContextVar:
    """_active_budget ContextVar is defined with default=None."""

    def test_is_context_var(self):
        from runsight_core.budget_enforcement import _active_budget

        assert isinstance(_active_budget, contextvars.ContextVar)

    def test_default_is_none(self):
        from runsight_core.budget_enforcement import _active_budget

        assert _active_budget.get() is None

    def test_name_is_active_budget(self):
        from runsight_core.budget_enforcement import _active_budget

        assert _active_budget.name == "_active_budget"

    def test_can_set_and_get_value(self):
        """ContextVar can be set to a sentinel and retrieved."""
        from runsight_core.budget_enforcement import _active_budget

        sentinel = object()
        token = _active_budget.set(sentinel)
        try:
            assert _active_budget.get() is sentinel
        finally:
            _active_budget.reset(token)

    def test_reset_restores_default(self):
        """After reset, ContextVar returns to default=None."""
        from runsight_core.budget_enforcement import _active_budget

        sentinel = object()
        token = _active_budget.set(sentinel)
        _active_budget.reset(token)
        assert _active_budget.get() is None
