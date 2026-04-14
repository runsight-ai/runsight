"""
RUN-885: Failing tests for LinearBlock migration to BlockContext/BlockOutput.

Tests verify that after migration:
AC-1: LinearBlock.execute accepts BlockContext and returns BlockOutput (not WorkflowState)
AC-2: No direct state mutation in LinearBlock.execute
AC-3: execute_block dispatches LinearBlock via new path; other blocks via old path
AC-4: Stateful conversation history round-trips through BlockContext -> BlockOutput
AC-5: execute_block outer contract still returns WorkflowState with all fields mapped
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.linear import LinearBlock
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
def sample_soul():
    return Soul(id="soul_a", role="Analyst", system_prompt="You analyze things.")


@pytest.fixture
def sample_task():
    return Task(id="t1", instruction="Summarize the data")


@pytest.fixture
def block_execution_ctx(mock_runner, sample_soul):
    """Minimal BlockExecutionContext for execute_block dispatch tests."""
    return BlockExecutionContext(
        workflow_name="test_workflow",
        blocks={},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )


def _make_minimal_block_context(block_id: str, soul: Soul, instruction: str) -> BlockContext:
    """Helper: build a BlockContext directly (bypasses build_block_context internals)."""
    return BlockContext(
        block_id=block_id,
        instruction=instruction,
        context=None,
        inputs={},
        conversation_history=[],
        soul=soul,
        model_name=soul.model_name or "gpt-4o",
    )


# ---------------------------------------------------------------------------
# AC-1: LinearBlock.execute accepts BlockContext and returns BlockOutput
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linearblock_execute_accepts_block_context(mock_runner, sample_soul):
    """LinearBlock.execute must accept a BlockContext argument and return BlockOutput."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Analysis complete.",
        cost_usd=0.01,
        total_tokens=100,
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    ctx = _make_minimal_block_context("analyze", sample_soul, "Summarize the data")

    result = await block.execute(ctx)

    # Must return BlockOutput, NOT WorkflowState
    assert isinstance(result, BlockOutput), (
        f"Expected BlockOutput but got {type(result).__name__}. "
        "LinearBlock.execute must return BlockOutput after RUN-885 migration."
    )


