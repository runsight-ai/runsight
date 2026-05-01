"""LinearBlock BlockContext/BlockOutput migration coverage.

Boundary: LinearBlock execution and workflow dispatch must use the BlockContext
to BlockOutput contract while the public execute_block contract still returns
WorkflowState. Owner: packages/core runtime block execution. Exit criteria:
remove this migration guard once the block execution contract is no longer in
transition and equivalent behavior coverage lives in ordinary block suites.
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
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block

pytestmark = pytest.mark.migration
UNSET_MODEL_SENTINEL = "__runsight_explicit_model_required__"

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = UNSET_MODEL_SENTINEL
    runner._build_prompt = MagicMock(
        side_effect=lambda task: (
            task.instruction
            if not task.context
            else f"{task.instruction}\n\nContext:\n{task.context}"
        )
    )
    return runner


@pytest.fixture
def analysis_soul():
    return Soul(
        id="analysis_soul",
        kind="soul",
        name="Analysis Soul",
        role="Analyst",
        system_prompt="You analyze things.",
    )


@pytest.fixture
def block_execution_ctx():
    """Minimal BlockExecutionContext for execute_block dispatch tests."""
    return BlockExecutionContext(
        workflow_name="linear_dispatch_workflow",
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
        model_name=soul.model_name or UNSET_MODEL_SENTINEL,
    )


# LinearBlock BlockContext execution


@pytest.mark.asyncio
async def test_linearblock_execute_accepts_block_context(mock_runner, analysis_soul):
    """LinearBlock.execute must accept a BlockContext argument and return BlockOutput."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Analysis complete.",
        cost_usd=0.01,
        total_tokens=100,
    )

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    ctx = _make_minimal_block_context("analysis_block", analysis_soul, "Summarize the data")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput), (
        f"Expected BlockOutput but got {type(result).__name__}. "
        "LinearBlock.execute must return BlockOutput under the execution contract."
    )


@pytest.mark.asyncio
async def test_linearblock_execute_output_contains_llm_response(mock_runner, analysis_soul):
    """BlockOutput.output must contain the LLM response string."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="The final analysis.",
    )

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    ctx = _make_minimal_block_context("analysis_block", analysis_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.output == "The final analysis."


@pytest.mark.asyncio
async def test_linearblock_execute_populates_cost_and_tokens(mock_runner, analysis_soul):
    """BlockOutput.cost_usd and total_tokens must be populated from ExecutionResult."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Done.",
        cost_usd=0.05,
        total_tokens=500,
    )

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    ctx = _make_minimal_block_context("analysis_block", analysis_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.cost_usd == 0.05
    assert result.total_tokens == 500


@pytest.mark.asyncio
async def test_linearblock_execute_log_entries_contain_block_id(mock_runner, analysis_soul):
    """BlockOutput.log_entries must contain at least one entry referencing the block_id."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Analysis done.",
    )

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    ctx = _make_minimal_block_context("analysis_block", analysis_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert len(result.log_entries) >= 1
    assert any("analysis_block" in entry.get("content", "") for entry in result.log_entries), (
        "Expected log_entries to contain an entry referencing block_id 'analysis_block'"
    )


# LinearBlock output isolation


@pytest.mark.asyncio
async def test_linearblock_execute_returns_data_not_state(mock_runner, analysis_soul):
    """BlockOutput is a pure data object with no state mutation surface."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Result.",
    )

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    ctx = _make_minimal_block_context("analysis_block", analysis_soul, "Summarize")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert not hasattr(result, "results") or not isinstance(
        getattr(result, "results", None), dict
    ), "BlockOutput must not carry a WorkflowState-style results dict"
    assert not hasattr(result, "current_task"), (
        "BlockOutput must not have current_task; that belongs to WorkflowState"
    )


# Workflow dispatch contract


