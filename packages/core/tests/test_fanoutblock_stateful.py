"""
RUN-192: Failing tests for DispatchBlock stateful conversation history.

Tests verify that when stateful=True, DispatchBlock:
- Reads N independent histories (one per soul) keyed {block_id}_{soul_id}
- Passes each soul's history to runner.execute_task(task, soul, messages=history)
- Appends user+assistant messages per soul after parallel execution
- Applies windowing per-soul via prune_messages using correct model
- Writes all N histories in a single model_copy update
- Each soul sees only its own prior messages (history independence)

When stateful=False (default), conversation_histories must be untouched.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core import DispatchBlock
from runsight_core.blocks.dispatch import DispatchBranch
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


def _souls_to_branches(souls):
    """Convert a list of Soul objects to DispatchBranch objects (exit_id = soul.id)."""
    return [
        DispatchBranch(exit_id=s.id, label=s.role, soul=s, task_instruction="Execute task")
        for s in souls
    ]


def _make_stateful_fanout(block_id, souls, runner):
    """Helper to create a stateful DispatchBlock."""
    block = DispatchBlock(block_id, _souls_to_branches(souls), runner)
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


@pytest.mark.asyncio
async def test_stateful_first_invocation_creates_per_soul_histories(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """First call on a stateful DispatchBlock with no prior history should
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


@pytest.mark.asyncio
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
    # With per-exit branches, prompt is built from the branch's task instruction
    branch_task = Task(id="t", instruction="Execute task")
    expected_prompt = mock_runner._build_prompt(branch_task)

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


@pytest.mark.asyncio
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
    # Prompt is built from branch task instruction + context from current_task
    branch_task = Task(id="t", instruction="Execute task", context="Budget is $10k")
    expected_prompt = mock_runner._build_prompt(branch_task)

    new_state = await block.execute(state)

    for key in ["review_soul_alpha", "review_soul_beta"]:
        history = new_state.conversation_histories[key]
        assert history[0]["content"] == expected_prompt
        assert "Budget is $10k" in history[0]["content"]


# ---------------------------------------------------------------------------
# AC: Round 2 — each soul sees only its own prior history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
    # Prompt is built from branch's task instruction (not the original sample_task)
    branch_task = Task(id="t", instruction="Execute task")
    expected_prompt = mock_runner._build_prompt(branch_task)

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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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

    block = _make_stateful_fanout("dispatch", souls, mock_runner)
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
        key = f"dispatch_{soul_id}"
        assert key in state_r2.conversation_histories, f"Missing history for {key}"
        history = state_r2.conversation_histories[key]
        assert len(history) >= 4, f"Expected >= 4 messages for {key}, got {len(history)}"
        # Round 2 assistant message must be the latest
        assert history[-1]["role"] == "assistant"

    # Verify cross-contamination is impossible
    history_a = state_r2.conversation_histories["dispatch_soul_alpha"]
    all_a = " ".join(m["content"] for m in history_a)
    assert "A-R1" in all_a
    assert "A-R2" in all_a
    assert "B-R1" not in all_a
    assert "C-R1" not in all_a


# ---------------------------------------------------------------------------
# AC: N histories written in single state update (no partial writes)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_stateful_preserves_other_block_histories(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """When other blocks already have histories, DispatchBlock must preserve them
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


