"""
RUN-263 (updated for RUN-875): LoopBlock carry_context integration tests.

After RUN-875, LinearBlock reads _resolved_inputs from shared_memory
instead of state.current_task. runner.execute() is used instead of execute_task().

The LoopBlock still injects carry_context into shared_memory and into
state.current_task.context (when current_task is present). The inner
LinearBlock uses fit_to_budget to manage its own context budget.

These tests verify:
1. LoopBlock with 22 rounds + carry_context completes successfully
2. The LoopBlock injects carry_context into shared_memory each round
3. fit_to_budget is called by LinearBlock in stateful mode
4. BudgetReport shows pruning occurs with large histories
"""

from __future__ import annotations

import importlib
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock
from runsight_core.memory.budget import (
    BudgetedContext,
    BudgetReport,
    ContextBudgetRequest,
    fit_to_budget,
)
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState


def _get_source(module_path: str) -> str:
    """Import a module by dotted path and return its source code."""
    mod = importlib.import_module(module_path)
    return inspect.getsource(mod)


def _get_class_method_source(module_path: str, class_name: str, method_name: str) -> str:
    """Return source of a specific class method."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    method = getattr(cls, method_name)
    return inspect.getsource(method)


# ===========================================================================
# LoopBlock carry_context -> shared_memory integration
# ===========================================================================

LOOP_MODULE = "runsight_core.blocks.loop"


class TestLoopBlockCarryContextFlowsThroughSharedMemory:
    """When carry_context accumulates data, it flows into shared_memory
    so downstream blocks (and _resolved_inputs) can access it."""


# ===========================================================================
# Integration test: 20+ loop rounds with carry_context mode="all"
# + stateful inner block on a small token budget.
# Must complete without ContextBudgetExceeded.
# ===========================================================================


def _make_soul() -> Soul:
    return Soul(
        id="test_soul",
        kind="soul",
        name="Test Soul",
        role="Test Agent",
        system_prompt="You are a test agent.",
        model_name="gpt-4o-mini",
    )


def _make_mock_runner(round_counter: list[int]):
    """Create a mock runner that produces ~200-token outputs per round.

    Each call generates a unique output with ~800 chars (~200 tokens at 4ch/tok).
    Accepts **kwargs to handle messages= passed by stateful blocks.
    """
    runner = MagicMock()

    async def _execute(instruction, context, soul, **kwargs):
        round_counter[0] += 1
        n = round_counter[0]
        # ~800 chars of unique output per call
        output = f"=== Round {n} output ===\nround_{n}_data: " + "x" * 760
        return ExecutionResult(
            task_id=f"round_{n}",
            soul_id=soul.id,
            output=output,
            cost_usd=0.001,
            total_tokens=200,
        )

    runner.execute = AsyncMock(side_effect=_execute)
    runner.model_name = "gpt-4o-mini"
    return runner


class TestLoopCarryContextBudgetIntegration:
    """Run a LoopBlock with 22 rounds, carry_context mode='all', and a stateful
    inner LinearBlock.  After RUN-875, the inner block uses runner.execute()
    and reads _resolved_inputs, not current_task.

    With 22 rounds of ~200 tokens each (~4400 total) accumulated in
    conversation history via stateful mode, the context would overflow a
    tight budget without truncation. The inner block must use fit_to_budget
    to prune P3 (conversation history) entries.
    """

    NUM_ROUNDS = 22

    async def _run_loop(self) -> WorkflowState:
        """Set up and execute the full LoopBlock pipeline."""
        soul = _make_soul()
        round_counter = [0]
        runner = _make_mock_runner(round_counter)

        inner_block = LinearBlock("inner_writer", soul, runner)
        inner_block.stateful = True

        loop_block = LoopBlock(
            block_id="loop_main",
            inner_block_refs=["inner_writer"],
            max_rounds=self.NUM_ROUNDS,
            carry_context=CarryContextConfig(
                enabled=True,
                mode="all",
                inject_as="previous_round_context",
            ),
        )

        initial_state = WorkflowState()

        final_state = await loop_block.execute(
            initial_state,
            blocks={"inner_writer": inner_block},
        )
        return final_state

    @pytest.mark.asyncio
    async def test_twenty_two_rounds_complete_successfully(self):
        """LoopBlock with 22 rounds + carry_context mode='all' must complete
        all rounds without error. The inner LinearBlock uses fit_to_budget
        to manage growing conversation history."""
        final_state = await self._run_loop()

        # Verify all 22 rounds completed
        loop_meta = final_state.shared_memory.get("__loop__loop_main", {})
        assert loop_meta.get("rounds_completed") == self.NUM_ROUNDS, (
            f"Expected {self.NUM_ROUNDS} rounds completed, got {loop_meta.get('rounds_completed')}"
        )

        # Verify carry_context data was injected into shared_memory
        carry_data = final_state.shared_memory.get("previous_round_context")
        assert carry_data is not None, (
            "LoopBlock must inject carry_context data into shared_memory['previous_round_context']"
        )

    @pytest.mark.asyncio
    async def test_carry_context_is_set_in_shared_memory(self):
        """The LoopBlock must inject carry_context data into shared_memory
        each round under the inject_as key."""
        soul = _make_soul()
        round_counter = [0]
        runner = _make_mock_runner(round_counter)

        inner_block = LinearBlock("inner_writer", soul, runner)
        inner_block.stateful = True

        loop_block = LoopBlock(
            block_id="loop_main",
            inner_block_refs=["inner_writer"],
            max_rounds=self.NUM_ROUNDS,
            carry_context=CarryContextConfig(
                enabled=True,
                mode="all",
                inject_as="previous_round_context",
            ),
        )

        initial_state = WorkflowState()

        final_state = await loop_block.execute(
            initial_state,
            blocks={"inner_writer": inner_block},
        )

        # After the loop, runner.execute should have been called NUM_ROUNDS times
        assert runner.execute.call_count == self.NUM_ROUNDS

        # Verify carry_context data is in shared_memory after the loop
        carry_data = final_state.shared_memory.get("previous_round_context")
        assert carry_data is not None, (
            "LoopBlock must store carry_context in shared_memory['previous_round_context']"
        )
        # mode='all' means it's a list of round outputs
        assert isinstance(carry_data, list), (
            "With mode='all', carry_context must be a list of round outputs"
        )

    @pytest.mark.asyncio
    async def test_fit_to_budget_is_called_in_stateful_mode(self):
        """fit_to_budget must be called by LinearBlock in stateful mode."""
        soul = _make_soul()
        round_counter = [0]
        runner = _make_mock_runner(round_counter)

        inner_block = LinearBlock("inner_writer", soul, runner)
        inner_block.stateful = True

        loop_block = LoopBlock(
            block_id="loop_main",
            inner_block_refs=["inner_writer"],
            max_rounds=self.NUM_ROUNDS,
            carry_context=CarryContextConfig(
                enabled=True,
                mode="all",
                inject_as="previous_round_context",
            ),
        )

        initial_state = WorkflowState()

        budget_requests: list[ContextBudgetRequest] = []

        # Patch fit_to_budget to track requests
        with patch("runsight_core.block_io.fit_to_budget") as mock_fit:

            def _tracking_fit(req, counter):
                budget_requests.append(req)
                return BudgetedContext(
                    instruction=req.instruction,
                    context=req.context,
                    messages=req.conversation_history,
                    report=BudgetReport(
                        model=req.model,
                        max_input_tokens=128000,
                        output_reserve=0,
                        effective_budget=100000,
                        p1_tokens=100,
                        p2_tokens_before=1000,
                        p2_tokens_after=800,
                        p3_tokens_before=0,
                        p3_tokens_after=0,
                        p3_pairs_dropped=0,
                        total_tokens=900,
                        headroom=99100,
                        warnings=[],
                    ),
                )

            mock_fit.side_effect = _tracking_fit

            await loop_block.execute(
                initial_state,
                blocks={"inner_writer": inner_block},
            )

        # fit_to_budget must have been called at least once per round (stateful path).
        # Note: LoopBlock also calls fit_to_budget internally for carry_context budgeting,
        # so the total count may be > NUM_ROUNDS.
        assert len(budget_requests) >= self.NUM_ROUNDS, (
            f"Expected fit_to_budget called at least {self.NUM_ROUNDS} times, "
            f"got {len(budget_requests)}"
        )

    @pytest.mark.asyncio
    async def test_budget_report_shows_pruning_in_later_rounds(self):
        """After enough rounds, the BudgetReport from fit_to_budget should show
        p3_pairs_dropped > 0 or p3_tokens_before > p3_tokens_after,
        proving conversation history was pruned.

        Uses a very small model context (500 tokens) to force pruning
        with the accumulating conversation history.
        """
        soul = _make_soul()
        round_counter = [0]
        runner = _make_mock_runner(round_counter)

        inner_block = LinearBlock("inner_writer", soul, runner)
        inner_block.stateful = True

        loop_block = LoopBlock(
            block_id="loop_main",
            inner_block_refs=["inner_writer"],
            max_rounds=self.NUM_ROUNDS,
            carry_context=CarryContextConfig(
                enabled=True,
                mode="all",
                inject_as="previous_round_context",
            ),
        )

        initial_state = WorkflowState()

        budget_reports: list[BudgetReport] = []

        # Patch fit_to_budget to collect reports
        original_fit = fit_to_budget

        def _tracking_fit(req, counter):
            result = original_fit(req, counter)
            budget_reports.append(result.report)
            return result

        # Patch get_model_budget to return a small budget (500 tokens) so that
        # conversation history accumulation forces pruning after a few rounds.
        with (
            patch(
                "runsight_core.block_io.fit_to_budget",
                side_effect=_tracking_fit,
            ),
            patch(
                "runsight_core.memory.budget.get_model_budget",
                return_value=500,
            ),
        ):
            await loop_block.execute(
                initial_state,
                blocks={"inner_writer": inner_block},
            )

        # Among all reports, find any where p3 (conversation history) was pruned.
        # LinearBlock calls are the ones that have conversation history (p3_tokens_before > 0).
        pruned_reports = [
            r
            for r in budget_reports
            if r.p3_pairs_dropped > 0 or r.p3_tokens_before > r.p3_tokens_after
        ]
        assert len(pruned_reports) > 0, (
            f"No BudgetReport shows history pruning (p3_pairs_dropped > 0 or "
            f"p3_tokens_before > p3_tokens_after). "
            f"Collected {len(budget_reports)} total reports. "
            f"p3_tokens_before values: {[r.p3_tokens_before for r in budget_reports[:5]]}. "
            f"With {self.NUM_ROUNDS} rounds of ~200 tokens each in conversation history "
            f"and max 500 tokens budget, truncation must occur."
        )
