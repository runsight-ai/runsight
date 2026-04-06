"""
Failing tests for RUN-711: BudgetSession — in-memory accumulator with parent propagation.

Foundation ticket for RUN-708. BudgetSession is a mutable accumulator tracking
cost/tokens/time during execution. Supports parent chain for hierarchical enforcement.

Tests cover:
- BudgetSession is importable from runsight_core.budget_enforcement
- __init__ stores all params and initialises cost_usd=0.0, tokens=0, _started_at
- elapsed_s property returns wall-clock time since creation
- accrue() adds cost and tokens to session and propagates to parent
- check_or_raise() checks this session's caps, then parent's caps recursively
- on_exceed="fail" raises BudgetKilledException
- on_exceed="warn" does NOT raise
- create_isolated_child() returns session with parent=None
- reconcile_child() adds child's totals to parent
- from_workflow_limits() and from_block_limits() construct sessions correctly
"""

from __future__ import annotations

import time

import pytest
from runsight_core.budget_enforcement import BudgetKilledException, BudgetSession

# ===========================================================================
# 1. Importability
# ===========================================================================


class TestBudgetSessionImportable:
    """BudgetSession must be importable from runsight_core.budget_enforcement."""

    def test_class_importable(self):
        """BudgetSession should be importable without error."""
        from runsight_core.budget_enforcement import BudgetSession  # noqa: F401

    def test_is_a_class(self):
        """BudgetSession must be a class, not a function or module."""
        assert isinstance(BudgetSession, type)


# ===========================================================================
# 2. Construction and initial state
# ===========================================================================


class TestBudgetSessionInit:
    """__init__ stores all params and initialises accumulators to zero."""

    def test_scope_name_stored(self):
        s = BudgetSession(scope_name="workflow:my-wf")
        assert s.scope_name == "workflow:my-wf"

    def test_cost_cap_usd_stored(self):
        s = BudgetSession(scope_name="w", cost_cap_usd=1.0)
        assert s.cost_cap_usd == 1.0

    def test_cost_cap_usd_defaults_none(self):
        s = BudgetSession(scope_name="w")
        assert s.cost_cap_usd is None

    def test_token_cap_stored(self):
        s = BudgetSession(scope_name="w", token_cap=5000)
        assert s.token_cap == 5000

    def test_token_cap_defaults_none(self):
        s = BudgetSession(scope_name="w")
        assert s.token_cap is None

    def test_max_duration_seconds_stored(self):
        s = BudgetSession(scope_name="w", max_duration_seconds=120)
        assert s.max_duration_seconds == 120

    def test_max_duration_seconds_defaults_none(self):
        s = BudgetSession(scope_name="w")
        assert s.max_duration_seconds is None

    def test_on_exceed_stored(self):
        s = BudgetSession(scope_name="w", on_exceed="warn")
        assert s.on_exceed == "warn"

    def test_on_exceed_defaults_fail(self):
        s = BudgetSession(scope_name="w")
        assert s.on_exceed == "fail"

    def test_warn_at_pct_stored(self):
        s = BudgetSession(scope_name="w", warn_at_pct=0.9)
        assert s.warn_at_pct == 0.9

    def test_warn_at_pct_defaults_0_8(self):
        s = BudgetSession(scope_name="w")
        assert s.warn_at_pct == 0.8

    def test_parent_stored(self):
        parent = BudgetSession(scope_name="parent")
        child = BudgetSession(scope_name="child", parent=parent)
        assert child.parent is parent

    def test_parent_defaults_none(self):
        s = BudgetSession(scope_name="w")
        assert s.parent is None

    def test_cost_usd_initialised_zero(self):
        s = BudgetSession(scope_name="w")
        assert s.cost_usd == 0.0

    def test_tokens_initialised_zero(self):
        s = BudgetSession(scope_name="w")
        assert s.tokens == 0

    def test_started_at_is_set(self):
        """_started_at should be set to a monotonic timestamp on creation."""
        before = time.monotonic()
        s = BudgetSession(scope_name="w")
        after = time.monotonic()
        assert before <= s._started_at <= after


# ===========================================================================
# 3. elapsed_s property
# ===========================================================================


class TestBudgetSessionElapsed:
    """elapsed_s returns wall-clock time since session creation."""

    def test_elapsed_s_is_positive(self):
        s = BudgetSession(scope_name="w")
        assert s.elapsed_s >= 0.0

    def test_elapsed_s_increases_over_time(self):
        s = BudgetSession(scope_name="w")
        t1 = s.elapsed_s
        # Busy-wait a tiny bit to ensure monotonic clock advances
        time.sleep(0.01)
        t2 = s.elapsed_s
        assert t2 > t1

    def test_elapsed_s_is_float(self):
        s = BudgetSession(scope_name="w")
        assert isinstance(s.elapsed_s, float)


