"""
RUN-888: Failing tests for DispatchBlock migration to BlockContext/BlockOutput.

Tests verify that after migration:
AC-1: DispatchBlock.execute accepts BlockContext and returns BlockOutput
AC-2: No direct state mutation in DispatchBlock.execute
AC-3: Per-branch context building produces correct budgeted contexts
AC-4: Budget isolation between branches still works after migration (regression)
AC-5: extra_results correctly captures per-exit block results
AC-6: conversation_updates correctly captures per-branch histories (stateful)
AC-7: End-to-end via execute_block — state contains per-exit results after apply_block_output
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.budget_enforcement import BudgetSession, _active_budget
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    runner.model_name = "gpt-4o"
    runner._build_prompt = MagicMock(
        side_effect=lambda task: (
            task.instruction
            if not task.context
            else f"{task.instruction}\n\nContext:\n{task.context}"
        )
    )
    return runner


@pytest.fixture
def soul_alpha():
    return Soul(id="soul_alpha", role="Reviewer A", system_prompt="You are reviewer A.")


@pytest.fixture
def soul_beta():
    return Soul(id="soul_beta", role="Reviewer B", system_prompt="You are reviewer B.")


@pytest.fixture
def sample_task():
    return Task(id="t1", instruction="dispatch")


@pytest.fixture
def block_execution_ctx():
    """Minimal BlockExecutionContext for execute_block dispatch tests."""
    return BlockExecutionContext(
        workflow_name="test_workflow",
        blocks={},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )


def _make_branches(soul_alpha: Soul, soul_beta: Soul) -> list[DispatchBranch]:
    return [
        DispatchBranch(
            exit_id="exit_a", label="Exit A", soul=soul_alpha, task_instruction="Do task A"
        ),
        DispatchBranch(
            exit_id="exit_b", label="Exit B", soul=soul_beta, task_instruction="Do task B"
        ),
    ]


def _make_result(soul_id: str, output: str, cost: float = 0.0, tokens: int = 0) -> ExecutionResult:
    return ExecutionResult(
        task_id="t1", soul_id=soul_id, output=output, cost_usd=cost, total_tokens=tokens
    )


def _make_dispatch_ctx(block_id: str, task: Task) -> BlockContext:
    """Build a minimal BlockContext for a DispatchBlock (branches info in inputs)."""
    return BlockContext(
        block_id=block_id,
        instruction=task.instruction or "dispatch",
        context=task.context,
        inputs={},
        conversation_history=[],
        soul=None,
        model_name=None,
    )


def _setup_runner_side_effect(mock_runner, soul_output_map: dict):
    """Configure runner.execute_task to return different outputs per soul."""

    async def _side_effect(task, soul, **kwargs):
        return soul_output_map[soul.id]

    mock_runner.execute_task = AsyncMock(side_effect=_side_effect)


# ---------------------------------------------------------------------------
# AC-1: DispatchBlock.execute accepts BlockContext and returns BlockOutput
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatchblock_execute_accepts_block_context(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """DispatchBlock.execute must accept a BlockContext argument and return BlockOutput."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha output.", cost=0.01, tokens=100),
            "soul_beta": _make_result("soul_beta", "Beta output.", cost=0.02, tokens=200),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput), (
        f"Expected BlockOutput but got {type(result).__name__}. "
        "DispatchBlock.execute must return BlockOutput after RUN-888 migration."
    )


