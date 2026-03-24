"""
RUN-263: Verify LoopBlock carry_context flows through task.context as P2 elastic data.

Integration test: 20+ loop rounds with carry_context mode="all" on a tight budget
must complete without ContextBudgetExceeded, with BudgetReport proving truncation.
"""

from __future__ import annotations

import importlib
import inspect
import re
from unittest.mock import AsyncMock, MagicMock, patch

from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock
from runsight_core.memory.budget import (
    BudgetedContext,
    BudgetReport,
    ContextBudgetRequest,
    fit_to_budget,
)
from runsight_core.primitives import Soul, Task
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
# LoopBlock carry_context -> task.context integration
# ===========================================================================

LOOP_MODULE = "runsight_core.blocks.loop"


class TestLoopBlockCarryContextFlowsThroughTaskContext:
    """When carry_context accumulates data, it should flow through task.context
    as P2 elastic data so the budget manager can truncate it."""

    def test_loop_carry_context_injects_into_task_context(self):
        """LoopBlock carry_context data must be written to task.context (not just
        shared_memory) so the budget system treats it as P2 elastic content."""
        source = _get_class_method_source(LOOP_MODULE, "LoopBlock", "execute")
        # The carry_context data must update current_task.context or
        # build a new task with context= containing the carry data
        assert re.search(
            r"(current_task\.context|task\.context|context\s*=.*carry)",
            source,
            re.DOTALL | re.IGNORECASE,
        ), (
            "LoopBlock.execute() does not flow carry_context data through task.context — "
            "accumulated carry_context must be set on the task's context field "
            "so the budget manager can truncate it as P2 elastic content"
        )


# ===========================================================================
# Integration test: 20+ loop rounds with carry_context mode="all"
# + stateful inner block on a small token budget.
# Must complete without ContextBudgetExceeded.
# ===========================================================================