# ===========================================================================
# 4. accrue() — adds cost and tokens, propagates to parent
# ===========================================================================


class TestBudgetSessionAccrue:
    """accrue() adds cost and tokens to session and propagates to parent."""

    def test_accrue_adds_cost(self):
        s = BudgetSession(scope_name="w")
        s.accrue(cost_usd=0.25, tokens=100)
        assert s.cost_usd == pytest.approx(0.25)

    def test_accrue_adds_tokens(self):
        s = BudgetSession(scope_name="w")
        s.accrue(cost_usd=0.0, tokens=500)
        assert s.tokens == 500

    def test_accrue_is_cumulative(self):
        s = BudgetSession(scope_name="w")
        s.accrue(cost_usd=0.10, tokens=100)
        s.accrue(cost_usd=0.15, tokens=200)
        assert s.cost_usd == pytest.approx(0.25)
        assert s.tokens == 300

    def test_accrue_propagates_to_parent(self):
        """When a child accrues, the parent should also accrue the same amount."""
        parent = BudgetSession(scope_name="parent", cost_cap_usd=5.0)
        child = BudgetSession(scope_name="child", parent=parent)
        child.accrue(cost_usd=0.50, tokens=1000)
        assert parent.cost_usd == pytest.approx(0.50)
        assert parent.tokens == 1000

    def test_accrue_propagates_through_chain(self):
        """Grandparent should also receive accruals from grandchild."""
        grandparent = BudgetSession(scope_name="gp")
        parent = BudgetSession(scope_name="p", parent=grandparent)
        child = BudgetSession(scope_name="c", parent=parent)
        child.accrue(cost_usd=0.10, tokens=50)
        assert grandparent.cost_usd == pytest.approx(0.10)
        assert grandparent.tokens == 50

    def test_accrue_zero_is_noop(self):
        s = BudgetSession(scope_name="w")
        s.accrue(cost_usd=0.0, tokens=0)
        assert s.cost_usd == 0.0
        assert s.tokens == 0


# ===========================================================================
# 5. check_or_raise() — on_exceed="fail" raises BudgetKilledException
# ===========================================================================


class TestBudgetSessionCheckOrRaiseFail:
    """check_or_raise() with on_exceed='fail' raises BudgetKilledException."""

    def test_cost_cap_exceeded_raises(self):
        """
        Acceptance scenario:
        Given session with cost_cap_usd=1.0, on_exceed="fail", cost_usd=0.0
        When accrue(cost_usd=1.10, tokens=500) then check_or_raise()
        Then BudgetKilledException(limit_kind="cost_usd", limit_value=1.0, actual_value=1.10) raised
        """
        s = BudgetSession(scope_name="w", cost_cap_usd=1.0, on_exceed="fail")
        s.accrue(cost_usd=1.10, tokens=500)
        with pytest.raises(BudgetKilledException) as exc_info:
            s.check_or_raise()
        assert exc_info.value.limit_kind == "cost_usd"
        assert exc_info.value.limit_value == 1.0
        assert exc_info.value.actual_value == pytest.approx(1.10)

    def test_token_cap_exceeded_raises(self):
        s = BudgetSession(scope_name="w", token_cap=1000, on_exceed="fail")
        s.accrue(cost_usd=0.0, tokens=1500)
        with pytest.raises(BudgetKilledException) as exc_info:
            s.check_or_raise()
        assert exc_info.value.limit_kind == "token_cap"
        assert exc_info.value.limit_value == 1000
        assert exc_info.value.actual_value == 1500

    def test_under_cap_does_not_raise(self):
        """When usage is under caps, check_or_raise should succeed silently."""
        s = BudgetSession(scope_name="w", cost_cap_usd=1.0, token_cap=5000, on_exceed="fail")
        s.accrue(cost_usd=0.50, tokens=2000)
        # Should not raise
        s.check_or_raise()

    def test_exact_cap_does_not_raise(self):
        """Exactly at the cap boundary should NOT raise (not exceeded)."""
        s = BudgetSession(scope_name="w", cost_cap_usd=1.0, on_exceed="fail")
        s.accrue(cost_usd=1.0, tokens=0)
        # At the boundary, not exceeded — should not raise
        s.check_or_raise()

    def test_no_caps_set_does_not_raise(self):
        """When no caps are set, check_or_raise should never raise."""
        s = BudgetSession(scope_name="w", on_exceed="fail")
        s.accrue(cost_usd=999.99, tokens=999999)
        s.check_or_raise()

    def test_block_id_passed_to_exception(self):
        """check_or_raise(block_id=...) passes the block_id to the exception."""
        s = BudgetSession(scope_name="block:research", cost_cap_usd=0.50, on_exceed="fail")
        s.accrue(cost_usd=0.60, tokens=0)
        with pytest.raises(BudgetKilledException) as exc_info:
            s.check_or_raise(block_id="research")
        assert exc_info.value.block_id == "research"