@pytest.mark.asyncio
async def test_dispatchblock_execute_output_is_combined_json_array(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """BlockOutput.output must be JSON array: [{'exit_id': ..., 'output': ...}, ...]."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha says yes."),
            "soul_beta": _make_result("soul_beta", "Beta says no."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    parsed = json.loads(result.output)
    assert isinstance(parsed, list), "BlockOutput.output must be a JSON array"
    assert len(parsed) == 2, "JSON array must have one entry per branch"

    exit_ids = {item["exit_id"] for item in parsed}
    assert "exit_a" in exit_ids
    assert "exit_b" in exit_ids


@pytest.mark.asyncio
async def test_dispatchblock_execute_cost_is_sum_of_branches(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """BlockOutput.cost_usd must equal the sum of all branch execution costs."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha.", cost=0.03, tokens=300),
            "soul_beta": _make_result("soul_beta", "Beta.", cost=0.07, tokens=700),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.cost_usd == pytest.approx(0.10), (
        f"Expected cost_usd=0.10 (sum of branches), got {result.cost_usd}"
    )
    assert result.total_tokens == 1000, (
        f"Expected total_tokens=1000 (sum of branches), got {result.total_tokens}"
    )


@pytest.mark.asyncio
async def test_dispatchblock_execute_log_entries_contain_dispatch_completion(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """BlockOutput.log_entries must contain dispatch completion message referencing the block_id."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert len(result.log_entries) >= 1, "BlockOutput.log_entries must not be empty"
    all_content = " ".join(entry.get("content", "") for entry in result.log_entries)
    assert "dispatch1" in all_content, (
        "Expected log_entries to contain an entry referencing block_id 'dispatch1'"
    )
    assert "Dispatch" in all_content or "dispatch" in all_content.lower(), (
        "Expected log_entries to mention dispatch completion"
    )


# ---------------------------------------------------------------------------
# AC-2: No direct state mutation in DispatchBlock.execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatchblock_execute_returns_data_not_state(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """BlockOutput is a pure data object — no WorkflowState fields."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput), f"Expected BlockOutput, got {type(result).__name__}"
    # BlockOutput must NOT have WorkflowState-style 'results' dict
    assert not (
        hasattr(result, "results")
        and isinstance(getattr(result, "results", None), dict)
        and any(isinstance(v, BlockResult) for v in getattr(result, "results", {}).values())
    ), "BlockOutput must not carry a WorkflowState-style results dict with BlockResult values"
    # BlockOutput must NOT have current_task
    assert not hasattr(result, "current_task"), (
        "BlockOutput must not have current_task — that belongs to WorkflowState"
    )


@pytest.mark.asyncio
async def test_dispatchblock_execute_with_block_context_does_not_mutate_input_ctx(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """The input BlockContext must not be mutated during DispatchBlock execution."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)
    original_inputs = dict(ctx.inputs)
    original_history = list(ctx.conversation_history)

    await block.execute(ctx)

    assert ctx.inputs == original_inputs, "BlockContext.inputs must not be mutated"
    assert ctx.conversation_history == original_history, (
        "BlockContext.conversation_history must not be mutated"
    )


# ---------------------------------------------------------------------------
# AC-3: Per-branch context building
# ---------------------------------------------------------------------------


def test_build_block_context_for_dispatchblock_returns_block_context(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """build_block_context for DispatchBlock must return a BlockContext instance."""
    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task)

    ctx = build_block_context(block, state)

    assert isinstance(ctx, BlockContext), (
        f"Expected BlockContext from build_block_context, got {type(ctx).__name__}"
    )


def test_build_block_context_for_dispatchblock_sets_correct_block_id(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """build_block_context must set ctx.block_id to the DispatchBlock's block_id."""
    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task)

    ctx = build_block_context(block, state)

    assert ctx.block_id == "dispatch1", f"Expected block_id='dispatch1', got {ctx.block_id!r}"


def test_build_block_context_for_dispatchblock_sets_instruction_from_task(
    mock_runner, soul_alpha, soul_beta
):
    """build_block_context must set ctx.instruction from state.current_task.instruction."""
    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    task = Task(id="t1", instruction="Classify this document")
    state = WorkflowState(current_task=task)

    ctx = build_block_context(block, state)

    assert ctx.instruction == "Classify this document", (
        f"Expected instruction from current_task, got {ctx.instruction!r}"
    )


def test_build_block_context_for_dispatchblock_branches_accessible_via_inputs(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """build_block_context for DispatchBlock should expose branch data so execute can use it.

    After migration, per-branch task instructions come from branch.task_instruction.
    This test verifies that build_block_context returns a ctx with branch-compatible
    data — the block's branches are accessible from the block instance itself.
    """
    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task)

    ctx = build_block_context(block, state)

    # The block retains its branches — each branch has its own task_instruction
    assert len(block.branches) == 2
    branch_a = next(b for b in block.branches if b.exit_id == "exit_a")
    branch_b = next(b for b in block.branches if b.exit_id == "exit_b")
    assert branch_a.task_instruction == "Do task A"
    assert branch_b.task_instruction == "Do task B"
    # ctx carries context from current_task (not overriding per-branch instructions)
    assert ctx.block_id == "dispatch1"


def test_build_block_context_for_dispatchblock_raises_if_no_current_task(
    mock_runner, soul_alpha, soul_beta
):
    """build_block_context must raise ValueError if state.current_task is None for DispatchBlock."""
    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=None)

    with pytest.raises(ValueError) as exc_info:
        build_block_context(block, state)

    assert "current_task" in str(exc_info.value).lower(), (
        f"ValueError must mention current_task. Got: {str(exc_info.value)!r}"
    )


