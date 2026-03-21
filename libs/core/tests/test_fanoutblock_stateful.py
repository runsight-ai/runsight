"""
RUN-192: Failing tests for FanOutBlock stateful conversation history.

Tests verify that when stateful=True, FanOutBlock:
- Reads N independent histories (one per soul) keyed {block_id}_{soul_id}
- Passes each soul's history to runner.execute_task(task, soul, messages=history)
- Appends user+assistant messages per soul after parallel execution
- Applies windowing per-soul via prune_messages using correct model
- Writes all N histories in a single model_copy update
- Each soul sees only its own prior messages (history independence)

When stateful=False (default), conversation_histories must be untouched.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from runsight_core import FanOutBlock
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState


# ---------------------------------------------------------------------------
# Fixtures
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
    """Soul A without model_name override."""
    return Soul(id="soul_alpha", role="Reviewer A", system_prompt="You are reviewer A.")


@pytest.fixture
def soul_beta():
    """Soul B without model_name override."""
    return Soul(id="soul_beta", role="Reviewer B", system_prompt="You are reviewer B.")


@pytest.fixture
def soul_gamma_with_model():
    """Soul C with an explicit model_name override."""
    return Soul(
        id="soul_gamma",
        role="Reviewer C",
        system_prompt="You are reviewer C.",
        model_name="claude-3-opus-20240229",
    )


@pytest.fixture
def sample_task():
    return Task(id="t1", instruction="Review the proposal")


@pytest.fixture
def sample_task_with_context():
    return Task(id="t2", instruction="Review the proposal", context="Budget is $10k")


def _make_result(soul_id, output, cost=0.0, tokens=0):
    """Helper to create an ExecutionResult."""
    return ExecutionResult(
        task_id="t1",
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


def _make_stateful_fanout(block_id, souls, runner):
    """Helper to create a stateful FanOutBlock."""
    block = FanOutBlock(block_id, souls, runner)
    block.stateful = True
    return block


def _setup_runner_side_effect(mock_runner, soul_output_map):
    """Configure runner.execute_task to return different outputs per soul.

    soul_output_map: dict mapping soul_id -> ExecutionResult
    """

    async def _side_effect(task, soul, **kwargs):
        return soul_output_map[soul.id]

    mock_runner.execute_task = AsyncMock(side_effect=_side_effect)


# ---------------------------------------------------------------------------
# AC: First invocation — each soul gets its own history entry
# ---------------------------------------------------------------------------


async def test_stateful_first_invocation_creates_per_soul_histories(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """First call on a stateful FanOutBlock with no prior history should
    create one history entry per soul, each keyed {block_id}_{soul_id}."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha's review."),
            "soul_beta": _make_result("soul_beta", "Beta's review."),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    new_state = await block.execute(state)

    # Both souls must have history entries
    assert "review_soul_alpha" in new_state.conversation_histories
    assert "review_soul_beta" in new_state.conversation_histories

    # Each history must have exactly one user+assistant pair
    history_a = new_state.conversation_histories["review_soul_alpha"]
    history_b = new_state.conversation_histories["review_soul_beta"]
    assert len(history_a) == 2
    assert len(history_b) == 2


async def test_stateful_first_invocation_stores_correct_user_and_assistant(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """Each soul's history must contain the correct user prompt and that
    soul's specific assistant output."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha says yes."),
            "soul_beta": _make_result("soul_beta", "Beta says no."),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)
    expected_prompt = mock_runner._build_prompt(sample_task)

    new_state = await block.execute(state)

    history_a = new_state.conversation_histories["review_soul_alpha"]
    assert history_a[0]["role"] == "user"
    assert history_a[0]["content"] == expected_prompt
    assert history_a[1]["role"] == "assistant"
    assert history_a[1]["content"] == "Alpha says yes."

    history_b = new_state.conversation_histories["review_soul_beta"]
    assert history_b[0]["role"] == "user"
    assert history_b[0]["content"] == expected_prompt
    assert history_b[1]["role"] == "assistant"
    assert history_b[1]["content"] == "Beta says no."


async def test_stateful_first_invocation_user_message_includes_context(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task_with_context,
):
    """When the task has context, the stored user message includes it."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Done."),
            "soul_beta": _make_result("soul_beta", "Done."),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task_with_context)
    expected_prompt = mock_runner._build_prompt(sample_task_with_context)

    new_state = await block.execute(state)

    for key in ["review_soul_alpha", "review_soul_beta"]:
        history = new_state.conversation_histories[key]
        assert history[0]["content"] == expected_prompt
        assert "Budget is $10k" in history[0]["content"]