# ===========================================================================
# 6. check_or_raise() — on_exceed="warn" does NOT raise
# ===========================================================================


class TestBudgetSessionCheckOrRaiseWarn:
    """check_or_raise() with on_exceed='warn' does NOT raise."""

    def test_cost_cap_exceeded_no_raise(self):
        """
        Acceptance scenario:
        Given session with cost_cap_usd=1.0, on_exceed="warn", cost_usd=1.10
        When check_or_raise() called
        Then no exception raised
        """
        s = BudgetSession(scope_name="w", cost_cap_usd=1.0, on_exceed="warn")
        s.accrue(cost_usd=1.10, tokens=0)
        # Must not raise
        s.check_or_raise()

    def test_token_cap_exceeded_no_raise(self):
        s = BudgetSession(scope_name="w", token_cap=100, on_exceed="warn")
        s.accrue(cost_usd=0.0, tokens=500)
        # Must not raise
        s.check_or_raise()


# ===========================================================================
# 7. check_or_raise() — parent chain recursion
# ===========================================================================


class TestBudgetSessionParentChainCheck:
    """check_or_raise() checks parent chain recursively."""

    def test_parent_cap_exceeded_raises_from_child(self):
        """
        Acceptance scenario:
        Given parent with cost_cap_usd=2.0, child with no cap, child accrues $2.50
        When child check_or_raise() called
        Then parent's check raises BudgetKilledException(scope="workflow")
        """
        parent = BudgetSession(
            scope_name="workflow:main",
            cost_cap_usd=2.0,
            on_exceed="fail",
        )
        child = BudgetSession(scope_name="block:research", parent=parent)
        child.accrue(cost_usd=2.50, tokens=0)
        with pytest.raises(BudgetKilledException) as exc_info:
            child.check_or_raise()
        assert exc_info.value.limit_kind == "cost_usd"
        assert exc_info.value.limit_value == 2.0
        assert exc_info.value.actual_value == pytest.approx(2.50)

    def test_grandparent_cap_exceeded_raises_from_grandchild(self):
        """Three-level chain: grandparent cap exceeded via grandchild accrual."""
        gp = BudgetSession(scope_name="workflow:top", cost_cap_usd=1.0, on_exceed="fail")
        parent = BudgetSession(scope_name="workflow:sub", parent=gp)
        child = BudgetSession(scope_name="block:leaf", parent=parent)
        child.accrue(cost_usd=1.50, tokens=0)
        with pytest.raises(BudgetKilledException):
            child.check_or_raise()

    def test_child_cap_checked_before_parent(self):
        """If child has its own tighter cap, that should fire first."""
        parent = BudgetSession(scope_name="workflow", cost_cap_usd=10.0, on_exceed="fail")
        child = BudgetSession(
            scope_name="block:tight",
            cost_cap_usd=0.50,
            on_exceed="fail",
            parent=parent,
        )
        child.accrue(cost_usd=0.60, tokens=0)
        with pytest.raises(BudgetKilledException) as exc_info:
            child.check_or_raise()
        # The child's own cap should fire (0.50), not the parent's (10.0)
        assert exc_info.value.limit_value == 0.50

    def test_parent_warn_child_fail_still_checks_child(self):
        """Parent is warn-only, child is fail. Child cap exceeded raises."""
        parent = BudgetSession(scope_name="wf", cost_cap_usd=1.0, on_exceed="warn")
        child = BudgetSession(
            scope_name="block",
            cost_cap_usd=0.50,
            on_exceed="fail",
            parent=parent,
        )
        child.accrue(cost_usd=0.60, tokens=0)
        with pytest.raises(BudgetKilledException):
            child.check_or_raise()


# ===========================================================================
# 8. create_isolated_child() — for DispatchBlock parallel branches
# ===========================================================================