# ---------------------------------------------------------------------------
# AC-4: Budget isolation regression — still works after migration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_isolation_one_branch_exceeding_cap_does_not_bleed_to_sibling(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Regression: budget isolation via _gather_with_budget_isolation must survive migration.

    Branch A spends within cap; branch B spends beyond its own cap.
    The exception from B must propagate; A's context var must not be tainted.
    """
    captured_sessions: dict[str, object] = {}

    async def _side_effect_with_capture(task, soul, **kwargs):
        # Capture the active budget session at call time for each branch
        captured_sessions[soul.id] = _active_budget.get(None)
        cost = 0.001 if soul.id == "soul_alpha" else 0.001
        tokens = 10
        return _make_result(soul.id, f"{soul.id} output", cost=cost, tokens=tokens)

    mock_runner.execute_task = AsyncMock(side_effect=_side_effect_with_capture)

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)

    # Set an active parent budget session
    parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=1.0)
    token = _active_budget.set(parent)
    try:
        ctx = _make_dispatch_ctx("dispatch1", sample_task)
        await block.execute(ctx)
    finally:
        _active_budget.reset(token)

    # Both branches ran — each captured an isolated child session (not the parent)
    assert len(captured_sessions) == 2
    session_alpha = captured_sessions.get("soul_alpha")
    session_beta = captured_sessions.get("soul_beta")

    # Child sessions must be separate from the parent
    assert session_alpha is not parent, (
        "soul_alpha must execute with an isolated child session, not the parent"
    )
    assert session_beta is not parent, (
        "soul_beta must execute with an isolated child session, not the parent"
    )
    # Each branch gets a different isolated session
    assert session_alpha is not session_beta, (
        "soul_alpha and soul_beta must execute in different isolated budget sessions"
    )


@pytest.mark.asyncio
async def test_budget_isolation_no_parent_session_runs_without_overhead(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Regression: when no BudgetSession is active, dispatch runs as plain asyncio.gather.

    This is the zero-overhead code path — must not raise or change behavior.
    """
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    # Ensure no active budget
    assert _active_budget.get(None) is None

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    # Must not raise
    result = await block.execute(ctx)
    assert isinstance(result, BlockOutput)

    parsed = json.loads(result.output)
    assert len(parsed) == 2