def _make_soul() -> Soul:
    return Soul(
        id="test_soul",
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

    async def _execute(task, soul, **kwargs):
        round_counter[0] += 1
        n = round_counter[0]
        # ~800 chars of unique output per call
        output = f"=== Round {n} output ===\nround_{n}_data: " + "x" * 760
        return ExecutionResult(
            task_id=task.id,
            soul_id=soul.id,
            output=output,
            cost_usd=0.001,
            total_tokens=200,
        )

    runner.execute_task = AsyncMock(side_effect=_execute)
    runner.model_name = "gpt-4o-mini"
    runner._build_prompt = MagicMock(
        side_effect=lambda task: (
            task.instruction
            if not task.context
            else f"{task.instruction}\n\nContext:\n{task.context}"
        )
    )
    return runner


class TestLoopCarryContextBudgetIntegration:
    """Run a LoopBlock with 22 rounds, carry_context mode='all', and a stateful
    inner LinearBlock.  After migration, the inner block must call fit_to_budget
    with the carry_context data in task.context.

    With 22 rounds of ~200 tokens each (~4400 total) accumulated via carry_context
    mode='all', the context would overflow a tight budget without truncation.
    The inner block must use fit_to_budget to prune P2 carry_context entries.
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

        initial_task = Task(
            id="loop_task",
            instruction="Process iteratively and accumulate results.",
        )

        initial_state = WorkflowState(
            workflow_id="test_wf",
            current_task=initial_task,
        )

        final_state = await loop_block.execute(
            initial_state,
            blocks={"inner_writer": inner_block},
        )
        return final_state

    async def test_twenty_two_rounds_complete_with_carry_context_in_task(self):
        """LoopBlock with 22 rounds + carry_context mode='all' must inject
        carry_context data into state.current_task.context (not just shared_memory).
        The final state's current_task.context must contain carry_context data."""
        final_state = await self._run_loop()

        # Verify all 22 rounds completed
        loop_meta = final_state.shared_memory.get("__loop__loop_main", {})
        assert loop_meta.get("rounds_completed") == self.NUM_ROUNDS, (
            f"Expected {self.NUM_ROUNDS} rounds completed, got {loop_meta.get('rounds_completed')}"
        )

        # Verify carry_context data was injected into the task's context field
        # (not just shared_memory). After 22 rounds, the task.context should
        # contain accumulated round data.
        task_context = (
            final_state.current_task.context
            if final_state.current_task and final_state.current_task.context
            else ""
        )
        assert "round_" in task_context, (
            "After 22 rounds with carry_context mode='all', "
            "state.current_task.context should contain accumulated round data. "
            f"Got: {repr(task_context[:100]) if task_context else 'EMPTY'}. "
            "LoopBlock must inject carry_context into state.current_task.context "
            "so inner blocks can pass it through fit_to_budget as P2 elastic data."
        )

    async def test_carry_context_is_set_on_task_context(self):
        """The inner block must receive carry_context data via state.current_task.context
        (P2 elastic field), not just via shared_memory."""
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

        initial_task = Task(
            id="loop_task",
            instruction="Process iteratively.",
        )
        initial_state = WorkflowState(
            workflow_id="test_wf",
            current_task=initial_task,
        )

        await loop_block.execute(
            initial_state,
            blocks={"inner_writer": inner_block},
        )

        # After the loop, the runner should have been called with tasks
        # whose context field contains carry_context data (from round 2 onward).
        # Round 1 has no carry_context; round 2+ should have accumulated data.
        assert runner.execute_task.call_count == self.NUM_ROUNDS

        # Check that later rounds received carry_context via task.context
        # The task.context field must contain carry_context round data,
        # not be empty or None.
        later_calls = runner.execute_task.call_args_list[1:]  # skip round 1
        tasks_with_carry_data = [
            call.args[0]
            for call in later_calls
            if hasattr(call.args[0], "context")
            and call.args[0].context
            and "round_" in call.args[0].context
        ]

        assert len(tasks_with_carry_data) > 0, (
            "No tasks received carry_context round data via task.context field. "
            "LoopBlock must inject accumulated carry_context into "
            "state.current_task.context so inner blocks pass it through "
            "fit_to_budget as P2 elastic data. Currently carry_context only "
            "goes to shared_memory, but it must also flow through task.context."
        )

    async def test_fit_to_budget_receives_carry_context_as_p2(self):
        """fit_to_budget must receive carry_context data in the context field
        (P2 elastic) of the ContextBudgetRequest, not empty string."""
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

        initial_task = Task(
            id="loop_task",
            instruction="Process iteratively.",
        )
        initial_state = WorkflowState(
            workflow_id="test_wf",
            current_task=initial_task,
        )

        budget_requests: list[ContextBudgetRequest] = []

        # Patch fit_to_budget to track requests
        with patch("runsight_core.blocks.linear.fit_to_budget") as mock_fit:

            def _tracking_fit(req, counter):
                budget_requests.append(req)
                return BudgetedContext(
                    task=Task(id="budget_task", instruction=req.instruction, context=req.context),
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

        # From round 2 onward, fit_to_budget must receive carry_context data
        # in the context field (P2 elastic), not empty string
        later_requests = budget_requests[1:]  # skip round 1
        requests_with_carry_data = [
            req for req in later_requests if req.context and "round_" in req.context
        ]

        assert len(requests_with_carry_data) > 0, (
            f"No fit_to_budget call received carry_context data in the context field. "
            f"Collected {len(budget_requests)} requests; later rounds had contexts: "
            f"{[repr(r.context[:50]) if r.context else 'EMPTY' for r in later_requests[:3]]}. "
            f"LoopBlock must inject carry_context into state.current_task.context "
            f"so fit_to_budget can manage it as P2 elastic content."
        )

    async def test_budget_report_shows_pruning_in_later_rounds(self):
        """After enough rounds, the BudgetReport from fit_to_budget should show
        p2_tokens_before > p2_tokens_after, proving carry_context was pruned."""
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

        initial_task = Task(
            id="loop_task",
            instruction="Process iteratively.",
        )
        initial_state = WorkflowState(
            workflow_id="test_wf",
            current_task=initial_task,
        )

        budget_reports: list[BudgetReport] = []

        # Patch fit_to_budget to collect reports
        original_fit = fit_to_budget

        def _tracking_fit(req, counter):
            result = original_fit(req, counter)
            budget_reports.append(result.report)
            return result

        with patch(
            "runsight_core.blocks.linear.fit_to_budget",
            side_effect=_tracking_fit,
        ):
            await loop_block.execute(
                initial_state,
                blocks={"inner_writer": inner_block},
            )

        # There must be at least one report where pruning occurred
        pruned_reports = [r for r in budget_reports if r.p2_tokens_before > r.p2_tokens_after]
        assert len(pruned_reports) > 0, (
            f"No BudgetReport shows carry_context pruning (p2_tokens_before > p2_tokens_after). "
            f"Collected {len(budget_reports)} reports. "
            f"The inner block must pass carry_context as P2 context to fit_to_budget, "
            f"and with 22 rounds of ~200 tokens each, truncation must occur."
        )