class TestBudgetSessionIsolatedChild:
    """create_isolated_child() returns a session with parent=None."""

    def test_returns_budget_session(self):
        parent = BudgetSession(scope_name="workflow")
        child = parent.create_isolated_child(branch_id="branch-0")
        assert isinstance(child, BudgetSession)

    def test_child_has_no_parent(self):
        parent = BudgetSession(scope_name="workflow")
        child = parent.create_isolated_child(branch_id="branch-0")
        assert child.parent is None

    def test_child_scope_name_includes_branch_id(self):
        parent = BudgetSession(scope_name="workflow:main")
        child = parent.create_isolated_child(branch_id="branch-0")
        assert "branch-0" in child.scope_name

    def test_child_starts_fresh(self):
        """Isolated child starts with zero cost and zero tokens."""
        parent = BudgetSession(scope_name="w", cost_cap_usd=5.0)
        parent.accrue(cost_usd=1.0, tokens=500)
        child = parent.create_isolated_child(branch_id="b1")
        assert child.cost_usd == 0.0
        assert child.tokens == 0

    def test_child_accrue_does_not_propagate_to_original_parent(self):
        """Since parent=None, accruals should not reach the original parent."""
        parent = BudgetSession(scope_name="w")
        child = parent.create_isolated_child(branch_id="b1")
        child.accrue(cost_usd=1.0, tokens=1000)
        assert parent.cost_usd == 0.0
        assert parent.tokens == 0


# ===========================================================================
# 9. reconcile_child() — merge child totals back to parent
# ===========================================================================


class TestBudgetSessionReconcileChild:
    """reconcile_child() adds child's cost_usd and tokens to self."""

    def test_reconcile_adds_cost(self):
        parent = BudgetSession(scope_name="w")
        child = parent.create_isolated_child(branch_id="b1")
        child.accrue(cost_usd=0.75, tokens=0)
        parent.reconcile_child(child)
        assert parent.cost_usd == pytest.approx(0.75)

    def test_reconcile_adds_tokens(self):
        parent = BudgetSession(scope_name="w")
        child = parent.create_isolated_child(branch_id="b1")
        child.accrue(cost_usd=0.0, tokens=3000)
        parent.reconcile_child(child)
        assert parent.tokens == 3000

    def test_reconcile_multiple_children(self):
        """Reconciling several children accumulates their totals."""
        parent = BudgetSession(scope_name="w")
        c1 = parent.create_isolated_child(branch_id="b1")
        c2 = parent.create_isolated_child(branch_id="b2")
        c1.accrue(cost_usd=0.30, tokens=100)
        c2.accrue(cost_usd=0.20, tokens=200)
        parent.reconcile_child(c1)
        parent.reconcile_child(c2)
        assert parent.cost_usd == pytest.approx(0.50)
        assert parent.tokens == 300

    def test_reconcile_is_additive_to_existing(self):
        """Reconciliation adds to whatever the parent already has."""
        parent = BudgetSession(scope_name="w")
        parent.accrue(cost_usd=1.0, tokens=500)
        child = parent.create_isolated_child(branch_id="b1")
        child.accrue(cost_usd=0.50, tokens=250)
        parent.reconcile_child(child)
        assert parent.cost_usd == pytest.approx(1.50)
        assert parent.tokens == 750


# ===========================================================================
# 10. from_workflow_limits() — factory method
# ===========================================================================


