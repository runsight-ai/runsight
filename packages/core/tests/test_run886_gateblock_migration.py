"""
RUN-886: Failing tests for GateBlock migration to BlockContext/BlockOutput.

Tests verify that after migration:
AC-1: GateBlock.execute accepts BlockContext and returns BlockOutput (not WorkflowState)
AC-2: PASS/FAIL exit_handle logic preserved identically
AC-3: extract_field behavior preserved
AC-4: End-to-end workflow with GateBlock produces identical routing decisions
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
from runsight_core.blocks.gate import GateBlock
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
def gate_soul():
    return Soul(id="gate_soul", role="Gate", system_prompt="Evaluate quality strictly.")


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


def _make_gate_block_context(
    block_id: str,
    soul: Soul,
    instruction: str,
    context: str,
) -> BlockContext:
    """Helper: build a BlockContext for GateBlock tests directly."""
    return BlockContext(
        block_id=block_id,
        instruction=instruction,
        context=context,
        inputs={},
        conversation_history=[],
        soul=soul,
        model_name=soul.model_name or "gpt-4o",
    )


# ---------------------------------------------------------------------------
# AC-1: GateBlock.execute accepts BlockContext and returns BlockOutput
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateblock_execute_accepts_block_context(mock_runner, gate_soul):
    """GateBlock.execute must accept a BlockContext argument and return BlockOutput."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
        cost_usd=0.01,
        total_tokens=100,
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context(
        "gate1",
        gate_soul,
        instruction=(
            "Evaluate the following content and decide if it meets quality standards.\n"
            "Respond with EXACTLY one of:\n"
            "PASS - if the content meets quality standards\n"
            "FAIL: <detailed reason> - if the content needs improvement"
        ),
        context="Some content to evaluate",
    )

    result = await block.execute(ctx)

    # Must return BlockOutput, NOT WorkflowState
    assert isinstance(result, BlockOutput), (
        f"Expected BlockOutput but got {type(result).__name__}. "
        "GateBlock.execute must return BlockOutput after RUN-886 migration."
    )


@pytest.mark.asyncio
async def test_gateblock_execute_populates_cost_and_tokens(mock_runner, gate_soul):
    """BlockOutput.cost_usd and total_tokens must be populated from ExecutionResult."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
        cost_usd=0.05,
        total_tokens=500,
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context("gate1", gate_soul, instruction="Evaluate", context="Content")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.cost_usd == 0.05
    assert result.total_tokens == 500


@pytest.mark.asyncio
async def test_gateblock_execute_log_entries_contain_block_id(mock_runner, gate_soul):
    """BlockOutput.log_entries must contain at least one entry referencing the block_id."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context("gate1", gate_soul, instruction="Evaluate", context="Content")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert len(result.log_entries) >= 1, (
        "BlockOutput.log_entries must not be empty after gate execution"
    )
    assert any("gate1" in entry.get("content", "") for entry in result.log_entries), (
        "Expected log_entries to contain an entry referencing block_id 'gate1'"
    )


@pytest.mark.asyncio
async def test_gateblock_execute_returns_data_not_state(mock_runner, gate_soul):
    """BlockOutput is a pure data object — no WorkflowState fields present."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context("gate1", gate_soul, instruction="Evaluate", context="Content")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    # BlockOutput must NOT have a WorkflowState-style 'results' dict
    assert not (
        hasattr(result, "results") and isinstance(getattr(result, "results", None), dict)
    ), "BlockOutput must not carry a WorkflowState-style results dict"
    # BlockOutput must NOT have current_task
    assert not hasattr(result, "current_task"), (
        "BlockOutput must not have current_task — that belongs to WorkflowState"
    )


# ---------------------------------------------------------------------------
# AC-2: PASS/FAIL exit_handle logic preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateblock_pass_sets_exit_handle_pass(mock_runner, gate_soul):
    """When LLM returns 'PASS', output.exit_handle must be 'pass'."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context(
        "gate1", gate_soul, instruction="Evaluate", context="Good content"
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "pass", (
        f"Expected exit_handle='pass' on PASS decision, got {result.exit_handle!r}"
    )


@pytest.mark.asyncio
async def test_gateblock_pass_output_is_pass_through_content(mock_runner, gate_soul):
    """When LLM returns 'PASS', output.output is the pass-through content (decision line)."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context(
        "gate1", gate_soul, instruction="Evaluate", context="Good content"
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.output == "PASS", (
        f"On PASS (no extract_field), output.output should be 'PASS', got {result.output!r}"
    )


@pytest.mark.asyncio
async def test_gateblock_fail_sets_exit_handle_fail(mock_runner, gate_soul):
    """When LLM returns 'FAIL: quality too low', output.exit_handle must be 'fail'."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="FAIL: quality too low",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context(
        "gate1", gate_soul, instruction="Evaluate", context="Weak content"
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "fail", (
        f"Expected exit_handle='fail' on FAIL decision, got {result.exit_handle!r}"
    )


