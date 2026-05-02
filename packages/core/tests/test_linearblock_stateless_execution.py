"""
LinearBlock stateful conversation history behavior.

Tests verify that when stateful=True, LinearBlock:
- Reads existing conversation history from state.conversation_histories
- Passes history to runner.execute(instruction, context, soul, messages=history)
- Appends user+assistant messages after execution
- Applies windowing via fit_to_budget
- Uses correct history key: {block_id}_{soul_id}
- Never stores system messages in conversation_histories
- Falls back to runner.model_name when soul.model_name is None

When stateful=False (default), conversation_histories must be untouched.

LinearBlock reads _resolved_inputs from shared_memory
instead of state.current_task. runner.execute() is used instead of execute_task().
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core import LinearBlock
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState


async def _exec(block, state):
    """Helper: build BlockContext, execute block, apply output to state."""
    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o"
    return runner


@pytest.fixture
def sample_soul():
    """Soul without model_name override (falls back to runner.model_name)."""
    return Soul(
        id="soul_a",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="You analyze things.",
    )


@pytest.fixture
def soul_with_model():
    """Soul with an explicit model_name override."""
    return Soul(
        id="soul_b",
        kind="soul",
        name="Writer",
        role="Writer",
        system_prompt="You write things.",
        model_name="claude-3-opus-20240229",
    )


def _make_stateful_block(block_id, soul, runner):
    """Helper to create a stateful LinearBlock."""
    block = LinearBlock(block_id, soul, runner)
    block.stateful = True
    return block


# ---------------------------------------------------------------------------
# First invocation stores a single user and assistant pair
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_stateful_block_no_history_entries(
    mock_runner,
    sample_soul,
):
    """A non-stateful LinearBlock must not add any conversation_histories entries."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Output.",
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    assert block.stateful is False  # default

    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}})
    new_state = await _exec(block, state)

    assert new_state.conversation_histories == {}


@pytest.mark.asyncio
async def test_non_stateful_block_preserves_other_histories(
    mock_runner,
    sample_soul,
):
    """A non-stateful block must not modify existing conversation_histories from other blocks."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Output.",
    )

    other_history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    block = LinearBlock("analyze", sample_soul, mock_runner)
    assert block.stateful is False

    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}},
        conversation_histories={"other_block_other_soul": other_history},
    )
    new_state = await _exec(block, state)

    # Other block's history should be untouched
    assert new_state.conversation_histories == {"other_block_other_soul": other_history}
    # No new key for this block
    assert "analyze_soul_a" not in new_state.conversation_histories


@pytest.mark.asyncio
async def test_non_stateful_calls_runner_execute_without_messages(
    mock_runner,
    sample_soul,
):
    """Non-stateful block calls runner.execute without messages kwarg."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Output.",
    )

    block = LinearBlock("analyze", sample_soul, mock_runner)
    assert block.stateful is False

    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}})
    await _exec(block, state)

    # Should have been called with (instruction, context, soul) — no messages kwarg
    call_kwargs = mock_runner.execute.call_args
    passed_messages = call_kwargs.kwargs.get("messages")
    assert passed_messages is None, f"Non-stateful block passed messages={passed_messages!r}"


# ---------------------------------------------------------------------------
# Conversation histories do not store system messages
# ---------------------------------------------------------------------------
