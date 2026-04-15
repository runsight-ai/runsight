"""
Failing tests for RUN-884: Implement build_block_context for LinearBlock.

Imports build_block_context from runsight_core.block_io — it does not exist yet.
All tests are expected to fail with ImportError or AttributeError until implemented.

AC coverage:
1. build_block_context produces correct BlockContext for LinearBlock
2. Resolution results are identical to Step._resolve_from_ref for the same inputs (parity test)
3. Conversation history is shallow-copied into BlockContext
4. fit_to_budget called with correct parameters
5. artifact_store passed through from state
6. Unit tests cover: empty inputs, single input, multiple inputs, missing source (ValueError),
   JSON auto-parse
"""

from unittest.mock import MagicMock, patch

import pytest
from runsight_core.artifacts import InMemoryArtifactStore
from runsight_core.block_io import (  # noqa: F401
    BlockContext,
    build_block_context,
)
from runsight_core.blocks.linear import LinearBlock
from runsight_core.memory.budget import BudgetedContext, BudgetReport
from runsight_core.primitives import Soul, Step, Task
from runsight_core.state import BlockResult, WorkflowState

# ==============================================================================
# Helpers
# ==============================================================================

_MODEL = "gpt-4o"


def make_soul(soul_id: str = "soul_1", model_name: str = _MODEL) -> Soul:
    return Soul(
        id=soul_id,
        role="Researcher",
        system_prompt="You are a researcher.",
        model_name=model_name,
    )


def make_runner(model_name: str = _MODEL) -> MagicMock:
    runner = MagicMock()
    runner.model_name = model_name
    return runner


def make_linear_block(block_id: str = "block_a", soul: Soul | None = None) -> LinearBlock:
    if soul is None:
        soul = make_soul()
    return LinearBlock(block_id=block_id, soul=soul, runner=make_runner())


def make_task(instruction: str = "Do the thing", context: str | None = None) -> Task:
    return Task(id="task_1", instruction=instruction, context=context)


def make_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


def make_artifact_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore(run_id="run-test-001")


def _make_budgeted_context(
    instruction: str = "Do the thing",
    context: str | None = None,
    messages: list | None = None,
) -> BudgetedContext:
    """Construct a fake BudgetedContext returned by mocked fit_to_budget."""
    task = Task(id="budget_task", instruction=instruction, context=context)
    report = BudgetReport(
        model=_MODEL,
        max_input_tokens=128000,
        output_reserve=4096,
        effective_budget=100000,
        p1_tokens=10,
        p2_tokens_before=5,
        p2_tokens_after=5,
        p3_tokens_before=0,
        p3_tokens_after=0,
        p3_pairs_dropped=0,
        total_tokens=15,
        headroom=99985,
        warnings=[],
    )
    return BudgetedContext(task=task, messages=messages or [], report=report)


# ==============================================================================
# 1. Input resolution — AC-6 (empty, single, multiple, missing, JSON)
# ==============================================================================