@pytest.mark.asyncio
async def test_gateblock_fail_output_is_feedback(mock_runner, gate_soul):
    """When LLM returns 'FAIL: quality too low', output.output is the feedback text."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="FAIL: quality too low",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context(
        "gate1", gate_soul, instruction="Evaluate", context="Weak content"
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert "quality too low" in result.output, (
        f"Expected feedback text in output, got {result.output!r}"
    )


@pytest.mark.asyncio
async def test_gateblock_only_first_line_matters_for_pass(mock_runner, gate_soul):
    """When LLM returns 'PASS\\nsome extra text', only first line matters — exit_handle='pass'."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS\nsome extra text that should be ignored",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context("gate1", gate_soul, instruction="Evaluate", context="Content")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "pass", (
        f"Multiline PASS response: expected exit_handle='pass', got {result.exit_handle!r}"
    )
    # The output should not include the trailing extra lines
    assert "extra text" not in result.output, (
        "Only first line should be used; trailing lines must be discarded"
    )


@pytest.mark.asyncio
async def test_gateblock_lowercase_pass_is_recognized(mock_runner, gate_soul):
    """When LLM returns 'pass' (lowercase), it must still be recognized as PASS."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="pass",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    ctx = _make_gate_block_context("gate1", gate_soul, instruction="Evaluate", context="Content")

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "pass", (
        f"Lowercase 'pass' must be recognized; expected exit_handle='pass', got {result.exit_handle!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: extract_field behavior preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateblock_extract_field_on_pass(mock_runner, gate_soul):
    """On PASS with extract_field='score', JSON context is parsed and field extracted."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner, extract_field="score")
    ctx = _make_gate_block_context(
        "gate1",
        gate_soul,
        instruction="Evaluate",
        context=json.dumps([{"score": 85}]),
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "pass"
    assert result.output == 85 or result.output == "85", (
        f"Expected extracted score=85, got {result.output!r}"
    )


@pytest.mark.asyncio
async def test_gateblock_extract_field_invalid_json_falls_back(mock_runner, gate_soul):
    """When JSON is invalid and extract_field is set, output falls back to decision line."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner, extract_field="score")
    ctx = _make_gate_block_context(
        "gate1",
        gate_soul,
        instruction="Evaluate",
        context="not valid json at all",
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "pass"
    # Falls back to decision_line ("PASS") when JSON parse fails
    assert result.output == "PASS", (
        f"Expected fallback to 'PASS' on invalid JSON, got {result.output!r}"
    )


@pytest.mark.asyncio
async def test_gateblock_extract_field_missing_field_falls_back(mock_runner, gate_soul):
    """When JSON is valid but field is missing, output falls back to decision line."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner, extract_field="score")
    ctx = _make_gate_block_context(
        "gate1",
        gate_soul,
        instruction="Evaluate",
        context=json.dumps([{"other_field": "value"}]),  # "score" missing
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "pass"
    # Falls back to decision_line ("PASS") when field not in JSON
    assert result.output == "PASS", (
        f"Expected fallback to 'PASS' on missing field, got {result.output!r}"
    )


@pytest.mark.asyncio
async def test_gateblock_extract_field_not_applied_on_fail(mock_runner, gate_soul):
    """extract_field must NOT be applied when gate decision is FAIL."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="FAIL: insufficient quality",
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner, extract_field="score")
    ctx = _make_gate_block_context(
        "gate1",
        gate_soul,
        instruction="Evaluate",
        context=json.dumps([{"score": 42}]),
    )

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.exit_handle == "fail"
    # On FAIL, feedback is returned (not the extracted field)
    assert "insufficient quality" in result.output, (
        f"On FAIL, feedback must be returned, not extracted field. Got: {result.output!r}"
    )


# ---------------------------------------------------------------------------
# AC-4: End-to-end via execute_block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_block_dispatches_gateblock_via_new_path(
    mock_runner, gate_soul, block_execution_ctx
):
    """execute_block must route GateBlock through build_block_context + apply_block_output."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
        cost_usd=0.02,
        total_tokens=200,
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="evaluate"),
        results={"prior_block": BlockResult(output="Content to evaluate")},
    )

    # Patch build_block_context to verify it IS called for GateBlock (new path)
    with patch(
        "runsight_core.workflow.build_block_context",
        wraps=build_block_context,
    ) as mock_build_ctx:
        result_state = await execute_block(block, state, block_execution_ctx)

    assert mock_build_ctx.called, (
        "execute_block must call build_block_context for GateBlock (new dispatch path)"
    )
    # Outer contract: still returns WorkflowState
    assert isinstance(result_state, WorkflowState)
    assert "gate1" in result_state.results


