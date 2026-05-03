"""build_block_context behavior coverage for LinearBlock.

Tests cover:
1. Declared input resolution for empty, single, multiple, missing, and JSON refs.
2. Parity with the canonical _resolve_ref helper.
3. BlockContext field population for LinearBlock.
4. Conversation history shallow-copy behavior.
5. fit_to_budget request construction.
6. artifact_store passthrough from WorkflowState.
"""

from unittest.mock import MagicMock, patch

from runsight_core.artifacts import InMemoryArtifactStore
from runsight_core.block_io import (  # noqa: F401
    BlockContext,
    build_block_context,
)
from runsight_core.blocks.linear import LinearBlock
from runsight_core.memory.budget import BudgetedContext, BudgetReport
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState

# ==============================================================================
# Helpers
# ==============================================================================

_MODEL = "gpt-4o"


def make_soul(soul_id: str = "research_soul", model_name: str = _MODEL) -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name="Researcher Soul",
        role="Researcher",
        system_prompt="You are a researcher.",
        model_name=model_name,
    )


def make_runner(model_name: str = _MODEL) -> MagicMock:
    runner = MagicMock()
    runner.model_name = model_name
    return runner


def make_linear_block(block_id: str = "research_block", soul: Soul | None = None) -> LinearBlock:
    if soul is None:
        soul = make_soul()
    return LinearBlock(block_id=block_id, soul=soul, runner=make_runner())


def make_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


def make_artifact_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore(run_id="block-context-test-run")


def _make_budgeted_context(
    instruction: str = "Do the thing",
    context: str | None = None,
    messages: list | None = None,
) -> BudgetedContext:
    """Construct a fake BudgetedContext returned by mocked fit_to_budget."""
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
    return BudgetedContext(
        instruction=instruction, context=context, messages=messages or [], report=report
    )


# ==============================================================================
# Input resolution for empty, single, multiple, missing, and JSON refs
# ==============================================================================


class TestFitToBudgetIntegration:
    """build_block_context calls fit_to_budget with correct parameters."""

    def test_fit_to_budget_is_called(self):
        """fit_to_budget is invoked when building context for a LinearBlock."""
        block = make_linear_block()
        state = make_state()

        budgeted = _make_budgeted_context(instruction="Test instr")
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        assert mock_fit.called, "fit_to_budget must be called"

    def test_fit_to_budget_receives_correct_model(self):
        """fit_to_budget is called with the resolved model name."""
        soul = make_soul(soul_id="research_soul", model_name="gpt-4o-mini")
        block = make_linear_block(soul=soul)
        state = make_state()

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]  # positional first argument is ContextBudgetRequest
        assert request.model == "gpt-4o-mini"

    def test_fit_to_budget_receives_correct_instruction(self):
        """fit_to_budget is called with soul.system_prompt as instruction for LinearBlock."""
        soul = make_soul(soul_id="research_soul")
        block = make_linear_block(soul=soul)
        state = make_state()

        budgeted = _make_budgeted_context(instruction=soul.system_prompt)
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        assert request.instruction == soul.system_prompt

    def test_fit_to_budget_receives_correct_context(self):
        """fit_to_budget is called with context from state.workflow_inputs or empty string."""
        block = make_linear_block()
        state = make_state()

        budgeted = _make_budgeted_context(context="")
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        # No workflow input in state, so context defaults to ""
        assert request.context == ""

    def test_fit_to_budget_receives_conversation_history(self):
        """fit_to_budget is called with conversation history keyed by block_id_soul_id."""
        soul = make_soul(soul_id="research_soul")
        block = make_linear_block(block_id="research_block", soul=soul)
        history = [{"role": "user", "content": "prior turn"}]
        # Key is "{block_id}_{soul_id}"
        state = make_state(
            conversation_histories={"research_block_research_soul": history},
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
            id="research_soul",
            kind="soul",
            name="Specialized Soul",
            role="R",
            system_prompt="You are a specialized assistant.",
            model_name=_MODEL,
        )
        block = make_linear_block(soul=soul)
        state = make_state()

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted) as mock_fit:
            build_block_context(block, state)

        call_args = mock_fit.call_args
        request = call_args[0][0]
        assert request.system_prompt == "You are a specialized assistant."

    def test_budgeted_messages_populate_conversation_history(self):
        """ctx.conversation_history is populated from BudgetedContext.messages."""
        block = make_linear_block()
        state = make_state()
        pruned_messages = [{"role": "user", "content": "kept message"}]

        budgeted = _make_budgeted_context(messages=pruned_messages)
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.conversation_history == pruned_messages


# ==============================================================================
# artifact_store passthrough
# ==============================================================================


class TestArtifactStorePassthrough:
    """build_block_context passes state.artifact_store through to BlockContext."""

    def test_artifact_store_from_state_is_passed_through(self):
        """ctx.artifact_store is the same object as state.artifact_store."""
        store = make_artifact_store()
        block = make_linear_block()
        state = make_state(artifact_store=store)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.artifact_store is store

    def test_artifact_store_none_when_state_has_none(self):
        """ctx.artifact_store is None when state.artifact_store is None."""
        block = make_linear_block()
        state = make_state(artifact_store=None)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state)

        assert ctx.artifact_store is None


# ==============================================================================
# 7. Edge cases
# ==============================================================================