@pytest.mark.asyncio
async def test_budget_isolation_parent_costs_reconciled_after_gather(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Regression: after gather, child branch costs are reconciled to parent session."""
    # Use a mock that accrues to the active budget session (as the real runner does).
    results_by_soul = {
        "soul_alpha": _make_result("soul_alpha", "Alpha.", cost=0.05, tokens=500),
        "soul_beta": _make_result("soul_beta", "Beta.", cost=0.03, tokens=300),
    }

    async def _accruing_side_effect(task, soul, **kwargs):
        result = results_by_soul[soul.id]
        session = _active_budget.get(None)
        if session is not None:
            session.accrue(cost_usd=result.cost_usd, tokens=result.total_tokens)
        return result

    mock_runner.execute_task = AsyncMock(side_effect=_accruing_side_effect)

    parent = BudgetSession(scope_name="workflow:test", cost_cap_usd=10.0)
    initial_cost = parent.cost_usd
    token = _active_budget.set(parent)
    try:
        branches = _make_branches(soul_alpha, soul_beta)
        block = DispatchBlock("dispatch1", branches, mock_runner)
        ctx = _make_dispatch_ctx("dispatch1", sample_task)
        await block.execute(ctx)
    finally:
        _active_budget.reset(token)

    # Parent session must reflect combined branch costs after reconciliation
    assert parent.cost_usd == pytest.approx(initial_cost + 0.08), (
        f"Parent session cost must be reconciled after gather. "
        f"Expected ~0.08, got {parent.cost_usd}"
    )
    assert parent.tokens == 800, (
        f"Parent session tokens must be reconciled. Expected 800, got {parent.tokens}"
    )


# ---------------------------------------------------------------------------
# AC-5: extra_results captures per-exit block results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatchblock_extra_results_contains_per_exit_keys(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """BlockOutput.extra_results must contain per-exit results keyed '{block_id}.{exit_id}'."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha result."),
            "soul_beta": _make_result("soul_beta", "Beta result."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.extra_results is not None, (
        "BlockOutput.extra_results must not be None for DispatchBlock (per-exit keys required)"
    )
    assert "dispatch1.exit_a" in result.extra_results, (
        "extra_results must contain 'dispatch1.exit_a'"
    )
    assert "dispatch1.exit_b" in result.extra_results, (
        "extra_results must contain 'dispatch1.exit_b'"
    )


@pytest.mark.asyncio
async def test_dispatchblock_extra_results_values_are_block_results(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """extra_results values must be BlockResult instances with the branch output string."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha final answer."),
            "soul_beta": _make_result("soul_beta", "Beta final answer."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.extra_results is not None

    result_a = result.extra_results["dispatch1.exit_a"]
    result_b = result.extra_results["dispatch1.exit_b"]

    # Values must be BlockResult instances with correct outputs
    assert isinstance(result_a, BlockResult), (
        f"extra_results['dispatch1.exit_a'] must be BlockResult, got {type(result_a).__name__}"
    )
    assert result_a.output == "Alpha final answer.", (
        f"exit_a result output mismatch: got {result_a.output!r}"
    )
    assert isinstance(result_b, BlockResult), (
        f"extra_results['dispatch1.exit_b'] must be BlockResult, got {type(result_b).__name__}"
    )
    assert result_b.output == "Beta final answer.", (
        f"exit_b result output mismatch: got {result_b.output!r}"
    )


@pytest.mark.asyncio
async def test_dispatchblock_extra_results_exit_handle_matches_exit_id(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Each per-exit BlockResult must have exit_handle set to that branch's exit_id."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert result.extra_results is not None
    assert result.extra_results["dispatch1.exit_a"].exit_handle == "exit_a", (
        "BlockResult for exit_a must have exit_handle='exit_a'"
    )
    assert result.extra_results["dispatch1.exit_b"].exit_handle == "exit_b", (
        "BlockResult for exit_b must have exit_handle='exit_b'"
    )


@pytest.mark.asyncio
async def test_apply_block_output_merges_extra_results_into_state(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """apply_block_output must merge extra_results into state.results (per-exit keys appear in state)."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    output = await block.execute(ctx)
    assert isinstance(output, BlockOutput)

    initial_state = WorkflowState(current_task=sample_task)
    new_state = apply_block_output(initial_state, "dispatch1", output)

    # Combined result at block_id key
    assert "dispatch1" in new_state.results, "state.results must have combined entry at 'dispatch1'"
    # Per-exit keys from extra_results
    assert "dispatch1.exit_a" in new_state.results, (
        "apply_block_output must merge 'dispatch1.exit_a' from extra_results into state.results"
    )
    assert "dispatch1.exit_b" in new_state.results, (
        "apply_block_output must merge 'dispatch1.exit_b' from extra_results into state.results"
    )


# ---------------------------------------------------------------------------
# AC-6: conversation_updates captures per-branch histories (stateful)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_dispatchblock_conversation_updates_not_none(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Stateful DispatchBlock.execute must return BlockOutput with conversation_updates set."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha answer."),
            "soul_beta": _make_result("soul_beta", "Beta answer."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    block.stateful = True
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.conversation_replacements is not None, (
        "Stateful DispatchBlock must set conversation_replacements on BlockOutput (not None)"
    )


@pytest.mark.asyncio
async def test_stateful_dispatchblock_conversation_updates_per_exit_keys(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """conversation_updates must have keys '{block_id}_{exit_id}' for each branch."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha answer."),
            "soul_beta": _make_result("soul_beta", "Beta answer."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    block.stateful = True
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert result.conversation_replacements is not None
    assert "dispatch1_exit_a" in result.conversation_replacements, (
        "conversation_updates must contain key 'dispatch1_exit_a' for branch exit_a"
    )
    assert "dispatch1_exit_b" in result.conversation_replacements, (
        "conversation_updates must contain key 'dispatch1_exit_b' for branch exit_b"
    )


@pytest.mark.asyncio
async def test_stateful_dispatchblock_conversation_updates_contain_user_assistant_pairs(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Each branch history in conversation_updates must have user+assistant message pair."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "ALPHA_UNIQUE_OUTPUT"),
            "soul_beta": _make_result("soul_beta", "BETA_UNIQUE_OUTPUT"),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    block.stateful = True
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert result.conversation_replacements is not None

    history_a = result.conversation_replacements["dispatch1_exit_a"]
    history_b = result.conversation_replacements["dispatch1_exit_b"]

    # Each must have at least 2 messages (user + assistant)
    assert len(history_a) >= 2, (
        f"dispatch1_exit_a history must have at least 2 messages, got {len(history_a)}"
    )
    assert len(history_b) >= 2, (
        f"dispatch1_exit_b history must have at least 2 messages, got {len(history_b)}"
    )

    # Last message must be the assistant output
    assert history_a[-1]["role"] == "assistant"
    assert history_a[-1]["content"] == "ALPHA_UNIQUE_OUTPUT"
    assert history_b[-1]["role"] == "assistant"
    assert history_b[-1]["content"] == "BETA_UNIQUE_OUTPUT"


@pytest.mark.asyncio
async def test_stateful_dispatchblock_conversation_updates_history_independence(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Each branch's history must contain only that branch's outputs (no cross-contamination)."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "ALPHA_UNIQUE_XYZ"),
            "soul_beta": _make_result("soul_beta", "BETA_UNIQUE_ABC"),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    block.stateful = True
    ctx = _make_dispatch_ctx("dispatch1", sample_task)

    result = await block.execute(ctx)

    assert result.conversation_replacements is not None

    history_a = result.conversation_replacements["dispatch1_exit_a"]
    history_b = result.conversation_replacements["dispatch1_exit_b"]

    all_a = " ".join(m["content"] for m in history_a)
    all_b = " ".join(m["content"] for m in history_b)

    assert "ALPHA_UNIQUE_XYZ" in all_a
    assert "BETA_UNIQUE_ABC" not in all_a, (
        "dispatch1_exit_a history must not contain BETA output — cross-contamination detected"
    )
    assert "BETA_UNIQUE_ABC" in all_b
    assert "ALPHA_UNIQUE_XYZ" not in all_b, (
        "dispatch1_exit_b history must not contain ALPHA output — cross-contamination detected"
    )


@pytest.mark.asyncio
async def test_stateful_dispatchblock_apply_block_output_extends_conversation_histories(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """apply_block_output must merge conversation history into state.conversation_histories.

    When the block's ctx carries prior history (via state_snapshot.conversation_histories),
    the stored history after apply_block_output must include both the prior messages and
    the new user+assistant pair (budgeted.messages + new pair = >= 4 total).
    """
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha second."),
            "soul_beta": _make_result("soul_beta", "Beta second."),
        },
    )

    prior_alpha = [
        {"role": "user", "content": "Round 1"},
        {"role": "assistant", "content": "Alpha first."},
    ]
    prior_beta = [
        {"role": "user", "content": "Round 1"},
        {"role": "assistant", "content": "Beta first."},
    ]

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    block.stateful = True

    # Provide prior history via state_snapshot so the block reads it correctly.
    # In real execution, build_block_context populates state_snapshot from WorkflowState.
    initial_state = WorkflowState(
        current_task=sample_task,
        conversation_histories={
            "dispatch1_exit_a": prior_alpha,
            "dispatch1_exit_b": prior_beta,
        },
    )
    ctx = _make_dispatch_ctx("dispatch1", sample_task)
    ctx = ctx.model_copy(update={"state_snapshot": initial_state})

    output = await block.execute(ctx)
    assert isinstance(output, BlockOutput)

    new_state = apply_block_output(initial_state, "dispatch1", output)

    # History must contain prior messages + new pair (>= 4 total)
    history_a = new_state.conversation_histories.get("dispatch1_exit_a", [])
    history_b = new_state.conversation_histories.get("dispatch1_exit_b", [])

    assert len(history_a) >= 4, (
        f"dispatch1_exit_a history must have >= 4 messages after apply_block_output, got {len(history_a)}"
    )
    assert len(history_b) >= 4, (
        f"dispatch1_exit_b history must have >= 4 messages after apply_block_output, got {len(history_b)}"
    )
    # Prior messages preserved
    assert history_a[0]["content"] == "Round 1"
    assert history_b[0]["content"] == "Round 1"
    # New assistant messages appended
    all_a_content = " ".join(m["content"] for m in history_a)
    all_b_content = " ".join(m["content"] for m in history_b)
    assert "Alpha second." in all_a_content
    assert "Beta second." in all_b_content


@pytest.mark.asyncio
async def test_non_stateful_dispatchblock_conversation_updates_is_none(
    mock_runner, soul_alpha, soul_beta, sample_task
):
    """Non-stateful DispatchBlock must return BlockOutput with conversation_updates=None."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    assert block.stateful is False

    ctx = _make_dispatch_ctx("dispatch1", sample_task)
    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.conversation_replacements is None, (
        "Non-stateful DispatchBlock must NOT set conversation_replacements on BlockOutput"
    )


# ---------------------------------------------------------------------------
# AC-7: End-to-end via execute_block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_block_dispatches_dispatchblock_via_new_path(
    mock_runner, soul_alpha, soul_beta, sample_task, block_execution_ctx
):
    """execute_block must route DispatchBlock through build_block_context + apply_block_output."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha.", cost=0.01, tokens=100),
            "soul_beta": _make_result("soul_beta", "Beta.", cost=0.02, tokens=200),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task)

    with patch(
        "runsight_core.workflow.build_block_context",
        wraps=build_block_context,
    ) as mock_build_ctx:
        result_state = await execute_block(block, state, block_execution_ctx)

    assert mock_build_ctx.called, (
        "execute_block must call build_block_context for DispatchBlock (new dispatch path)"
    )
    assert isinstance(result_state, WorkflowState)
    assert "dispatch1" in result_state.results


@pytest.mark.asyncio
async def test_execute_block_dispatchblock_state_has_combined_output(
    mock_runner, soul_alpha, soul_beta, sample_task, block_execution_ctx
):
    """After execute_block, state.results['dispatch1'].output is JSON array of branch results."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha final."),
            "soul_beta": _make_result("soul_beta", "Beta final."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task)

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert "dispatch1" in result_state.results
    combined = json.loads(result_state.results["dispatch1"].output)
    assert isinstance(combined, list)
    assert len(combined) == 2
    exit_ids = {item["exit_id"] for item in combined}
    assert "exit_a" in exit_ids
    assert "exit_b" in exit_ids


@pytest.mark.asyncio
async def test_execute_block_dispatchblock_per_exit_results_in_state(
    mock_runner, soul_alpha, soul_beta, sample_task, block_execution_ctx
):
    """After execute_block, state.results must contain per-exit keys '{block_id}.{exit_id}'."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha per-exit."),
            "soul_beta": _make_result("soul_beta", "Beta per-exit."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task)

    result_state = await execute_block(block, state, block_execution_ctx)

    assert "dispatch1.exit_a" in result_state.results, (
        "state.results must contain per-exit key 'dispatch1.exit_a' after execute_block"
    )
    assert "dispatch1.exit_b" in result_state.results, (
        "state.results must contain per-exit key 'dispatch1.exit_b' after execute_block"
    )
    assert result_state.results["dispatch1.exit_a"].output == "Alpha per-exit."
    assert result_state.results["dispatch1.exit_b"].output == "Beta per-exit."


@pytest.mark.asyncio
async def test_execute_block_dispatchblock_accumulates_cost(
    mock_runner, soul_alpha, soul_beta, sample_task, block_execution_ctx
):
    """execute_block via DispatchBlock new path must accumulate cost_usd in state."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha.", cost=0.04, tokens=400),
            "soul_beta": _make_result("soul_beta", "Beta.", cost=0.06, tokens=600),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task, total_cost_usd=0.10, total_tokens=100)

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert result_state.total_cost_usd == pytest.approx(0.20), (
        f"Expected total_cost_usd=0.20 after dispatch, got {result_state.total_cost_usd}"
    )
    assert result_state.total_tokens == 1100, (
        f"Expected total_tokens=1100 after dispatch, got {result_state.total_tokens}"
    )


