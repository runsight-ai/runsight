"""
RUN-887: Failing tests for SynthesizeBlock migration to BlockContext/BlockOutput.

Tests verify that after migration:
AC-1: SynthesizeBlock.execute accepts BlockContext and returns BlockOutput (not WorkflowState)
AC-2: Combined outputs format in ctx.context is identical to current concatenation
AC-3: Missing input_block_ids raises ValueError during context building
AC-4: End-to-end via execute_block produces identical results
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.primitives import Soul
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
def synth_soul():
    return Soul(id="synth_soul", role="Synthesizer", system_prompt="Synthesize everything.")


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


def _make_synth_block_context(
    block_id: str,
    soul: Soul,
    combined_outputs: str,
) -> BlockContext:
    """Helper: build a BlockContext for SynthesizeBlock tests directly."""
    return BlockContext(
        block_id=block_id,
        instruction=(
            "Synthesize the following outputs into a cohesive, unified result. "
            "Identify common themes, resolve conflicts, and provide a comprehensive summary."
        ),
        context=combined_outputs,
        inputs={},
        conversation_history=[],
        soul=soul,
        model_name=soul.model_name or "gpt-4o",
    )


# ---------------------------------------------------------------------------
# AC-1: SynthesizeBlock.execute accepts BlockContext, returns BlockOutput
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesizeblock_execute_accepts_block_context(mock_runner, synth_soul):
    """SynthesizeBlock.execute must accept a BlockContext argument and return BlockOutput."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesized result.",
        cost_usd=0.01,
        total_tokens=100,
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    combined = "=== Output from block_a ===\nOutput A\n\n=== Output from block_b ===\nOutput B"
    ctx = _make_synth_block_context("synth1", synth_soul, combined)

    result = await block.execute(ctx)

    # Must return BlockOutput, NOT WorkflowState
    assert isinstance(result, BlockOutput), (
        f"Expected BlockOutput but got {type(result).__name__}. "
        "SynthesizeBlock.execute must return BlockOutput after RUN-887 migration."
    )


@pytest.mark.asyncio
async def test_synthesizeblock_execute_output_contains_llm_response(mock_runner, synth_soul):
    """BlockOutput.output must contain the LLM response string."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="The unified synthesis.",
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    combined = "=== Output from block_a ===\nA\n\n=== Output from block_b ===\nB"
    ctx = _make_synth_block_context("synth1", synth_soul, combined)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.output == "The unified synthesis."


@pytest.mark.asyncio
async def test_synthesizeblock_execute_populates_cost_and_tokens(mock_runner, synth_soul):
    """BlockOutput.cost_usd and total_tokens must be populated from ExecutionResult."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Done.",
        cost_usd=0.05,
        total_tokens=500,
    )

    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    combined = "=== Output from block_a ===\nOutput A"
    ctx = _make_synth_block_context("synth1", synth_soul, combined)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert result.cost_usd == 0.05
    assert result.total_tokens == 500


@pytest.mark.asyncio
async def test_synthesizeblock_execute_log_entries_contain_block_id(mock_runner, synth_soul):
    """BlockOutput.log_entries must contain at least one entry referencing the block_id."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesis done.",
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    combined = "=== Output from block_a ===\nA\n\n=== Output from block_b ===\nB"
    ctx = _make_synth_block_context("synth1", synth_soul, combined)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert len(result.log_entries) >= 1, (
        "BlockOutput.log_entries must not be empty after synthesize execution"
    )
    assert any("synth1" in entry.get("content", "") for entry in result.log_entries), (
        "Expected log_entries to contain an entry referencing block_id 'synth1'"
    )


@pytest.mark.asyncio
async def test_synthesizeblock_execute_returns_data_not_state(mock_runner, synth_soul):
    """BlockOutput is a pure data object — no WorkflowState fields present."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Output.",
    )

    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    combined = "=== Output from block_a ===\nOutput A"
    ctx = _make_synth_block_context("synth1", synth_soul, combined)

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
# AC-2: Combined outputs format in ctx.context matches current concatenation
# ---------------------------------------------------------------------------


def test_build_block_context_synthesize_two_inputs_format(mock_runner, synth_soul):
    """build_block_context for SynthesizeBlock with 2 inputs must produce
    '=== Output from {bid} ===\\n{output}' joined by '\\n\\n'.
    """
    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
        }
    )

    ctx = build_block_context(block, state)

    assert isinstance(ctx, BlockContext)
    expected = "=== Output from block_a ===\nOutput A\n\n=== Output from block_b ===\nOutput B"
    assert ctx.context == expected, (
        f"Combined outputs format mismatch.\nExpected:\n{expected!r}\nGot:\n{ctx.context!r}"
    )