@pytest.mark.asyncio
async def test_execute_block_gateblock_state_has_correct_exit_handle(
    mock_runner, gate_soul, block_execution_ctx
):
    """After execute_block with GateBlock, state.results[gate_id].exit_handle must be 'pass'."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
        cost_usd=0.01,
        total_tokens=100,
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="evaluate"),
        results={"prior_block": BlockResult(output="Good content")},
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert "gate1" in result_state.results
    assert result_state.results["gate1"].exit_handle == "pass", (
        f"Expected exit_handle='pass' in state after PASS gate, got {result_state.results['gate1'].exit_handle!r}"
    )


@pytest.mark.asyncio
async def test_execute_block_gateblock_fail_routing(mock_runner, gate_soul, block_execution_ctx):
    """After execute_block with GateBlock on FAIL, state.results contains exit_handle='fail'."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="FAIL: poor structure",
        cost_usd=0.01,
        total_tokens=80,
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="evaluate"),
        results={"prior_block": BlockResult(output="Weak content")},
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert "gate1" in result_state.results
    assert result_state.results["gate1"].exit_handle == "fail", (
        f"Expected exit_handle='fail' in state after FAIL gate, got {result_state.results['gate1'].exit_handle!r}"
    )


@pytest.mark.asyncio
async def test_execute_block_gateblock_accumulates_cost(
    mock_runner, gate_soul, block_execution_ctx
):
    """execute_block via GateBlock new path must accumulate cost_usd in state."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
        cost_usd=0.03,
        total_tokens=300,
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="evaluate"),
        results={"prior_block": BlockResult(output="Content")},
        total_cost_usd=1.0,
        total_tokens=500,
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert result_state.total_cost_usd == pytest.approx(1.03), (
        f"Expected total_cost_usd=1.03 after gate, got {result_state.total_cost_usd}"
    )
    assert result_state.total_tokens == 800, (
        f"Expected total_tokens=800 after gate, got {result_state.total_tokens}"
    )


@pytest.mark.asyncio
async def test_execute_block_uses_new_path_for_synthesize_block(mock_runner, gate_soul):
    """execute_block MUST call build_block_context for SynthesizeBlock (migrated in RUN-887)."""
    from runsight_core.block_io import build_block_context
    from runsight_core.blocks.synthesize import SynthesizeBlock

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth_eval",
        soul_id="gate_soul",
        output="Synthesized output",
    )

    sample_soul = Soul(id="synth_soul", role="Synthesizer", system_prompt="Synthesize things.")
    synth_block = SynthesizeBlock("synth1", ["prior_block"], sample_soul, mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="synthesize"),
        results={"prior_block": BlockResult(output="something")},
    )
    ctx = BlockExecutionContext(
        workflow_name="test",
        blocks={"synth1": synth_block},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )

    # build_block_context MUST be called for SynthesizeBlock (new dispatch path, RUN-887)
    with patch(
        "runsight_core.workflow.build_block_context",
        wraps=build_block_context,
    ) as mock_bbc:
        result_state = await execute_block(synth_block, state, ctx)

    assert mock_bbc.called, (
        "execute_block must call build_block_context for SynthesizeBlock (new dispatch path, RUN-887)"
    )
    assert isinstance(result_state, WorkflowState)


@pytest.mark.asyncio
async def test_execute_block_end_to_end_gate_routing_workflow(mock_runner, gate_soul):
    """Full workflow: LinearBlock -> GateBlock with conditional routing on pass/fail."""
    from runsight_core.blocks.linear import LinearBlock
    from runsight_core.workflow import Workflow

    sample_soul = Soul(id="writer_soul", role="Writer", system_prompt="Write content.")

    mock_runner.execute_task.side_effect = [
        # LinearBlock call
        ExecutionResult(
            task_id="t1",
            soul_id="writer_soul",
            output="Draft content here.",
            cost_usd=0.01,
            total_tokens=100,
        ),
        # GateBlock call
        ExecutionResult(
            task_id="gate_eval",
            soul_id="gate_soul",
            output="PASS",
            cost_usd=0.02,
            total_tokens=150,
        ),
        # Pass-through block
        ExecutionResult(
            task_id="t_pass",
            soul_id="writer_soul",
            output="Publishing approved content.",
            cost_usd=0.01,
            total_tokens=50,
        ),
    ]

    linear_block = LinearBlock("writer", sample_soul, mock_runner)
    gate_block = GateBlock("quality_gate", gate_soul, "writer", mock_runner)
    publish_block = LinearBlock("publish", sample_soul, mock_runner)
    revise_block = LinearBlock("revise", sample_soul, mock_runner)

    wf = Workflow("gate_routing_workflow")
    wf.add_block(linear_block)
    wf.add_block(gate_block)
    wf.add_block(publish_block)
    wf.add_block(revise_block)
    wf.add_transition("writer", "quality_gate")
    wf.add_conditional_transition(
        "quality_gate",
        {"pass": "publish", "fail": "revise"},
    )
    wf.add_transition("publish", None)
    wf.add_transition("revise", None)
    wf.set_entry("writer")

    task = Task(id="t1", instruction="Write a report")
    state = WorkflowState(current_task=task)

    final_state = await wf.run(state)

    assert isinstance(final_state, WorkflowState)
    assert "writer" in final_state.results
    assert final_state.results["writer"].output == "Draft content here."
    assert "quality_gate" in final_state.results
    assert final_state.results["quality_gate"].exit_handle == "pass"
    # On PASS, publish block must execute; revise block must not
    assert "publish" in final_state.results, "Publish block must execute when gate passes"
    assert "revise" not in final_state.results, "Revise block must NOT execute when gate passes"


@pytest.mark.asyncio
async def test_execute_block_end_to_end_gate_fail_routing_workflow(mock_runner, gate_soul):
    """Full workflow: LinearBlock -> GateBlock routing to revise on FAIL."""
    from runsight_core.blocks.linear import LinearBlock
    from runsight_core.workflow import Workflow

    sample_soul = Soul(id="writer_soul", role="Writer", system_prompt="Write content.")

    mock_runner.execute_task.side_effect = [
        # LinearBlock call
        ExecutionResult(
            task_id="t1",
            soul_id="writer_soul",
            output="Poor draft content.",
            cost_usd=0.01,
            total_tokens=100,
        ),
        # GateBlock call
        ExecutionResult(
            task_id="gate_eval",
            soul_id="gate_soul",
            output="FAIL: needs improvement",
            cost_usd=0.02,
            total_tokens=150,
        ),
        # Revise block
        ExecutionResult(
            task_id="t_revise",
            soul_id="writer_soul",
            output="Revised content.",
            cost_usd=0.01,
            total_tokens=50,
        ),
    ]

    linear_block = LinearBlock("writer", sample_soul, mock_runner)
    gate_block = GateBlock("quality_gate", gate_soul, "writer", mock_runner)
    publish_block = LinearBlock("publish", sample_soul, mock_runner)
    revise_block = LinearBlock("revise", sample_soul, mock_runner)

    wf = Workflow("gate_fail_workflow")
    wf.add_block(linear_block)
    wf.add_block(gate_block)
    wf.add_block(publish_block)
    wf.add_block(revise_block)
    wf.add_transition("writer", "quality_gate")
    wf.add_conditional_transition(
        "quality_gate",
        {"pass": "publish", "fail": "revise"},
    )
    wf.add_transition("publish", None)
    wf.add_transition("revise", None)
    wf.set_entry("writer")

    task = Task(id="t1", instruction="Write a report")
    state = WorkflowState(current_task=task)

    final_state = await wf.run(state)

    assert isinstance(final_state, WorkflowState)
    assert "quality_gate" in final_state.results
    assert final_state.results["quality_gate"].exit_handle == "fail", (
        f"Expected exit_handle='fail' after FAIL gate, got {final_state.results['quality_gate'].exit_handle!r}"
    )
    # On FAIL, revise block must execute; publish block must not
    assert "revise" in final_state.results, "Revise block must execute when gate fails"
    assert "publish" not in final_state.results, "Publish block must NOT execute when gate fails"


@pytest.mark.asyncio
async def test_execute_block_gateblock_apply_block_output_called(
    mock_runner, gate_soul, block_execution_ctx
):
    """execute_block must call apply_block_output for GateBlock (new path)."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="gate_eval",
        soul_id="gate_soul",
        output="PASS",
        cost_usd=0.02,
        total_tokens=200,
    )

    block = GateBlock("gate1", gate_soul, "prior_block", mock_runner)
    state = WorkflowState(
        current_task=Task(id="t1", instruction="evaluate"),
        results={"prior_block": BlockResult(output="Content")},
        total_cost_usd=0.10,
        total_tokens=100,
    )

    apply_calls = []
    original_apply = apply_block_output

    def tracking_apply(s, block_id, output):
        apply_calls.append(block_id)
        return original_apply(s, block_id, output)

    with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
        result_state = await execute_block(block, state, block_execution_ctx)

    # KEY: apply_block_output must have been called for GateBlock (new path)
    assert "gate1" in apply_calls, (
        "execute_block must call apply_block_output for GateBlock (new dispatch path)"
    )
    assert isinstance(result_state, WorkflowState)
    assert result_state.total_cost_usd == pytest.approx(0.12)
    assert result_state.total_tokens == 300