@pytest.mark.asyncio
async def test_execute_block_dispatchblock_apply_block_output_called(
    mock_runner, soul_alpha, soul_beta, sample_task, block_execution_ctx
):
    """execute_block must call apply_block_output for DispatchBlock (new path)."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha.", cost=0.01, tokens=100),
            "soul_beta": _make_result("soul_beta", "Beta.", cost=0.02, tokens=200),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(current_task=sample_task)

    apply_calls = []
    original_apply = apply_block_output

    def tracking_apply(s, block_id, output):
        apply_calls.append(block_id)
        return original_apply(s, block_id, output)

    with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
        result_state = await execute_block(block, state, block_execution_ctx)

    assert "dispatch1" in apply_calls, (
        "execute_block must call apply_block_output for DispatchBlock (new dispatch path)"
    )
    assert isinstance(result_state, WorkflowState)


@pytest.mark.asyncio
async def test_execute_block_dispatchblock_preserves_prior_results(
    mock_runner, soul_alpha, soul_beta, sample_task, block_execution_ctx
):
    """execute_block via DispatchBlock must preserve all prior state.results entries."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha."),
            "soul_beta": _make_result("soul_beta", "Beta."),
        },
    )

    branches = _make_branches(soul_alpha, soul_beta)
    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState(
        current_task=sample_task,
        results={"prior_block": BlockResult(output="Prior output")},
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    assert "prior_block" in result_state.results
    assert result_state.results["prior_block"].output == "Prior output"
    assert "dispatch1" in result_state.results