@pytest.mark.asyncio
async def test_execute_block_dispatches_linearblock_via_block_context(
    mock_runner, analysis_soul, block_execution_ctx
):
    """execute_block must route LinearBlock through build_block_context + apply_block_output."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Linear result.",
        cost_usd=0.02,
        total_tokens=200,
    )

    block = LinearBlock("analysis_linear", analysis_soul, mock_runner)
    state = WorkflowState()

    # Patch build_block_context to verify dispatch uses BlockContext.
    with patch(
        "runsight_core.workflow.build_block_context",
        wraps=build_block_context,
    ) as mock_build_ctx:
        result_state = await execute_block(block, state, block_execution_ctx)

    assert mock_build_ctx.called, (
        "execute_block must call build_block_context for LinearBlock dispatch"
    )
    # Outer contract: still returns WorkflowState
    assert isinstance(result_state, WorkflowState)
    assert "analysis_linear" in result_state.results


@pytest.mark.asyncio
async def test_execute_block_dispatches_gateblock_via_block_context(
    mock_runner, analysis_soul, block_execution_ctx
):
    """execute_block must use the BlockContext path for GateBlock."""
    from runsight_core.blocks.gate import GateBlock

    mock_runner.execute.return_value = ExecutionResult(
        task_id="gate-eval-task",
        soul_id="analysis_soul",
        output="PASS",
    )

    gate_block = GateBlock("approval_gate", analysis_soul, "prior_block", mock_runner)
    state = WorkflowState(
        results={"prior_block": BlockResult(output="Some content to evaluate")},
    )

    with patch(
        "runsight_core.workflow.build_block_context",
        wraps=build_block_context,
    ) as mock_build_ctx:
        result_state = await execute_block(gate_block, state, block_execution_ctx)

    assert mock_build_ctx.called, (
        "execute_block must call build_block_context for GateBlock dispatch"
    )
    assert isinstance(result_state, WorkflowState)


@pytest.mark.asyncio
async def test_execute_block_mixed_workflow_linear_and_gate(mock_runner, analysis_soul):
    """A workflow containing both LinearBlock and GateBlock should work through execution.

    LinearBlock and GateBlock both use build_block_context and produce the
    expected WorkflowState.
    """
    from runsight_core.blocks.gate import GateBlock
    from runsight_core.workflow import Workflow

    # LinearBlock returns research output
    # GateBlock evaluates it and returns pass
    mock_runner.execute.side_effect = [
        ExecutionResult(
            task_id="analysis-task",
            soul_id="analysis_soul",
            output="Research report content.",
            cost_usd=0.01,
            total_tokens=100,
        ),
        ExecutionResult(
            task_id="gate-eval-task",
            soul_id="analysis_soul",
            output='{"verdict": "pass", "feedback": "Approved"}',
        ),
    ]

    linear_block = LinearBlock("research", analysis_soul, mock_runner)
    gate_block = GateBlock("quality_gate", analysis_soul, "research", mock_runner)

    workflow = Workflow("mixed_workflow")
    workflow.add_block(linear_block)
    workflow.add_block(gate_block)
    workflow.add_transition("research", "quality_gate")
    workflow.add_transition("quality_gate", None)
    workflow.set_entry("research")

    state = WorkflowState()

    build_ctx_calls = []

    original_build = build_block_context

    def tracking_build(block, state, step=None, **kwargs):
        build_ctx_calls.append(block.block_id)
        return original_build(block, state, step=step, **kwargs)

    with patch("runsight_core.workflow.build_block_context", side_effect=tracking_build):
        final_state = await workflow.run(state)

    assert isinstance(final_state, WorkflowState)
    assert "research" in final_state.results
    assert final_state.results["research"].output == "Research report content."
    assert "quality_gate" in final_state.results

    assert "research" in build_ctx_calls, (
        "build_block_context must be called for LinearBlock in mixed workflow"
    )
    assert "quality_gate" in build_ctx_calls, (
        "build_block_context must be called for GateBlock in mixed workflow"
    )


# Stateful conversation history


@pytest.mark.asyncio
async def test_stateful_history_round_trip_via_block_context(mock_runner, analysis_soul):
    """BlockOutput.conversation_replacements must contain updated history from BlockContext.

    When a stateful LinearBlock receives existing history via BlockContext,
    it must return BlockOutput with conversation_replacements containing original + new pair.
    """
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Second response.",
    )

    prior_history = [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First response"},
    ]

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    block.stateful = True

    ctx = BlockContext(
        block_id="analysis_block",
        instruction="Summarize again",
        context=None,
        inputs={},
        conversation_history=prior_history,
        soul=analysis_soul,
        model_name=UNSET_MODEL_SENTINEL,
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput), f"Expected BlockOutput but got {type(result).__name__}"
    assert result.conversation_replacements is not None, (
        "Stateful LinearBlock must set conversation_replacements on BlockOutput"
    )

    history_key = f"analysis_block_{analysis_soul.id}"
    assert history_key in result.conversation_replacements, (
        f"Expected conversation_replacements to contain key '{history_key}'"
    )

    updated = result.conversation_replacements[history_key]
    assert len(updated) >= 2, (
        "conversation_replacements must contain at least the new user+assistant pair"
    )
    assert updated[-1]["role"] == "assistant"
    assert updated[-1]["content"] == "Second response."


@pytest.mark.asyncio
async def test_stateful_history_applied_via_apply_block_output(mock_runner, analysis_soul):
    """apply_block_output must correctly extend state.conversation_histories
    from BlockOutput.conversation_replacements (verifying full round-trip).
    """
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Second response.",
    )

    prior_history = [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First response"},
    ]
    history_key = f"analysis_block_{analysis_soul.id}"

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    block.stateful = True

    ctx = BlockContext(
        block_id="analysis_block",
        instruction="Summarize again",
        context=None,
        inputs={},
        conversation_history=prior_history,
        soul=analysis_soul,
        model_name=UNSET_MODEL_SENTINEL,
    )

    result = await block.execute(ctx)
    assert isinstance(result, BlockOutput)

    # Simulate what execute_block does: apply output to state
    initial_state = WorkflowState(
        conversation_histories={history_key: prior_history},
    )
    new_state = apply_block_output(initial_state, "analysis_block", result)

    assert history_key in new_state.conversation_histories
    final_history = new_state.conversation_histories[history_key]
    # Round-trip: prior history + new pair must all be present
    assert len(final_history) >= 4, (
        "After apply_block_output, conversation history must include prior + new messages"
    )
    assert final_history[-1]["role"] == "assistant"
    assert final_history[-1]["content"] == "Second response."


@pytest.mark.asyncio
async def test_non_stateful_block_no_conversation_updates(mock_runner, analysis_soul):
    """Non-stateful LinearBlock must return BlockOutput with conversation_updates=None."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Output.",
    )

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    assert block.stateful is False

    ctx = _make_minimal_block_context("analysis_block", analysis_soul, "Summarize")
    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.conversation_updates is None, (
        "Non-stateful LinearBlock must not set conversation_updates on BlockOutput"
    )