@pytest.mark.asyncio
async def test_linearblock_execute_output_contains_llm_response(mock_runner, sample_soul):
    """BlockOutput.output must contain the LLM response string."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="The final analysis.",
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    ctx = _make_minimal_block_context("analyze", sample_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.output == "The final analysis."


@pytest.mark.asyncio
async def test_linearblock_execute_populates_cost_and_tokens(mock_runner, sample_soul):
    """BlockOutput.cost_usd and total_tokens must be populated from ExecutionResult."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Done.",
        cost_usd=0.05,
        total_tokens=500,
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    ctx = _make_minimal_block_context("analyze", sample_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.cost_usd == 0.05
    assert result.total_tokens == 500


@pytest.mark.asyncio
async def test_linearblock_execute_log_entries_contain_block_id(mock_runner, sample_soul):
    """BlockOutput.log_entries must contain at least one entry referencing the block_id."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Analysis done.",
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    ctx = _make_minimal_block_context("analyze", sample_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert len(result.log_entries) >= 1
    assert any("analyze" in entry.get("content", "") for entry in result.log_entries), (
        "Expected log_entries to contain an entry referencing block_id 'analyze'"
    )


# ---------------------------------------------------------------------------
# AC-2: No direct state mutation in LinearBlock.execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linearblock_execute_does_not_accept_workflow_state(mock_runner, sample_soul):
    """After migration, LinearBlock.execute must NOT accept WorkflowState as first arg.

    Passing a WorkflowState should either raise TypeError or produce BlockOutput —
    it should NOT silently succeed and return WorkflowState.
    """
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Done.",
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    task = Task(id="t1", instruction="Summarize")
    state = WorkflowState(current_task=task)

    # After migration: calling execute(WorkflowState) should raise TypeError
    # because the signature is execute(ctx: BlockContext) -> BlockOutput
    with pytest.raises(TypeError):
        result = await block.execute(state)
        # If it somehow succeeds, it must NOT return WorkflowState
        assert not isinstance(result, WorkflowState), (
            "LinearBlock.execute must NOT return WorkflowState after migration"
        )


@pytest.mark.asyncio
async def test_linearblock_execute_returns_data_not_state(mock_runner, sample_soul):
    """BlockOutput is a pure data object — no state mutation possible."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Result.",
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    ctx = _make_minimal_block_context("analyze", sample_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    # BlockOutput must NOT have a 'results' dict (that would be WorkflowState territory)
    assert not hasattr(result, "results") or not isinstance(
        getattr(result, "results", None), dict
    ), "BlockOutput must not carry a WorkflowState-style results dict"
    # BlockOutput must NOT have a 'current_task' field
    assert not hasattr(result, "current_task"), (
        "BlockOutput must not have current_task — that belongs to WorkflowState"
    )


# ---------------------------------------------------------------------------
# AC-3: Dual-path dispatch in execute_block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_block_uses_new_path_for_linearblock(
    mock_runner, sample_soul, sample_task, block_execution_ctx
):
    """execute_block must route LinearBlock through build_block_context + apply_block_output."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Linear result.",
        cost_usd=0.02,
        total_tokens=200,
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    state = WorkflowState(current_task=sample_task)

    # Patch build_block_context to verify it's called (new path)
    with patch(
        "runsight_core.workflow.build_block_context",
        wraps=build_block_context,
    ) as mock_build_ctx:
        result_state = await execute_block(block, state, block_execution_ctx)

    assert mock_build_ctx.called, (
        "execute_block must call build_block_context for LinearBlock (new dispatch path)"
    )
    # Outer contract: still returns WorkflowState
    assert isinstance(result_state, WorkflowState)
    assert "linear1" in result_state.results


@pytest.mark.asyncio
async def test_execute_block_uses_old_path_for_gate_block(
    mock_runner, sample_soul, block_execution_ctx
):
    """execute_block must use old state-based path for non-LinearBlock (e.g. GateBlock)."""
    from runsight_core.blocks.gate import GateBlock

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="soul_a",
        output='{"verdict": "pass", "feedback": "Good work"}',
    )

    gate_block = GateBlock("gate1", sample_soul, "prior_block", mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="evaluate"),
        results={"prior_block": BlockResult(output="Some content to evaluate")},
    )

    # build_block_context must NOT be called for GateBlock
    with patch(
        "runsight_core.workflow.build_block_context",
    ) as mock_build_ctx:
        result_state = await execute_block(gate_block, state, block_execution_ctx)

    assert not mock_build_ctx.called, (
        "execute_block must NOT call build_block_context for GateBlock (old dispatch path)"
    )
    assert isinstance(result_state, WorkflowState)


@pytest.mark.asyncio
async def test_execute_block_mixed_workflow_linear_and_gate(mock_runner, sample_soul):
    """A workflow containing both LinearBlock and GateBlock should work end-to-end.

    LinearBlock uses new path (build_block_context called); GateBlock uses old path
    (build_block_context NOT called for gate). Both produce correct WorkflowState.
    """
    from runsight_core.blocks.gate import GateBlock
    from runsight_core.workflow import Workflow

    # LinearBlock returns research output
    # GateBlock evaluates it and returns pass
    mock_runner.execute_task.side_effect = [
        ExecutionResult(
            task_id="t1",
            soul_id="soul_a",
            output="Research report content.",
            cost_usd=0.01,
            total_tokens=100,
        ),
        ExecutionResult(
            task_id="gate_eval",
            soul_id="soul_a",
            output='{"verdict": "pass", "feedback": "Approved"}',
        ),
    ]

    linear_block = LinearBlock("research", sample_soul, mock_runner)
    gate_block = GateBlock("quality_gate", sample_soul, "research", mock_runner)

    wf = Workflow("mixed_workflow")
    wf.add_block(linear_block)
    wf.add_block(gate_block)
    wf.add_transition("research", "quality_gate")
    wf.add_transition("quality_gate", None)
    wf.set_entry("research")

    task = Task(id="t1", instruction="Research this topic")
    state = WorkflowState(current_task=task)

    build_ctx_calls = []

    original_build = build_block_context

    def tracking_build(block, state, step=None):
        build_ctx_calls.append(block.block_id)
        return original_build(block, state, step=step)

    with patch("runsight_core.workflow.build_block_context", side_effect=tracking_build):
        final_state = await wf.run(state)

    assert isinstance(final_state, WorkflowState)
    assert "research" in final_state.results
    assert final_state.results["research"].output == "Research report content."
    assert "quality_gate" in final_state.results

    # KEY assertion: build_block_context must have been called for LinearBlock, not GateBlock
    assert "research" in build_ctx_calls, (
        "build_block_context must be called for LinearBlock in mixed workflow (new path)"
    )
    assert "quality_gate" not in build_ctx_calls, (
        "build_block_context must NOT be called for GateBlock in mixed workflow (old path)"
    )


# ---------------------------------------------------------------------------
# AC-4: Stateful conversation history round-trip through BlockContext -> BlockOutput
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_history_round_trip_via_block_context(mock_runner, sample_soul):
    """BlockOutput.conversation_updates must contain updated history from BlockContext.

    When a stateful LinearBlock receives existing history via BlockContext,
    it must return BlockOutput with conversation_updates containing original + new pair.
    """
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Second response.",
    )

    prior_history = [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First response"},
    ]

    block = LinearBlock("analyze", sample_soul, mock_runner)
    block.stateful = True

    ctx = BlockContext(
        block_id="analyze",
        instruction="Summarize again",
        context=None,
        inputs={},
        conversation_history=prior_history,
        soul=sample_soul,
        model_name="gpt-4o",
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput), f"Expected BlockOutput but got {type(result).__name__}"
    assert result.conversation_updates is not None, (
        "Stateful LinearBlock must set conversation_updates on BlockOutput"
    )

    history_key = f"analyze_{sample_soul.id}"
    assert history_key in result.conversation_updates, (
        f"Expected conversation_updates to contain key '{history_key}'"
    )

    updated = result.conversation_updates[history_key]
    # Must include the new user+assistant pair appended to the prior history
    assert len(updated) >= 2, "conversation_updates must contain at least new user+assistant pair"
    assert updated[-1]["role"] == "assistant"
    assert updated[-1]["content"] == "Second response."


@pytest.mark.asyncio
async def test_stateful_history_applied_via_apply_block_output(mock_runner, sample_soul):
    """apply_block_output must correctly extend state.conversation_histories
    from BlockOutput.conversation_updates (verifying full round-trip).
    """
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Second response.",
    )

    prior_history = [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First response"},
    ]
    history_key = f"analyze_{sample_soul.id}"

    block = LinearBlock("analyze", sample_soul, mock_runner)
    block.stateful = True

    ctx = BlockContext(
        block_id="analyze",
        instruction="Summarize again",
        context=None,
        inputs={},
        conversation_history=prior_history,
        soul=sample_soul,
        model_name="gpt-4o",
    )

    result = await block.execute(ctx)
    assert isinstance(result, BlockOutput)

    # Simulate what execute_block does: apply output to state
    initial_state = WorkflowState(
        current_task=Task(id="t1", instruction="Summarize again"),
        conversation_histories={history_key: prior_history},
    )
    new_state = apply_block_output(initial_state, "analyze", result)

    assert history_key in new_state.conversation_histories
    final_history = new_state.conversation_histories[history_key]
    # Round-trip: prior history + new pair must all be present
    assert len(final_history) >= 4, (
        "After apply_block_output, conversation history must include prior + new messages"
    )
    assert final_history[-1]["role"] == "assistant"
    assert final_history[-1]["content"] == "Second response."


@pytest.mark.asyncio
async def test_non_stateful_block_no_conversation_updates(mock_runner, sample_soul):
    """Non-stateful LinearBlock must return BlockOutput with conversation_updates=None."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Output.",
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    assert block.stateful is False

    ctx = _make_minimal_block_context("analyze", sample_soul, "Summarize")
    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.conversation_updates is None, (
        "Non-stateful LinearBlock must NOT set conversation_updates on BlockOutput"
    )


# ---------------------------------------------------------------------------
# AC-5: execute_block outer contract returns WorkflowState with all fields mapped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_block_linearblock_maps_cost_to_state(
    mock_runner, sample_soul, sample_task, block_execution_ctx
):
    """execute_block must accumulate cost_usd via apply_block_output (new path) for LinearBlock.

    Verifies that apply_block_output is called in the dispatch path for LinearBlock.
    """
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Done.",
        cost_usd=0.05,
        total_tokens=500,
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    state = WorkflowState(current_task=sample_task, total_cost_usd=0.10, total_tokens=100)

    apply_calls = []
    original_apply = apply_block_output

    def tracking_apply(s, block_id, output):
        apply_calls.append(block_id)
        return original_apply(s, block_id, output)

    with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
        result_state = await execute_block(block, state, block_execution_ctx)

    # KEY: apply_block_output must have been called for LinearBlock (new path)
    assert "analyze" in apply_calls, (
        "execute_block must call apply_block_output for LinearBlock (new dispatch path)"
    )
    assert isinstance(result_state, WorkflowState)
    assert result_state.total_cost_usd == pytest.approx(0.15)
    assert result_state.total_tokens == 600