class TestInputResolution:
    """build_block_context resolves declared_inputs from step.declared_inputs."""

    def test_empty_declared_inputs_produces_empty_ctx_inputs(self):
        """When step.declared_inputs is empty, ctx.inputs is an empty dict."""
        block = make_linear_block()
        state = make_state(current_task=make_task())
        step = Step(block, declared_inputs={})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs == {}

    def test_single_input_resolved_from_state_results(self):
        """Single declared input resolves to the matching BlockResult.output."""
        block = make_linear_block()
        state = make_state(
            current_task=make_task(),
            results={"block_upstream": BlockResult(output="defective")},
        )
        step = Step(block, declared_inputs={"reason": "block_upstream"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["reason"] == "defective"

    def test_multiple_inputs_resolved_correctly(self):
        """Multiple declared inputs each resolve to their respective BlockResult.output."""
        block = make_linear_block()
        state = make_state(
            current_task=make_task(),
            results={
                "src_a": BlockResult(output="alpha"),
                "src_b": BlockResult(output="beta"),
            },
        )
        step = Step(block, declared_inputs={"input_a": "src_a", "input_b": "src_b"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["input_a"] == "alpha"
        assert ctx.inputs["input_b"] == "beta"

    def test_missing_source_raises_value_error(self):
        """Referencing a non-existent block_id in declared_inputs raises ValueError."""
        block = make_linear_block()
        state = make_state(current_task=make_task(), results={})
        step = Step(block, declared_inputs={"x": "nonexistent"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            with pytest.raises(ValueError, match="nonexistent"):
                build_block_context(block, state, step=step)

    def test_json_auto_parse_dot_path_resolution(self):
        """JSON output is parsed and dot-path resolution extracts the correct field."""
        block = make_linear_block()
        state = make_state(
            current_task=make_task(),
            results={"block_a": BlockResult(output='{"key": "val"}')},
        )
        step = Step(block, declared_inputs={"extracted": "block_a.key"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["extracted"] == "val"

    def test_non_json_string_returned_as_is_with_dot_path(self):
        """Non-JSON output with dot-path ref returns the raw string (no crash)."""
        block = make_linear_block()
        state = make_state(
            current_task=make_task(),
            results={"block_a": BlockResult(output="plain text")},
        )
        step = Step(block, declared_inputs={"data": "block_a.subfield"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["data"] == "plain text"


# ==============================================================================
# 2. Parity with Step._resolve_from_ref — AC-2
# ==============================================================================


class TestParityWithResolveRef:
    """build_block_context input resolution uses _resolve_ref (canonical resolver).
    Step._resolve_from_ref was removed in RUN-892; these tests verify the
    canonical _resolve_ref in block_io produces correct results."""

    def test_resolve_ref_single_plain_output(self):
        """For a plain output ref, build_block_context resolves correctly."""
        from runsight_core.block_io import _resolve_ref

        block = make_linear_block()
        state = make_state(
            current_task=make_task(),
            results={"src": BlockResult(output="the output")},
        )
        step = Step(block, declared_inputs={"result": "src"})

        expected = _resolve_ref("src", state)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["result"] == expected

    def test_resolve_ref_json_dot_path(self):
        """JSON auto-parse dot-path resolution works correctly."""
        from runsight_core.block_io import _resolve_ref

        block = make_linear_block()
        state = make_state(
            current_task=make_task(),
            results={"src": BlockResult(output='{"nested": {"value": 42}}')},
        )
        step = Step(block, declared_inputs={"num": "src.nested.value"})

        expected = _resolve_ref("src.nested.value", state)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["num"] == expected

    def test_resolve_ref_missing_source_raises_value_error(self):
        """Both _resolve_ref and build_block_context raise ValueError for missing src."""
        from runsight_core.block_io import _resolve_ref

        block = make_linear_block()
        state = make_state(current_task=make_task(), results={})
        step = Step(block, declared_inputs={"x": "missing_block"})

        with pytest.raises(ValueError):
            _resolve_ref("missing_block", state)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            with pytest.raises(ValueError):
                build_block_context(block, state, step=step)


# ==============================================================================
# 3. LinearBlock context population — AC-1
# ==============================================================================


class TestLinearBlockContextPopulation:
    """build_block_context correctly populates all BlockContext fields for LinearBlock."""

    def test_block_id_matches_block(self):
        """ctx.block_id equals block.block_id."""
        block = make_linear_block(block_id="my_block")
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.block_id == "my_block"

    def test_instruction_comes_from_budgeted_task(self):
        """ctx.instruction is taken from the BudgetedContext.task.instruction."""
        block = make_linear_block()
        state = make_state(current_task=make_task(instruction="original instruction"))

        budgeted = _make_budgeted_context(instruction="budgeted instruction")
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.instruction == "budgeted instruction"

    def test_context_comes_from_budgeted_task(self):
        """ctx.context is taken from the BudgetedContext.task.context."""
        block = make_linear_block()
        state = make_state(current_task=make_task(instruction="instr", context="original context"))

        budgeted = _make_budgeted_context(instruction="instr", context="budgeted context")
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.context == "budgeted context"

    def test_soul_is_set_from_block_soul(self):
        """ctx.soul matches block.soul."""
        soul = make_soul(soul_id="soul_unique")
        block = make_linear_block(soul=soul)
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.soul is soul
        assert ctx.soul.id == "soul_unique"

    def test_model_name_from_soul_model_name(self):
        """ctx.model_name is resolved from soul.model_name when set."""
        soul = make_soul(model_name="claude-3-opus")
        block = make_linear_block(soul=soul)
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.model_name == "claude-3-opus"

    def test_model_name_falls_back_to_runner_model_name(self):
        """ctx.model_name falls back to runner.model_name when soul.model_name is None."""
        soul = Soul(id="s1", role="R", system_prompt="p", model_name=None)
        runner = make_runner(model_name="gpt-4-turbo")
        block = LinearBlock(block_id="block_a", soul=soul, runner=runner)
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.model_name == "gpt-4-turbo"

    def test_conversation_history_from_state_histories(self):
        """ctx.conversation_history is populated from state.conversation_histories."""
        soul = make_soul(soul_id="soul_1")
        block = make_linear_block(block_id="block_a", soul=soul)
        history_key = "block_a_soul_1"
        existing_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        state = make_state(
            current_task=make_task(),
            conversation_histories={history_key: existing_history},
        )

        budgeted = _make_budgeted_context(messages=list(existing_history))
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.conversation_history == existing_history

    def test_conversation_history_empty_when_no_history_for_block(self):
        """ctx.conversation_history is empty when state has no history for this block-soul."""
        soul = make_soul(soul_id="soul_1")
        block = make_linear_block(block_id="block_a", soul=soul)
        state = make_state(current_task=make_task(), conversation_histories={})

        budgeted = _make_budgeted_context(messages=[])
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.conversation_history == []


# ==============================================================================
# 4. Conversation history is a shallow copy — AC-3
# ==============================================================================


class TestConversationHistoryShallowCopy:
    """build_block_context shallow-copies conversation history (AC-3)."""

    def test_conversation_history_is_not_same_object_as_state_history(self):
        """ctx.conversation_history must be a new list, not the same object from state."""
        soul = make_soul(soul_id="soul_1")
        block = make_linear_block(block_id="block_a", soul=soul)
        history_key = "block_a_soul_1"
        original_history = [{"role": "user", "content": "Question"}]
        state = make_state(
            current_task=make_task(),
            conversation_histories={history_key: original_history},
        )

        budgeted = _make_budgeted_context(messages=list(original_history))
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.conversation_history is not original_history

    def test_mutation_of_ctx_history_does_not_affect_state_history(self):
        """Mutating ctx.conversation_history must not affect state.conversation_histories."""
        soul = make_soul(soul_id="soul_1")
        block = make_linear_block(block_id="block_a", soul=soul)
        history_key = "block_a_soul_1"
        original_history = [{"role": "user", "content": "Question"}]
        state = make_state(
            current_task=make_task(),
            conversation_histories={history_key: original_history},
        )
        original_len = len(original_history)

        budgeted = _make_budgeted_context(messages=list(original_history))
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        ctx.conversation_history.append({"role": "assistant", "content": "late addition"})
        # original_history in state must not grow
        assert len(state.conversation_histories[history_key]) == original_len


# ==============================================================================
# 5. fit_to_budget integration — AC-4
# ==============================================================================


class TestFitToBudgetIntegration:
    """build_block_context calls fit_to_budget with correct parameters."""

    def test_fit_to_budget_is_called(self):
        """fit_to_budget is invoked when building context for a LinearBlock."""
        block = make_linear_block()
        state = make_state(current_task=make_task(instruction="Test instr"))

        budgeted = _make_budgeted_context(instruction="Test instr")
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        assert mock_fit.called, "fit_to_budget must be called"

    def test_fit_to_budget_receives_correct_model(self):
        """fit_to_budget is called with the resolved model name."""
        soul = make_soul(soul_id="soul_1", model_name="gpt-4o-mini")
        block = make_linear_block(soul=soul)
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]  # positional first argument is ContextBudgetRequest
        assert request.model == "gpt-4o-mini"

    def test_fit_to_budget_receives_correct_instruction(self):
        """fit_to_budget is called with instruction from state.current_task."""
        block = make_linear_block()
        state = make_state(current_task=make_task(instruction="specific instruction"))

        budgeted = _make_budgeted_context(instruction="specific instruction")
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        assert request.instruction == "specific instruction"

    def test_fit_to_budget_receives_correct_context(self):
        """fit_to_budget is called with context from state.current_task."""
        block = make_linear_block()
        state = make_state(current_task=make_task(context="some background"))

        budgeted = _make_budgeted_context(context="some background")
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        assert request.context == "some background"

    def test_fit_to_budget_receives_conversation_history(self):
        """fit_to_budget is called with conversation history keyed by block_id_soul_id."""
        soul = make_soul(soul_id="soul_1")
        block = make_linear_block(block_id="block_a", soul=soul)
        history = [{"role": "user", "content": "prior turn"}]
        # Key is "{block_id}_{soul_id}"
        state = make_state(
            current_task=make_task(),
            conversation_histories={"block_a_soul_1": history},
        )

        budgeted = _make_budgeted_context(messages=history)
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        assert request.conversation_history == history

    def test_fit_to_budget_receives_system_prompt_from_soul(self):
        """fit_to_budget is called with system_prompt from block.soul.system_prompt."""
        soul = Soul(
            id="soul_1",
            role="R",
            system_prompt="You are a specialized assistant.",
            model_name=_MODEL,
        )
        block = make_linear_block(soul=soul)
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        assert request.system_prompt == "You are a specialized assistant."

    def test_budgeted_messages_populate_conversation_history(self):
        """ctx.conversation_history is populated from BudgetedContext.messages."""
        block = make_linear_block()
        state = make_state(current_task=make_task())
        pruned_messages = [{"role": "user", "content": "kept message"}]

        budgeted = _make_budgeted_context(messages=pruned_messages)
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.conversation_history == pruned_messages


# ==============================================================================
# 6. artifact_store passthrough — AC-5
# ==============================================================================


class TestArtifactStorePassthrough:
    """build_block_context passes state.artifact_store through to BlockContext."""

    def test_artifact_store_from_state_is_passed_through(self):
        """ctx.artifact_store is the same object as state.artifact_store."""
        store = make_artifact_store()
        block = make_linear_block()
        state = make_state(current_task=make_task(), artifact_store=store)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.artifact_store is store

    def test_artifact_store_none_when_state_has_none(self):
        """ctx.artifact_store is None when state.artifact_store is None."""
        block = make_linear_block()
        state = make_state(current_task=make_task(), artifact_store=None)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.artifact_store is None


# ==============================================================================
# 7. Edge cases
# ==============================================================================


class TestEdgeCases:
    """Edge-case behaviour for build_block_context."""

    def test_no_step_provided_inputs_is_empty(self):
        """When step=None, no input resolution occurs and ctx.inputs is empty."""
        block = make_linear_block()
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.inputs == {}

    def test_current_task_none_returns_minimal_context(self):
        """When state.current_task is None, build_block_context returns a minimal context.

        Since RUN-893 the function returns a minimal BlockContext with empty instruction
        instead of raising, to support generic test helpers and blocks that don't need
        a task. fit_to_budget is NOT called in this path.
        """
        block = make_linear_block()
        state = make_state(current_task=None)

        ctx = build_block_context(block, state)
        assert ctx.instruction == ""
        assert ctx.context is None
        assert ctx.state_snapshot is state

    def test_step_with_empty_declared_inputs_no_step_produces_same_result(self):
        """Passing step with no declared_inputs is equivalent to passing step=None for inputs."""
        block = make_linear_block()
        state = make_state(current_task=make_task())
        step = Step(block, declared_inputs={})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx_with_step = build_block_context(block, state, step=step)

        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx_without_step = build_block_context(block, state)

        assert ctx_with_step.inputs == ctx_without_step.inputs == {}

    def test_returns_block_context_instance(self):
        """build_block_context returns a BlockContext instance."""
        block = make_linear_block()
        state = make_state(current_task=make_task())

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert isinstance(ctx, BlockContext)

    def test_task_context_none_passes_empty_string_to_budget(self):
        """When task.context is None, fit_to_budget receives an empty string (not None)."""
        block = make_linear_block()
        state = make_state(current_task=make_task(context=None))

        budgeted = _make_budgeted_context(context=None)
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        # Should be "" not None — mirrors LinearBlock.execute behaviour
        assert request.context == "" or request.context is None