# WorkflowState mapping


@pytest.mark.asyncio
async def test_execute_block_linearblock_maps_cost_to_state(
    mock_runner, analysis_soul, block_execution_ctx
):
    """execute_block must accumulate cost_usd via apply_block_output for LinearBlock.

    Verifies that apply_block_output is called in the dispatch path for LinearBlock.
    """
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Done.",
        cost_usd=0.05,
        total_tokens=500,
    )

    block = LinearBlock("analysis_block", analysis_soul, mock_runner)
    state = WorkflowState(total_cost_usd=0.10, total_tokens=100)

    apply_calls = []
    original_apply = apply_block_output

    def tracking_apply(s, block_id, output):
        apply_calls.append(block_id)
        return original_apply(s, block_id, output)

    with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
        result_state = await execute_block(block, state, block_execution_ctx)

    assert "analysis_block" in apply_calls, (
        "execute_block must call apply_block_output for LinearBlock dispatch"
    )
    assert isinstance(result_state, WorkflowState)
    assert result_state.total_cost_usd == pytest.approx(0.15)
    assert result_state.total_tokens == 600


@pytest.mark.asyncio
async def test_execute_block_linearblock_maps_result_to_state(
    mock_runner, analysis_soul, block_execution_ctx
):
    """execute_block must store BlockOutput.output in state.results via apply_block_output."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Research findings here.",
    )

    block = LinearBlock("research", analysis_soul, mock_runner)
    state = WorkflowState()

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
    mock_runner, analysis_soul, block_execution_ctx
):
    """execute_block must extend state.execution_log via apply_block_output for LinearBlock."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis-task",
        soul_id="analysis_soul",
        output="Log test output.",
    )

    block = LinearBlock("log_capture_block", analysis_soul, mock_runner)
    state = WorkflowState(
        execution_log=[{"role": "system", "content": "Prior log entry"}],
    )

    apply_calls = []
    original_apply = apply_block_output

    def tracking_apply(s, block_id, output):
        apply_calls.append(block_id)
        return original_apply(s, block_id, output)

    with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
        result_state = await execute_block(block, state, block_execution_ctx)

    assert "log_capture_block" in apply_calls, (
        "execute_block must call apply_block_output for LinearBlock dispatch"
    )
    assert isinstance(result_state, WorkflowState)
    assert len(result_state.execution_log) >= 2
    assert result_state.execution_log[0]["content"] == "Prior log entry"
    assert any("log_capture_block" in e.get("content", "") for e in result_state.execution_log[1:])


@pytest.mark.asyncio
async def test_execute_block_calls_build_block_context_for_gate(mock_runner, analysis_soul):
    """GateBlock goes through build_block_context dispatch."""
    from runsight_core.blocks.gate import GateBlock

    mock_runner.execute.return_value = ExecutionResult(
        task_id="gate-eval-task",
        soul_id="analysis_soul",
        output="PASS",
    )

    gate_block = GateBlock("approval_gate", analysis_soul, "prior", mock_runner)
    state = WorkflowState(
        results={"prior": BlockResult(output="Content")},
    )
    ctx = BlockExecutionContext(
        workflow_name="gate_dispatch_workflow",
        blocks={"approval_gate": gate_block},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )

    with patch("runsight_core.workflow.build_block_context", wraps=build_block_context) as mock_bbc:
        result_state = await execute_block(gate_block, state, ctx)

    assert mock_bbc.called
    assert isinstance(result_state, WorkflowState)