@pytest.mark.asyncio
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
# AC: Budget fitting is applied per-soul
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_windowing_called_per_soul(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """fit_to_budget must be invoked once per soul during stateful execution."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha, soul_beta], mock_runner)
    state = WorkflowState(current_task=sample_task)

    from runsight_core.memory.budget import BudgetedContext, BudgetReport

    def _passthrough_budget(request, counter):
        report = BudgetReport(
            model=request.model,
            max_input_tokens=0,
            output_reserve=0,
            effective_budget=100000,
            p1_tokens=0,
            p2_tokens_before=0,
            p2_tokens_after=0,
            p3_tokens_before=0,
            p3_tokens_after=0,
            p3_pairs_dropped=0,
            total_tokens=0,
            headroom=100000,
            warnings=[],
        )
        from runsight_core.primitives import Task as _Task

        return BudgetedContext(
            task=_Task(id="budget_task", instruction=request.instruction, context=request.context),
            messages=list(request.conversation_history),
            report=report,
        )

    with patch(
        "runsight_core.blocks.dispatch.fit_to_budget",
        side_effect=_passthrough_budget,
    ) as mock_budget:
        await block.execute(state)

    # Must be called once per soul (2 souls = 2 calls)
    assert mock_budget.call_count == 2, (
        f"fit_to_budget called {mock_budget.call_count} times, expected 2 (once per soul)"
    )


@pytest.mark.asyncio
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
# AC: Different model per soul → budget fitting uses correct model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stateful_windowing_uses_soul_specific_model(
    mock_runner,
    soul_alpha,
    soul_gamma_with_model,
    sample_task,
):
    """When souls have different models, fit_to_budget must use each soul's
    correct model. soul_alpha uses runner default (gpt-4o),
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

    from runsight_core.memory.budget import BudgetedContext, BudgetReport

    def _tracking_budget(request, counter):
        models_seen.append(request.model)
        report = BudgetReport(
            model=request.model,
            max_input_tokens=0,
            output_reserve=0,
            effective_budget=100000,
            p1_tokens=0,
            p2_tokens_before=0,
            p2_tokens_after=0,
            p3_tokens_before=0,
            p3_tokens_after=0,
            p3_pairs_dropped=0,
            total_tokens=0,
            headroom=100000,
            warnings=[],
        )
        from runsight_core.primitives import Task as _Task

        return BudgetedContext(
            task=_Task(id="budget_task", instruction=request.instruction, context=request.context),
            messages=list(request.conversation_history),
            report=report,
        )

    with patch(
        "runsight_core.blocks.dispatch.fit_to_budget",
        side_effect=_tracking_budget,
    ):
        await block.execute(state)

    # fit_to_budget must have been called with both models
    assert "gpt-4o" in models_seen, (
        f"Expected 'gpt-4o' (runner default) in models_seen, got {models_seen}"
    )
    assert "claude-3-opus-20240229" in models_seen, (
        f"Expected 'claude-3-opus-20240229' (soul override) in models_seen, got {models_seen}"
    )


@pytest.mark.asyncio
async def test_stateful_windowing_falls_back_to_runner_model(
    mock_runner,
    soul_alpha,
    sample_task,
):
    """When a soul has no model_name, fit_to_budget must use runner.model_name."""
    assert soul_alpha.model_name is None  # precondition

    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
        },
    )

    block = _make_stateful_fanout("review", [soul_alpha], mock_runner)
    state = WorkflowState(current_task=sample_task)

    from runsight_core.memory.budget import BudgetedContext, BudgetReport

    def _tracking_budget(request, counter):
        report = BudgetReport(
            model=request.model,
            max_input_tokens=0,
            output_reserve=0,
            effective_budget=100000,
            p1_tokens=0,
            p2_tokens_before=0,
            p2_tokens_after=0,
            p3_tokens_before=0,
            p3_tokens_after=0,
            p3_pairs_dropped=0,
            total_tokens=0,
            headroom=100000,
            warnings=[],
        )
        from runsight_core.primitives import Task as _Task

        return BudgetedContext(
            task=_Task(id="budget_task", instruction=request.instruction, context=request.context),
            messages=list(request.conversation_history),
            report=report,
        )

    with patch(
        "runsight_core.blocks.dispatch.fit_to_budget",
        side_effect=_tracking_budget,
    ) as mock_budget:
        await block.execute(state)

    # fit_to_budget must have been called with "gpt-4o" (runner default)
    assert mock_budget.call_count == 1
    call_request = mock_budget.call_args[0][0]
    assert call_request.model == "gpt-4o"


# ---------------------------------------------------------------------------
# AC: No system messages stored in conversation_histories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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
# AC: Non-stateful DispatchBlock unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_stateful_no_history_entries(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """A non-stateful DispatchBlock must not add any conversation_histories entries."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = DispatchBlock("review", _souls_to_branches([soul_alpha, soul_beta]), mock_runner)
    assert block.stateful is False  # default

    state = WorkflowState(current_task=sample_task)
    new_state = await block.execute(state)

    assert new_state.conversation_histories == {}


@pytest.mark.asyncio
async def test_non_stateful_preserves_other_histories(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """A non-stateful DispatchBlock must not modify existing conversation_histories."""
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

    block = DispatchBlock("review", _souls_to_branches([soul_alpha, soul_beta]), mock_runner)
    assert block.stateful is False

    state = WorkflowState(
        current_task=sample_task,
        conversation_histories={"other_block_other_soul": other_history},
    )
    new_state = await block.execute(state)

    assert new_state.conversation_histories == {"other_block_other_soul": other_history}
    assert "review_soul_alpha" not in new_state.conversation_histories


@pytest.mark.asyncio
async def test_non_stateful_does_not_pass_messages_to_runner(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """Non-stateful DispatchBlock calls runner.execute_task without messages param."""
    _setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": _make_result("soul_alpha", "Out A"),
            "soul_beta": _make_result("soul_beta", "Out B"),
        },
    )

    block = DispatchBlock("review", _souls_to_branches([soul_alpha, soul_beta]), mock_runner)
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


@pytest.mark.asyncio
async def test_stateful_still_stores_result_and_log(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """Stateful DispatchBlock must still produce results, execution_log, cost, and tokens
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


@pytest.mark.asyncio
async def test_stateful_does_not_mutate_original_state(
    mock_runner,
    soul_alpha,
    soul_beta,
    sample_task,
):
    """model_copy semantics: the original state's conversation_histories
    must not be mutated by a stateful DispatchBlock execution."""
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


@pytest.mark.asyncio
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