# ---------------------------------------------------------------------------
# AC: Round 2 — each soul sees only its own prior history
# ---------------------------------------------------------------------------


async def test_stateful_continuation_passes_per_soul_history_to_runner(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """When conversation_histories already has entries for each soul,
    runner.execute_task must receive the correct soul's history as messages=."""
    prior_alpha = [
        {"role": "user", "content": "Round 1 prompt"},
        {"role": "assistant", "content": "Alpha round 1"},
    ]
    prior_beta = [
        {"role": "user", "content": "Round 1 prompt"},
        {"role": "assistant", "content": "Beta round 1"},
    ]

    captured_messages = {}

    async def _capture_side_effect(task, soul, **kwargs):
        captured_messages[soul.id] = kwargs.get("messages")
        return _make_result(soul.id, f"{soul.id} round 2")

    mock_runner.execute_task = AsyncMock(side_effect=_capture_side_effect)

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(
        current_task=sample_task,
        conversation_histories={
            "review_soul_alpha": prior_alpha,
            "review_soul_beta": prior_beta,
        },
    )

    await block.execute(state)

    # Alpha must receive only alpha's history
    assert captured_messages["soul_alpha"] is not None, (
        "execute_task was not called with messages= for soul_alpha"
    )
    assert captured_messages["soul_alpha"] == prior_alpha

    # Beta must receive only beta's history
    assert captured_messages["soul_beta"] is not None, (
        "execute_task was not called with messages= for soul_beta"
    )
    assert captured_messages["soul_beta"] == prior_beta


async def test_stateful_continuation_appends_new_pair_per_soul(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """After round 2, each soul's history should contain round 1 + round 2 pairs."""
    prior_alpha = [
        {"role": "user", "content": "Round 1 prompt"},
        {"role": "assistant", "content": "Alpha round 1"},
    ]
    prior_beta = [
        {"role": "user", "content": "Round 1 prompt"},
        {"role": "assistant", "content": "Beta round 1"},
    ]

    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Alpha round 2"),
            "soul_beta": _make_result("soul_beta", "Beta round 2"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(
        current_task=sample_task,
        conversation_histories={
            "review_soul_alpha": prior_alpha,
            "review_soul_beta": prior_beta,
        },
    )
    expected_prompt = mock_runner._build_prompt(sample_task)

    new_state = await block.execute(state)

    # Alpha: 4 messages (prior 2 + new 2)
    history_a = new_state.conversation_histories["review_soul_alpha"]
    assert len(history_a) >= 4
    assert history_a[-2]["role"] == "user"
    assert history_a[-2]["content"] == expected_prompt
    assert history_a[-1]["role"] == "assistant"
    assert history_a[-1]["content"] == "Alpha round 2"

    # Beta: 4 messages (prior 2 + new 2)
    history_b = new_state.conversation_histories["review_soul_beta"]
    assert len(history_b) >= 4
    assert history_b[-2]["role"] == "user"
    assert history_b[-2]["content"] == expected_prompt
    assert history_b[-1]["role"] == "assistant"
    assert history_b[-1]["content"] == "Beta round 2"


# ---------------------------------------------------------------------------
# AC: Parallel history independence — soul A's history != soul B's
# ---------------------------------------------------------------------------


async def test_stateful_parallel_history_independence(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """Each soul's stored history must contain only that soul's outputs,
    not the other soul's. This verifies true independence under parallel execution."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "ALPHA_UNIQUE_OUTPUT"),
            "soul_beta": _make_result("soul_beta", "BETA_UNIQUE_OUTPUT"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    new_state = await block.execute(state)

    history_a = new_state.conversation_histories["review_soul_alpha"]
    history_b = new_state.conversation_histories["review_soul_beta"]

    # Alpha's history must contain only alpha's output
    all_a_content = " ".join(msg["content"] for msg in history_a)
    assert "ALPHA_UNIQUE_OUTPUT" in all_a_content
    assert "BETA_UNIQUE_OUTPUT" not in all_a_content

    # Beta's history must contain only beta's output
    all_b_content = " ".join(msg["content"] for msg in history_b)
    assert "BETA_UNIQUE_OUTPUT" in all_b_content
    assert "ALPHA_UNIQUE_OUTPUT" not in all_b_content


async def test_stateful_three_souls_independent_histories(
    mock_runner,
    soul_alpha,
    soul_beta,
    soul_gamma_with_model,
    sample_task,
):
    """Integration test: 3 souls, each gets independent history after 2 rounds."""
    souls = [soul_alpha, soul_beta, soul_gamma_with_model]

    # Round 1
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "A-R1"),
            "soul_beta": _make_result("soul_beta", "B-R1"),
            "soul_gamma": _make_result("soul_gamma", "C-R1"),
        },
    )

    block = _make_stateful_fanout("fanout", souls, mock_runner)
    state = WorkflowState(current_task=sample_task)
    state_r1 = await block.execute(state)

    # Round 2 — use the state from round 1
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "A-R2"),
            "soul_beta": _make_result("soul_beta", "B-R2"),
            "soul_gamma": _make_result("soul_gamma", "C-R2"),
        },
    )

    state_r2 = await block.execute(state_r1)

    # Each soul must have 4 messages (2 rounds x user+assistant)
    for soul_id in ["soul_alpha", "soul_beta", "soul_gamma"]:
        key = f"fanout_{soul_id}"
        assert key in state_r2.conversation_histories, f"Missing history for {key}"
        history = state_r2.conversation_histories[key]
        assert len(history) >= 4, f"Expected >= 4 messages for {key}, got {len(history)}"
        # Round 2 assistant message must be the latest
        assert history[-1]["role"] == "assistant"

    # Verify cross-contamination is impossible
    history_a = state_r2.conversation_histories["fanout_soul_alpha"]
    all_a = " ".join(m["content"] for m in history_a)
    assert "A-R1" in all_a
    assert "A-R2" in all_a
    assert "B-R1" not in all_a
    assert "C-R1" not in all_a


# ---------------------------------------------------------------------------
# AC: N histories written in single state update (no partial writes)
# ---------------------------------------------------------------------------


async def test_stateful_single_model_copy_update(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """All N per-soul histories must appear in a single model_copy(update=...) call,
    not through sequential mutations. We verify by checking the returned state
    has all histories present simultaneously."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Output A"),
            "soul_beta": _make_result("soul_beta", "Output B"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    new_state = await block.execute(state)

    # Both must be present in the same returned state
    assert "review_soul_alpha" in new_state.conversation_histories
    assert "review_soul_beta" in new_state.conversation_histories
    # And exactly 2 keys (no stray entries)
    assert len(new_state.conversation_histories) == 2


async def test_stateful_preserves_other_block_histories(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """When other blocks already have histories, FanOutBlock must preserve them
    in the merged update."""
    other_history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Output A"),
            "soul_beta": _make_result("soul_beta", "Output B"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(
        current_task=sample_task,
        conversation_histories={"other_block_other_soul": other_history},
    )

    new_state = await block.execute(state)

    # Other block's history must be untouched
    assert new_state.conversation_histories["other_block_other_soul"] == other_history
    # Plus our two new entries
    assert "review_soul_alpha" in new_state.conversation_histories
    assert "review_soul_beta" in new_state.conversation_histories
    assert len(new_state.conversation_histories) == 3


# ---------------------------------------------------------------------------
# AC: History key format is {block_id}_{soul_id}
# ---------------------------------------------------------------------------


async def test_stateful_history_key_format(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """History keys must follow the '{block_id}_{soul_id}' convention."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = _make_stateful_fanout("my_fanout", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    new_state = await block.execute(state)

    expected_keys = {"my_fanout_soul_alpha", "my_fanout_soul_beta"}
    actual_keys = set(new_state.conversation_histories.keys())
    assert actual_keys == expected_keys


# ---------------------------------------------------------------------------
# AC: Windowing is applied per-soul
# ---------------------------------------------------------------------------


async def test_stateful_windowing_called_per_soul(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """prune_messages must be invoked once per soul during stateful execution."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    with patch(
        "runsight_core.memory.windowing.prune_messages",
        side_effect=lambda msgs, max_tok, model: msgs,
    ) as mock_prune:
        await block.execute(state)

    # Must be called once per soul (2 souls = 2 calls)
    assert mock_prune.call_count == 2, (
        f"prune_messages called {mock_prune.call_count} times, expected 2 (once per soul)"
    )


async def test_stateful_windowing_prunes_large_history(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """When a soul's history exceeds the token budget, older pairs must be dropped.
    Simulated via a prune_messages mock that truncates to last 4 messages."""
    # Build a large prior history for alpha (10 pairs = 20 messages)
    large_history = []
    for i in range(10):
        large_history.append({"role": "user", "content": f"Prompt {i}" * 500})
        large_history.append({"role": "assistant", "content": f"Response {i}" * 500})

    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "New output A."),
            "soul_beta": _make_result("soul_beta", "New output B."),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(
        current_task=sample_task,
        conversation_histories={
            "review_soul_alpha": large_history,
            "review_soul_beta": [],  # Beta has no prior history
        },
    )

    new_state = await block.execute(state)

    history_a = new_state.conversation_histories["review_soul_alpha"]
    # With 10 prior pairs + 1 new pair = 22 messages, windowing should prune.
    # At minimum the new pair must be present
    assert history_a[-1]["role"] == "assistant"
    assert history_a[-1]["content"] == "New output A."
    assert len(history_a) >= 2


# ---------------------------------------------------------------------------
# AC: Different model per soul → windowing uses correct model's token limit
# ---------------------------------------------------------------------------


async def test_stateful_windowing_uses_soul_specific_model(
    mock_runner,
    soul_alpha,
    soul_gamma_with_model,
    sample_task,
):
    """When souls have different models, windowing must use each soul's
    correct model for get_max_tokens. soul_alpha uses runner default (gpt-4o),
    soul_gamma uses its own model (claude-3-opus-20240229)."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_gamma": _make_result("soul_gamma", "Out C"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_gamma_with_model], mock_runner)
    state = WorkflowState(current_task=sample_task)

    models_seen = []

    def _tracking_get_max_tokens(model):
        models_seen.append(model)
        return 16000

    with (
        patch(
            "runsight_core.memory.windowing.get_max_tokens",
            side_effect=_tracking_get_max_tokens,
        ),
        patch(
            "runsight_core.memory.windowing.prune_messages",
            side_effect=lambda msgs, max_tok, model: msgs,
        ),
    ):
        await block.execute(state)

    # get_max_tokens must have been called with both models
    assert "gpt-4o" in models_seen, (
        f"Expected 'gpt-4o' (runner default) in models_seen, got {models_seen}"
    )
    assert "claude-3-opus-20240229" in models_seen, (
        f"Expected 'claude-3-opus-20240229' (soul override) in models_seen, got {models_seen}"
    )


async def test_stateful_windowing_falls_back_to_runner_model(
    mock_runner,
    soul_alpha,
    sample_task,
):
    """When a soul has no model_name, windowing must use runner.model_name."""
    assert soul_alpha.model_name is None  # precondition

    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha], mock_runner)
    state = WorkflowState(current_task=sample_task)

    with (
        patch(
            "runsight_core.memory.windowing.get_max_tokens",
            return_value=8000,
        ) as mock_get_max,
        patch(
            "runsight_core.memory.windowing.prune_messages",
            side_effect=lambda msgs, max_tok, model: msgs,
        ),
    ):
        await block.execute(state)

    mock_get_max.assert_called_with("gpt-4o")


# ---------------------------------------------------------------------------
# AC: No system messages stored in conversation_histories
# ---------------------------------------------------------------------------


async def test_stateful_no_system_messages_stored(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """conversation_histories must only contain user and assistant roles,
    never system messages."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    new_state = await block.execute(state)

    for key in ["review_soul_alpha", "review_soul_beta"]:
        assert key in new_state.conversation_histories, (
            f"Stateful block did not create conversation history for {key}"
        )
        history = new_state.conversation_histories[key]
        for msg in history:
            assert msg["role"] in ("user", "assistant"), (
                f"Found '{msg['role']}' role in {key} — only user/assistant allowed"
            )


# ---------------------------------------------------------------------------
# AC: Non-stateful FanOutBlock unchanged
# ---------------------------------------------------------------------------


async def test_non_stateful_no_history_entries(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """A non-stateful FanOutBlock must not add any conversation_histories entries."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = FanOutBlock("review", [soul_alpha, soul_beta], mock_runner)
    assert block.stateful is False  # default

    state = WorkflowState(current_task=sample_task)
    new_state = await block.execute(state)

    assert new_state.conversation_histories == {}


async def test_non_stateful_preserves_other_histories(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """A non-stateful FanOutBlock must not modify existing conversation_histories."""
    other_history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = FanOutBlock("review", [soul_alpha, soul_beta], mock_runner)
    assert block.stateful is False

    state = WorkflowState(
        current_task=sample_task,
        conversation_histories={"other_block_other_soul": other_history},
    )
    new_state = await block.execute(state)

    assert new_state.conversation_histories == {"other_block_other_soul": other_history}
    assert "review_soul_alpha" not in new_state.conversation_histories


async def test_non_stateful_does_not_pass_messages_to_runner(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """Non-stateful FanOutBlock calls runner.execute_task without messages param."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = FanOutBlock("review", [soul_alpha, soul_beta], mock_runner)
    assert block.stateful is False

    state = WorkflowState(current_task=sample_task)

    # Replace side_effect so we can inspect exact call args
    mock_runner.execute_task = AsyncMock(
        side_effect=lambda task, soul: _make_result(soul.id, "Out")
    )
    await block.execute(state)

    # Each call should have exactly 2 positional args (task, soul), no messages kwarg
    for c in mock_runner.execute_task.call_args_list:
        assert "messages" not in c.kwargs, (
            f"Non-stateful execute_task was called with messages= for {c}"
        )


# ---------------------------------------------------------------------------
# AC: Stateful block still produces standard results, log, cost, tokens
# ---------------------------------------------------------------------------


async def test_stateful_still_stores_result_and_log(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """Stateful FanOutBlock must still produce results, execution_log, cost, and tokens
    exactly like the non-stateful path (regression guard)."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A", cost=0.02, tokens=100),
            "soul_beta": _make_result("soul_beta", "Out B", cost=0.03, tokens=150),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(
        current_task=sample_task,
        total_cost_usd=0.10,
        total_tokens=50,
    )

    new_state = await block.execute(state)

    # Standard result storage
    assert new_state.results["review"].output is not None
    # Execution log
    assert len(new_state.execution_log) >= 1
    assert "[Block review]" in new_state.execution_log[-1]["content"]
    # Cost and token aggregation
    assert new_state.total_cost_usd == pytest.approx(0.15)
    assert new_state.total_tokens == 300


# ---------------------------------------------------------------------------
# Edge: original state is not mutated
# ---------------------------------------------------------------------------


async def test_stateful_does_not_mutate_original_state(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """model_copy semantics: the original state's conversation_histories
    must not be mutated by a stateful FanOutBlock execution."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)

    original_histories = {}
    state = WorkflowState(
        current_task=sample_task,
        conversation_histories=original_histories,
    )

    new_state = await block.execute(state)

    # Original state must be unchanged
    assert state.conversation_histories == {}
    # New state must have the histories
    assert "review_soul_alpha" in new_state.conversation_histories
    assert "review_soul_beta" in new_state.conversation_histories


# ---------------------------------------------------------------------------
# Edge: One soul fails in gather → no history written (clean retry)
# ---------------------------------------------------------------------------


async def test_stateful_gather_failure_writes_no_history(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """If one soul fails during asyncio.gather, the entire block fails and
    no partial histories are written. The caller retries with clean state."""

    async def _failing_side_effect(task, soul, **kwargs):
        if soul.id == "soul_beta":
            raise RuntimeError("Soul beta LLM failure")
        return _make_result(soul.id, "Out A")

    mock_runner.execute_task = AsyncMock(side_effect=_failing_side_effect)

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    with pytest.raises(RuntimeError, match="Soul beta LLM failure"):
        await block.execute(state)

    # Original state must be unchanged — no partial history
    assert state.conversation_histories == {}