def test_build_block_context_synthesize_three_inputs_format(mock_runner, synth_soul):
    """build_block_context for SynthesizeBlock with 3 inputs must include all three
    in order, separated by '\\n\\n'.
    """
    block = SynthesizeBlock("synth1", ["block_a", "block_b", "block_c"], synth_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
            "block_c": BlockResult(output="Output C"),
        }
    )

    ctx = build_block_context(block, state)

    assert isinstance(ctx, BlockContext)
    expected = (
        "=== Output from block_a ===\nOutput A"
        "\n\n"
        "=== Output from block_b ===\nOutput B"
        "\n\n"
        "=== Output from block_c ===\nOutput C"
    )
    assert ctx.context == expected, (
        f"Three-input combined outputs format mismatch.\nExpected:\n{expected!r}\nGot:\n{ctx.context!r}"
    )


def test_build_block_context_synthesize_instruction_is_standard(mock_runner, synth_soul):
    """build_block_context for SynthesizeBlock must set the standard synthesis instruction."""
    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    state = WorkflowState(results={"block_a": BlockResult(output="Output A")})

    ctx = build_block_context(block, state)

    assert isinstance(ctx, BlockContext)
    expected_instruction = (
        "Synthesize the following outputs into a cohesive, unified result. "
        "Identify common themes, resolve conflicts, and provide a comprehensive summary."
    )
    assert ctx.instruction == expected_instruction, (
        f"Expected standard synthesis instruction.\nGot: {ctx.instruction!r}"
    )


def test_build_block_context_synthesize_populates_block_id(mock_runner, synth_soul):
    """build_block_context must set ctx.block_id to the SynthesizeBlock's block_id."""
    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    state = WorkflowState(results={"block_a": BlockResult(output="Output A")})

    ctx = build_block_context(block, state)

    assert ctx.block_id == "synth1", f"Expected block_id='synth1', got {ctx.block_id!r}"


def test_build_block_context_synthesize_populates_soul(mock_runner, synth_soul):
    """build_block_context must propagate the soul to the BlockContext."""
    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    state = WorkflowState(results={"block_a": BlockResult(output="Output A")})

    ctx = build_block_context(block, state)

    assert ctx.soul == synth_soul, f"Expected ctx.soul to be the synthesizer soul, got {ctx.soul!r}"


def test_build_block_context_synthesize_raw_string_result(mock_runner, synth_soul):
    """build_block_context handles raw string in state.results (not wrapped in BlockResult)."""
    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    # Raw string (not BlockResult) — matches legacy behavior in current SynthesizeBlock
    state = WorkflowState(results={"block_a": "Raw string output"})

    ctx = build_block_context(block, state)

    assert isinstance(ctx, BlockContext)
    assert "Raw string output" in ctx.context


# ---------------------------------------------------------------------------
# AC-3: Missing input_block_ids raises ValueError during context building
# ---------------------------------------------------------------------------


def test_build_block_context_synthesize_missing_one_input_raises(mock_runner, synth_soul):
    """build_block_context must raise ValueError when one of the input_block_ids is absent."""
    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={"block_a": BlockResult(output="Output A")}
        # block_b deliberately missing
    )

    with pytest.raises(ValueError) as exc_info:
        build_block_context(block, state)

    error_msg = str(exc_info.value)
    assert "block_b" in error_msg, (
        f"ValueError must mention the missing block id 'block_b'. Got: {error_msg!r}"
    )


def test_build_block_context_synthesize_missing_all_inputs_raises(mock_runner, synth_soul):
    """build_block_context must raise ValueError when all input_block_ids are absent."""
    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(results={})

    with pytest.raises(ValueError):
        build_block_context(block, state)


def test_build_block_context_synthesize_error_message_lists_available(mock_runner, synth_soul):
    """ValueError from missing inputs must include available block ids for debugging."""
    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={"block_a": BlockResult(output="Output A"), "other_block": BlockResult(output="X")}
        # block_b missing; other_block is present
    )

    with pytest.raises(ValueError) as exc_info:
        build_block_context(block, state)

    error_msg = str(exc_info.value)
    # The error should name the missing block
    assert "block_b" in error_msg, f"Expected 'block_b' in error message. Got: {error_msg!r}"
    # Helpful: should also reference available keys
    assert "block_a" in error_msg or "other_block" in error_msg or "Available" in error_msg, (
        f"Expected available keys mentioned in error. Got: {error_msg!r}"
    )


# ---------------------------------------------------------------------------
# AC-4: End-to-end via execute_block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_block_dispatches_synthesizeblock_via_new_path(
    mock_runner, synth_soul, block_execution_ctx
):
    """execute_block must route SynthesizeBlock through build_block_context + apply_block_output."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesized result.",
        cost_usd=0.02,
        total_tokens=200,
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
        }
    )

    with patch(
        "runsight_core.workflow.build_block_context",
        wraps=build_block_context,
    ) as mock_build_ctx:
        result_state = await execute_block(block, state, block_execution_ctx)

    assert mock_build_ctx.called, (
        "execute_block must call build_block_context for SynthesizeBlock (new dispatch path)"
    )
    # Outer contract: still returns WorkflowState
    assert isinstance(result_state, WorkflowState)
    assert "synth1" in result_state.results


@pytest.mark.asyncio
async def test_execute_block_synthesizeblock_state_has_output(
    mock_runner, synth_soul, block_execution_ctx
):
    """After execute_block with SynthesizeBlock, state.results[synth_id].output is the LLM output."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Cohesive final synthesis.",
        cost_usd=0.01,
        total_tokens=100,
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
        }
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert "synth1" in result_state.results
    assert isinstance(result_state.results["synth1"], BlockResult)
    assert result_state.results["synth1"].output == "Cohesive final synthesis."