@pytest.mark.asyncio
async def test_execute_block_linearblock_maps_result_to_state(
    mock_runner, sample_soul, sample_task, block_execution_ctx
):
    """execute_block must store BlockOutput.output in state.results via apply_block_output."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Research findings here.",
    )

    block = LinearBlock("research", sample_soul, mock_runner)
    state = WorkflowState(current_task=sample_task)

    apply_calls = []
    original_apply = apply_block_output

    def tracking_apply(s, block_id, output):
        apply_calls.append(block_id)
        return original_apply(s, block_id, output)

    with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
        result_state = await execute_block(block, state, block_execution_ctx)

    assert "research" in apply_calls, "execute_block must call apply_block_output for LinearBlock"
    assert "research" in result_state.results
    assert isinstance(result_state.results["research"], BlockResult)
    assert result_state.results["research"].output == "Research findings here."


@pytest.mark.asyncio
async def test_execute_block_linearblock_maps_log_to_state(
    mock_runner, sample_soul, sample_task, block_execution_ctx
):
    """execute_block must extend state.execution_log via apply_block_output for LinearBlock."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Log test output.",
    )

    block = LinearBlock("logblock", sample_soul, mock_runner)
    state = WorkflowState(
        current_task=sample_task,
        execution_log=[{"role": "system", "content": "Prior log entry"}],
    )

    apply_calls = []
    original_apply = apply_block_output

    def tracking_apply(s, block_id, output):
        apply_calls.append(block_id)
        return original_apply(s, block_id, output)

    with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
        result_state = await execute_block(block, state, block_execution_ctx)

    assert "logblock" in apply_calls, (
        "execute_block must call apply_block_output for LinearBlock (new dispatch path)"
    )
    assert isinstance(result_state, WorkflowState)
    assert len(result_state.execution_log) >= 2
    assert result_state.execution_log[0]["content"] == "Prior log entry"
    assert any("logblock" in e.get("content", "") for e in result_state.execution_log[1:])


@pytest.mark.asyncio
async def test_execute_block_does_not_call_build_block_context_for_gate(mock_runner, sample_soul):
    """Regression: GateBlock must NOT go through build_block_context new path."""
    from runsight_core.blocks.gate import GateBlock

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="soul_a",
        output='{"verdict": "pass", "feedback": "OK"}',
    )

    gate_block = GateBlock("gate1", sample_soul, "prior", mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="evaluate"),
        results={"prior": BlockResult(output="Content")},
    )
    ctx = BlockExecutionContext(
        workflow_name="test",
        blocks={"gate1": gate_block},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )

    with patch("runsight_core.workflow.build_block_context") as mock_bbc:
        result_state = await execute_block(gate_block, state, ctx)

    assert not mock_bbc.called
    assert isinstance(result_state, WorkflowState)
