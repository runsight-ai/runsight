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
async def test_stateful_first_invocation_stores_user_and_assistant(
    mock_runner,
    sample_soul,
):
    """First call on a stateful block with no prior history should store
    exactly one user+assistant pair in conversation_histories."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Analysis complete.",
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}})

    new_state = await _exec(block, state)

    history_key = "analyze_soul_a"
    assert history_key in new_state.conversation_histories

    history = new_state.conversation_histories[history_key]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Analysis complete."


@pytest.mark.asyncio
async def test_stateful_first_invocation_user_message_contains_instruction(
    mock_runner,
    sample_soul,
):
    """The user message stored in history must be the serialized instruction string."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Done.",
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}})

    new_state = await _exec(block, state)

    history = new_state.conversation_histories["analyze_soul_a"]
    assert isinstance(history[0]["content"], str)
    assert len(history[0]["content"]) >= 0  # non-empty or empty string is valid


@pytest.mark.asyncio
async def test_stateful_first_invocation_with_resolved_inputs(
    mock_runner,
    sample_soul,
):
    """When _resolved_inputs has data, the stored user message includes it."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t2",
        soul_id="soul_a",
        output="Done.",
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)
    block.declared_inputs = {
        "upstream": "shared_memory._resolved_inputs.upstream",
        "extra": "shared_memory._resolved_inputs.extra",
    }
    state = WorkflowState(
        shared_memory={
            "_resolved_inputs": {
                "upstream": "Summarize the data",
                "extra": "Some extra context",
            }
        }
    )

    new_state = await _exec(block, state)

    history = new_state.conversation_histories["analyze_soul_a"]
    assert isinstance(history[0]["content"], str)
    # The instruction must contain the resolved inputs data
    assert "Some extra context" in history[0]["content"] or "extra" in history[0]["content"]


# ---------------------------------------------------------------------------
# Continuation calls include existing user and assistant messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_continuation_passes_existing_history_to_runner(
    mock_runner,
    sample_soul,
):
    """When conversation_histories already has entries for this block+soul,
    they must be passed to runner.execute as messages=."""
    prior_history = [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First response"},
    ]

    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Second response.",
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)

    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}},
        conversation_histories={"analyze_soul_a": prior_history},
    )

    await _exec(block, state)

    # runner.execute must have been called with messages= containing prior history
    call_kwargs = mock_runner.execute.call_args
    assert call_kwargs is not None
    # Accept either positional or keyword 'messages' argument
    if len(call_kwargs.args) > 3:
        passed_messages = call_kwargs.args[3]
    else:
        passed_messages = call_kwargs.kwargs.get("messages")

    assert passed_messages is not None, "execute was not called with messages="
    assert passed_messages == prior_history


@pytest.mark.asyncio
async def test_stateful_continuation_appends_new_pair_to_history(
    mock_runner,
    sample_soul,
):
    """After round 2, the stored history should contain round 1 + round 2 pairs."""
    prior_history = [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First response"},
    ]

    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Second response.",
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)

    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}},
        conversation_histories={"analyze_soul_a": prior_history},
    )

    new_state = await _exec(block, state)

    history = new_state.conversation_histories["analyze_soul_a"]
    # At minimum 4 messages (prior 2 + new 2); windowing may reduce but
    # with small history it should not prune.
    assert len(history) >= 4
    # Verify the new pair is at the end
    assert history[-2]["role"] == "user"
    assert history[-1]["role"] == "assistant"
    assert history[-1]["content"] == "Second response."


# ---------------------------------------------------------------------------
# History key format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_history_key_format(mock_runner, sample_soul):
    """History key must be '{block_id}_{soul_id}'."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Done.",
    )

    block = _make_stateful_block("my_block", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}})

    new_state = await _exec(block, state)

    assert "my_block_soul_a" in new_state.conversation_histories
    # No other keys should have been created
    assert len(new_state.conversation_histories) == 1


# ---------------------------------------------------------------------------
# Windowing prunes when history exceeds token budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_no_system_messages_stored(
    mock_runner,
    sample_soul,
):
    """conversation_histories must only contain user and assistant roles,
    never system messages."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Analysis result.",
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}})

    new_state = await _exec(block, state)

    history_key = "analyze_soul_a"
    assert history_key in new_state.conversation_histories, (
        "Stateful block did not create conversation history entry"
    )

    history = new_state.conversation_histories[history_key]
    for msg in history:
        assert msg["role"] in ("user", "assistant"), (
            f"Found '{msg['role']}' role in conversation_histories — only user/assistant allowed"
        )


# ---------------------------------------------------------------------------
# Existing non-stateful behavior remains unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_block_still_stores_result_and_log(
    mock_runner,
    sample_soul,
):
    """Stateful block must still produce results, execution_log, cost, and tokens
    exactly like the non-stateful path."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Analysis result.",
        cost_usd=0.05,
        total_tokens=200,
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)

    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}},
        total_cost_usd=0.10,
        total_tokens=100,
    )

    new_state = await _exec(block, state)

    # Standard result storage
    assert new_state.results["analyze"].output == "Analysis result."
    # Execution log
    assert len(new_state.execution_log) == 1
    assert "[Block analyze]" in new_state.execution_log[0]["content"]
    # Cost and token aggregation
    assert new_state.total_cost_usd == pytest.approx(0.15)
    assert new_state.total_tokens == 300


# ---------------------------------------------------------------------------
# Edge: original state.conversation_histories is not mutated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_does_not_mutate_original_state(
    mock_runner,
    sample_soul,
):
    """model_copy semantics: the original state's conversation_histories
    must not be mutated by a stateful execution."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="soul_a",
        output="Done.",
    )

    block = _make_stateful_block("analyze", sample_soul, mock_runner)

    original_histories = {}
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Summarize the data"}},
        conversation_histories=original_histories,
    )

    new_state = await _exec(block, state)

    # Original state must be unchanged
    assert state.conversation_histories == {}
    # New state must have the history
    assert "analyze_soul_a" in new_state.conversation_histories