@pytest.mark.asyncio
async def test_execute_block_synthesizeblock_accumulates_cost(
    mock_runner, synth_soul, block_execution_ctx
):
    """execute_block via SynthesizeBlock new path must accumulate cost_usd in state."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesis.",
        cost_usd=0.03,
        total_tokens=300,
    )

    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    state = WorkflowState(
        results={"block_a": BlockResult(output="Output A")},
        total_cost_usd=1.0,
        total_tokens=500,
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert result_state.total_cost_usd == pytest.approx(1.03), (
        f"Expected total_cost_usd=1.03 after synth, got {result_state.total_cost_usd}"
    )
    assert result_state.total_tokens == 800, (
        f"Expected total_tokens=800 after synth, got {result_state.total_tokens}"
    )


@pytest.mark.asyncio
async def test_execute_block_synthesizeblock_apply_block_output_called(
    mock_runner, synth_soul, block_execution_ctx
):
    """execute_block must call apply_block_output for SynthesizeBlock (new path)."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesis.",
        cost_usd=0.02,
        total_tokens=200,
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
        },
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

    assert "synth1" in apply_calls, (
        "execute_block must call apply_block_output for SynthesizeBlock (new dispatch path)"
    )
    assert isinstance(result_state, WorkflowState)
    assert result_state.total_cost_usd == pytest.approx(0.12)
    assert result_state.total_tokens == 300


@pytest.mark.asyncio
async def test_execute_block_synthesizeblock_combined_context_passed_to_llm(
    mock_runner, synth_soul, block_execution_ctx
):
    """The combined outputs must be passed as context to execute_task (identical to old path)."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesized.",
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
        }
    )

    await execute_block(block, state, block_execution_ctx)

    # Verify runner.execute_task was called and the task contains combined outputs
    assert mock_runner.execute_task.called
    call_args = mock_runner.execute_task.call_args
    task_arg = call_args[0][0]  # First positional arg is Task
    assert "Output A" in task_arg.context, "Task context must include 'Output A' from block_a"
    assert "Output B" in task_arg.context, "Task context must include 'Output B' from block_b"
    assert "=== Output from block_a ===" in task_arg.context
    assert "=== Output from block_b ===" in task_arg.context


@pytest.mark.asyncio
async def test_execute_block_synthesizeblock_execution_log_extended(
    mock_runner, synth_soul, block_execution_ctx
):
    """execute_block via SynthesizeBlock must extend state.execution_log."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesis.",
    )

    block = SynthesizeBlock("synth1", ["block_a"], synth_soul, mock_runner)
    state = WorkflowState(
        results={"block_a": BlockResult(output="Output A")},
        execution_log=[{"role": "system", "content": "Prior log entry"}],
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    assert isinstance(result_state, WorkflowState)
    assert len(result_state.execution_log) >= 2, (
        "execution_log must be extended by SynthesizeBlock execution"
    )
    assert result_state.execution_log[0]["content"] == "Prior log entry"
    assert any("synth1" in e.get("content", "") for e in result_state.execution_log[1:]), (
        "New log entry must reference block_id 'synth1'"
    )


@pytest.mark.asyncio
async def test_execute_block_synthesizeblock_missing_input_raises_before_llm_call(
    mock_runner, synth_soul, block_execution_ctx
):
    """execute_block must raise ValueError for missing inputs before calling the LLM."""
    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={"block_a": BlockResult(output="Output A")}
        # block_b missing
    )

    with pytest.raises(ValueError) as exc_info:
        await execute_block(block, state, block_execution_ctx)

    assert "block_b" in str(exc_info.value)
    # LLM must NOT have been called
    mock_runner.execute_task.assert_not_called()


@pytest.mark.asyncio
async def test_execute_block_preserves_prior_results_after_synthesize(
    mock_runner, synth_soul, block_execution_ctx
):
    """execute_block via SynthesizeBlock must preserve all prior state.results entries."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth1_synthesis",
        soul_id="synth_soul",
        output="Synthesized.",
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], synth_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
        }
    )

    result_state = await execute_block(block, state, block_execution_ctx)

    # All prior results must still be present
    assert "block_a" in result_state.results
    assert result_state.results["block_a"].output == "Output A"
    assert "block_b" in result_state.results
    assert result_state.results["block_b"].output == "Output B"
    # And the new synth result is added
    assert "synth1" in result_state.results
    assert result_state.results["synth1"].output == "Synthesized."