class TestBudgetSessionFromWorkflowLimits:
    """from_workflow_limits() constructs a BudgetSession from WorkflowLimitsDef."""

    def test_returns_budget_session(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef(cost_cap_usd=5.0, token_cap=10000, on_exceed="fail")
        session = BudgetSession.from_workflow_limits(limits, workflow_name="my-wf")
        assert isinstance(session, BudgetSession)

    def test_maps_cost_cap_usd(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef(cost_cap_usd=2.50)
        session = BudgetSession.from_workflow_limits(limits, workflow_name="wf")
        assert session.cost_cap_usd == 2.50

    def test_maps_token_cap(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef(token_cap=8000)
        session = BudgetSession.from_workflow_limits(limits, workflow_name="wf")
        assert session.token_cap == 8000

    def test_maps_max_duration_seconds(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef(max_duration_seconds=300)
        session = BudgetSession.from_workflow_limits(limits, workflow_name="wf")
        assert session.max_duration_seconds == 300

    def test_maps_on_exceed(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef(on_exceed="warn")
        session = BudgetSession.from_workflow_limits(limits, workflow_name="wf")
        assert session.on_exceed == "warn"

    def test_maps_warn_at_pct(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef(warn_at_pct=0.9)
        session = BudgetSession.from_workflow_limits(limits, workflow_name="wf")
        assert session.warn_at_pct == 0.9

    def test_scope_name_contains_workflow_name(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef()
        session = BudgetSession.from_workflow_limits(limits, workflow_name="my-pipeline")
        assert "my-pipeline" in session.scope_name

    def test_parent_is_none(self):
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef()
        session = BudgetSession.from_workflow_limits(limits, workflow_name="wf")
        assert session.parent is None

    def test_all_none_limits(self):
        """WorkflowLimitsDef with all defaults produces a session with no caps."""
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = WorkflowLimitsDef()
        session = BudgetSession.from_workflow_limits(limits, workflow_name="wf")
        assert session.cost_cap_usd is None
        assert session.token_cap is None
        assert session.max_duration_seconds is None


# ===========================================================================
# 11. from_block_limits() — factory method
# ===========================================================================


class TestBudgetSessionFromBlockLimits:
    """from_block_limits() constructs a BudgetSession from BlockLimitsDef."""

    def test_returns_budget_session(self):
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef(cost_cap_usd=0.50, token_cap=2000)
        session = BudgetSession.from_block_limits(limits, block_id="research")
        assert isinstance(session, BudgetSession)

    def test_maps_cost_cap_usd(self):
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef(cost_cap_usd=1.25)
        session = BudgetSession.from_block_limits(limits, block_id="b1")
        assert session.cost_cap_usd == 1.25

    def test_maps_token_cap(self):
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef(token_cap=3000)
        session = BudgetSession.from_block_limits(limits, block_id="b1")
        assert session.token_cap == 3000

    def test_maps_max_duration_seconds(self):
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef(max_duration_seconds=60)
        session = BudgetSession.from_block_limits(limits, block_id="b1")
        assert session.max_duration_seconds == 60

    def test_maps_on_exceed(self):
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef(on_exceed="warn")
        session = BudgetSession.from_block_limits(limits, block_id="b1")
        assert session.on_exceed == "warn"

    def test_scope_name_contains_block_id(self):
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef()
        session = BudgetSession.from_block_limits(limits, block_id="summarize")
        assert "summarize" in session.scope_name

    def test_parent_linked(self):
        """When parent is provided, the session should link to it."""
        from runsight_core.yaml.schema import BlockLimitsDef

        parent = BudgetSession(scope_name="workflow")
        limits = BlockLimitsDef(cost_cap_usd=0.50)
        session = BudgetSession.from_block_limits(limits, block_id="b1", parent=parent)
        assert session.parent is parent

    def test_parent_defaults_none(self):
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef()
        session = BudgetSession.from_block_limits(limits, block_id="b1")
        assert session.parent is None

    def test_all_none_limits(self):
        """BlockLimitsDef with all defaults produces a session with no caps."""
        from runsight_core.yaml.schema import BlockLimitsDef

        limits = BlockLimitsDef()
        session = BudgetSession.from_block_limits(limits, block_id="b1")
        assert session.cost_cap_usd is None
        assert session.token_cap is None
        assert session.max_duration_seconds is None


# ===========================================================================
# 12. End-to-end: dispatch isolation pattern
# ===========================================================================


class TestBudgetSessionDispatchPattern:
    """Full isolation + reconciliation pattern used by DispatchBlock."""

    def test_dispatch_isolate_and_reconcile(self):
        """
        Given a workflow session with cost_cap_usd=5.0
        When two branches run in isolation and are reconciled
        Then the parent reflects combined totals
        """
        wf = BudgetSession(scope_name="workflow:main", cost_cap_usd=5.0)
        b1 = wf.create_isolated_child(branch_id="branch-a")
        b2 = wf.create_isolated_child(branch_id="branch-b")

        b1.accrue(cost_usd=1.00, tokens=500)
        b2.accrue(cost_usd=0.75, tokens=300)

        # During isolation, parent should be untouched
        assert wf.cost_usd == 0.0

        wf.reconcile_child(b1)
        wf.reconcile_child(b2)

        assert wf.cost_usd == pytest.approx(1.75)
        assert wf.tokens == 800

    def test_dispatch_reconcile_then_check_raises(self):
        """
        After reconciliation pushes parent over its cap, check_or_raise raises.
        """
        wf = BudgetSession(scope_name="workflow", cost_cap_usd=1.0, on_exceed="fail")
        b1 = wf.create_isolated_child(branch_id="b1")
        b2 = wf.create_isolated_child(branch_id="b2")

        b1.accrue(cost_usd=0.60, tokens=0)
        b2.accrue(cost_usd=0.50, tokens=0)

        wf.reconcile_child(b1)
        wf.reconcile_child(b2)

        with pytest.raises(BudgetKilledException) as exc_info:
            wf.check_or_raise()
        assert exc_info.value.limit_kind == "cost_usd"
        assert exc_info.value.actual_value == pytest.approx(1.10)
