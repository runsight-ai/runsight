"""
RUN-194: Integration tests for LoopBlock stateful round validation.

All underlying code is already implemented (RUN-191, RUN-192, RUN-212, RUN-195, RUN-181).
These tests validate that everything works together when a stateful block runs inside
a LoopBlock across multiple rounds:

1. Stateful LinearBlock inside LoopBlock, 3 rounds — history grows 2*N after N rounds
2. Stateful DispatchBlock (3 souls) inside LoopBlock, 2 rounds — per-soul independent histories
3. Windowing activates within loop — history exceeds token budget, gets pruned
4. Break condition works with BlockResult.output — evaluates string, not BlockResult object
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core import (
    DispatchBlock,
    LinearBlock,
    LoopBlock,
)
from runsight_core.blocks.dispatch import DispatchBranch
from runsight_core.conditions.engine import Condition
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_runner():
    """Create a mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o"
    return runner


def _make_result(task_id, soul_id, output, cost=0.0, tokens=0):
    """Helper to create an ExecutionResult."""
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


def _make_stateful_linear(block_id, soul, runner):
    """Helper to create a stateful LinearBlock."""
    block = LinearBlock(block_id, soul, runner)
    block.stateful = True
    return block


def _souls_to_branches(souls):
    """Convert a list of Soul objects to DispatchBranch objects."""
    return [
        DispatchBranch(exit_id=s.id, label=s.role, soul=s, task_instruction="Execute task")
        for s in souls
    ]


def _make_stateful_dispatch(block_id, souls, runner):
    """Helper to create a stateful DispatchBlock."""
    block = DispatchBlock(block_id, _souls_to_branches(souls), runner)
    block.stateful = True
    return block


# ===========================================================================
# 1. Stateful LinearBlock inside LoopBlock — 3 rounds
# ===========================================================================


class TestStatefulLinearBlockInsideLoop:
    """Stateful LinearBlock inside LoopBlock across multiple rounds.
    Conversation history should grow by 2 messages (user + assistant) per round."""

    @pytest.mark.asyncio
    async def test_history_grows_2n_after_n_rounds(self):
        """After 3 rounds, conversation_histories[key] must have 2*3 = 6 messages."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")

        # Runner returns different output each call to verify round ordering
        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Analysis round {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        history_key = "analyze_analyst"
        assert history_key in result_state.conversation_histories

        history = result_state.conversation_histories[history_key]
        assert len(history) == 6, f"Expected 6 messages (3 rounds x 2), got {len(history)}"

    @pytest.mark.asyncio
    async def test_each_round_alternates_user_assistant(self):
        """History must alternate user/assistant for every message."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Round {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        history = result_state.conversation_histories["analyze_analyst"]
        for i, msg in enumerate(history):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role, (
                f"Message {i}: expected role '{expected_role}', got '{msg['role']}'"
            )

    @pytest.mark.asyncio
    async def test_llm_receives_growing_history_each_round(self):
        """Each round's LLM call must include all prior rounds' messages."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")

        messages_received_per_call = []

        async def _capture_side_effect(instruction, context, soul, **kwargs):
            msgs = kwargs.get("messages", [])
            messages_received_per_call.append(list(msgs))
            return _make_result("t1", "analyst", f"Output {len(messages_received_per_call)}")

        runner.execute = AsyncMock(side_effect=_capture_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        await loop.execute(state, blocks=blocks)

        assert len(messages_received_per_call) == 3

        # Round 1: empty history (no prior rounds)
        assert len(messages_received_per_call[0]) == 0

        # Round 2: 2 messages from round 1 (user + assistant)
        assert len(messages_received_per_call[1]) == 2

        # Round 3: 4 messages from rounds 1 and 2
        assert len(messages_received_per_call[2]) == 4

    @pytest.mark.asyncio
    async def test_round_outputs_in_correct_order(self):
        """Assistant messages in history must be in chronological order."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Response_{call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        history = result_state.conversation_histories["analyze_analyst"]
        assistant_msgs = [m["content"] for m in history if m["role"] == "assistant"]
        assert assistant_msgs == ["Response_1", "Response_2", "Response_3"]

    @pytest.mark.asyncio
    async def test_works_via_workflow_run(self):
        """Integration through Workflow.run() — the real execution path."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Round {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )

        wf = Workflow(name="stateful_linear_loop_wf")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        state = WorkflowState()
        result_state = await wf.run(state)

        history = result_state.conversation_histories["analyze_analyst"]
        assert len(history) == 6


# ===========================================================================
# 2. Stateful DispatchBlock (3 souls) inside LoopBlock — 2 rounds
# ===========================================================================


class TestStatefulDispatchBlockInsideLoop:
    """Stateful DispatchBlock with 3 souls inside LoopBlock across 2 rounds.
    Each soul must have independent 2-round history."""

    @pytest.mark.asyncio
    async def test_per_soul_histories_after_2_rounds(self):
        """Each of 3 souls should have 4 messages (2 rounds x user + assistant)."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", role="Reviewer A", system_prompt="You review.")
        soul_b = Soul(id="soul_b", role="Reviewer B", system_prompt="You review.")
        soul_c = Soul(id="soul_c", role="Reviewer C", system_prompt="You review.")

        call_counts = {"soul_a": 0, "soul_b": 0, "soul_c": 0}

        async def _side_effect(instruction, context, soul, **kwargs):
            call_counts[soul.id] += 1
            return _make_result("t1", soul.id, f"{soul.id}_round_{call_counts[soul.id]}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("review", [soul_a, soul_b, soul_c], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["review"],
            max_rounds=2,
        )
        blocks = {"review": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        for soul_id in ["soul_a", "soul_b", "soul_c"]:
            history_key = f"review_{soul_id}"
            assert history_key in result_state.conversation_histories, (
                f"Missing history for {history_key}"
            )
            history = result_state.conversation_histories[history_key]
            assert len(history) == 4, (
                f"Expected 4 messages for {history_key} (2 rounds x 2), got {len(history)}"
            )

    @pytest.mark.asyncio
    async def test_per_soul_history_independence(self):
        """Each soul's history must contain only its own outputs, not other souls'."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", role="Reviewer A", system_prompt="Review A.")
        soul_b = Soul(id="soul_b", role="Reviewer B", system_prompt="Review B.")
        soul_c = Soul(id="soul_c", role="Reviewer C", system_prompt="Review C.")

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_result("t1", soul.id, f"UNIQUE_{soul.id}_OUTPUT")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("review", [soul_a, soul_b, soul_c], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["review"],
            max_rounds=2,
        )
        blocks = {"review": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Verify each soul's history contains only its own output
        for soul_id in ["soul_a", "soul_b", "soul_c"]:
            history = result_state.conversation_histories[f"review_{soul_id}"]
            all_content = " ".join(m["content"] for m in history)
            assert f"UNIQUE_{soul_id}_OUTPUT" in all_content

            # No other soul's output should appear
            for other_id in ["soul_a", "soul_b", "soul_c"]:
                if other_id != soul_id:
                    assert f"UNIQUE_{other_id}_OUTPUT" not in all_content, (
                        f"{soul_id}'s history contains {other_id}'s output"
                    )

    @pytest.mark.asyncio
    async def test_each_soul_receives_own_growing_history(self):
        """In round 2, each soul's LLM call must include only that soul's round 1 messages."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", role="A", system_prompt="A.")
        soul_b = Soul(id="soul_b", role="B", system_prompt="B.")
        soul_c = Soul(id="soul_c", role="C", system_prompt="C.")

        messages_per_soul_per_round = {"soul_a": [], "soul_b": [], "soul_c": []}

        async def _capture_side_effect(instruction, context, soul, **kwargs):
            msgs = kwargs.get("messages", [])
            messages_per_soul_per_round[soul.id].append(list(msgs))
            return _make_result("t1", soul.id, f"{soul.id}_output")

        runner.execute = AsyncMock(side_effect=_capture_side_effect)

        inner = _make_stateful_dispatch("fan", [soul_a, soul_b, soul_c], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["fan"],
            max_rounds=2,
        )
        blocks = {"fan": inner, "loop": loop}

        state = WorkflowState()
        await loop.execute(state, blocks=blocks)

        for soul_id in ["soul_a", "soul_b", "soul_c"]:
            calls = messages_per_soul_per_round[soul_id]
            assert len(calls) == 2, f"Expected 2 calls for {soul_id}, got {len(calls)}"
            # Round 1: empty history
            assert len(calls[0]) == 0, (
                f"Round 1 for {soul_id}: expected 0 messages, got {len(calls[0])}"
            )
            # Round 2: 2 messages from round 1
            assert len(calls[1]) == 2, (
                f"Round 2 for {soul_id}: expected 2 messages, got {len(calls[1])}"
            )

    @pytest.mark.asyncio
    async def test_dispatch_inside_loop_via_workflow_run(self):
        """Integration through Workflow.run()."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", role="A", system_prompt="A.")
        soul_b = Soul(id="soul_b", role="B", system_prompt="B.")

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_result("t1", soul.id, f"{soul.id}_out")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("fan", [soul_a, soul_b], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["fan"],
            max_rounds=2,
        )

        wf = Workflow(name="stateful_dispatch_loop_wf")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        state = WorkflowState()
        result_state = await wf.run(state)

        for soul_id in ["soul_a", "soul_b"]:
            history = result_state.conversation_histories[f"fan_{soul_id}"]
            assert len(history) == 4, f"Expected 4 messages for fan_{soul_id}, got {len(history)}"


# ===========================================================================
# 3. Windowing activates within loop
# ===========================================================================


class TestWindowingActivatesInsideLoop:
    """When history exceeds token budget inside a loop, budget fitting must prune."""

    @pytest.mark.asyncio
    async def test_windowing_prunes_during_loop_rounds(self):
        """With a tiny token budget simulated by mock, old messages get dropped."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Response {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=5,
        )
        blocks = {"analyze": inner, "loop": loop}

        from runsight_core.memory.budget import BudgetedContext, BudgetReport

        # Pre-call budget fitting keeps only the last 2 messages (1 pair)
        # so after appending the new pair: 2 + 2 = 4 messages stored
        def _aggressive_budget(request, counter):
            msgs = list(request.conversation_history)
            if len(msgs) > 2:
                msgs = msgs[-2:]
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
            return BudgetedContext(
                instruction=request.instruction,
                context=request.context,
                messages=msgs,
                report=report,
            )

        state = WorkflowState()

        with patch(
            "runsight_core.blocks.linear.fit_to_budget",
            side_effect=_aggressive_budget,
        ):
            result_state = await loop.execute(state, blocks=blocks)

        history = result_state.conversation_histories["analyze_analyst"]
        # Pre-call pruning keeps 2 msgs + appends 2 new = 4 stored
        assert len(history) == 4, (
            f"Expected 4 messages after aggressive pruning, got {len(history)}"
        )
        # The latest round's output must be the last message
        assert history[-1]["role"] == "assistant"
        assert history[-1]["content"] == "Response 5"

    @pytest.mark.asyncio
    async def test_windowing_prunes_dispatch_per_soul_inside_loop(self):
        """Budget fitting should prune per-soul histories independently inside a loop."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", role="A", system_prompt="A.")
        soul_b = Soul(id="soul_b", role="B", system_prompt="B.")

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_result("t1", soul.id, f"{soul.id}_out")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("fan", [soul_a, soul_b], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["fan"],
            max_rounds=4,
        )
        blocks = {"fan": inner, "loop": loop}

        from runsight_core.memory.budget import BudgetedContext, BudgetReport

        # Pre-call budget fitting returns empty messages (drops all history)
        # so after appending the new pair: 0 + 2 = 2 messages stored
        def _aggressive_budget(request, counter):
            msgs = []  # drop all history
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
            return BudgetedContext(
                instruction=request.instruction,
                context=request.context,
                messages=msgs,
                report=report,
            )

        state = WorkflowState()

        with patch(
            "runsight_core.blocks.dispatch.fit_to_budget",
            side_effect=_aggressive_budget,
        ):
            result_state = await loop.execute(state, blocks=blocks)

        for soul_id in ["soul_a", "soul_b"]:
            history = result_state.conversation_histories[f"fan_{soul_id}"]
            assert len(history) == 2, (
                f"Expected 2 messages for fan_{soul_id} after pruning, got {len(history)}"
            )
            assert history[-1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_pruned_history_still_passed_to_next_round(self):
        """After budget fitting, the pruned (shorter) history should be what the
        next round's LLM call receives — proving state passthrough works."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="Analyze.")

        messages_received = []

        async def _capture(instruction, context, soul, **kwargs):
            msgs = kwargs.get("messages", [])
            messages_received.append(list(msgs))
            return _make_result("t1", "analyst", f"Out {len(messages_received)}")

        runner.execute = AsyncMock(side_effect=_capture)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=4,
        )
        blocks = {"analyze": inner, "loop": loop}

        from runsight_core.memory.budget import BudgetedContext, BudgetReport

        # Pre-call budget fitting prunes to last 2 messages
        def _budget_prune_to_2(request, counter):
            msgs = list(request.conversation_history)
            if len(msgs) > 2:
                msgs = msgs[-2:]
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
            return BudgetedContext(
                instruction=request.instruction,
                context=request.context,
                messages=msgs,
                report=report,
            )

        state = WorkflowState()

        with patch(
            "runsight_core.blocks.linear.fit_to_budget",
            side_effect=_budget_prune_to_2,
        ):
            await loop.execute(state, blocks=blocks)

        assert len(messages_received) == 4

        # Round 1: no history (fit_to_budget gets [], returns [])
        assert len(messages_received[0]) == 0
        # Round 2: 2 messages from round 1 (not pruned yet — only 2 messages)
        assert len(messages_received[1]) == 2
        # Round 3: pruned to 2 by fit_to_budget (had 4, pruned to 2)
        assert len(messages_received[2]) == 2
        # Round 4: pruned to 2 by fit_to_budget (had 4, pruned to 2)
        assert len(messages_received[3]) == 2


# ===========================================================================
# 4. Break condition works with BlockResult.output
# ===========================================================================


class TestBreakConditionWithBlockResult:
    """Break condition must evaluate the string .output from BlockResult,
    not the BlockResult object itself."""

    @pytest.mark.asyncio
    async def test_break_condition_receives_string_output(self):
        """When inner block stores BlockResult in state.results, the break
        condition must extract .output and evaluate the string."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="Analyze.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            # On round 2, output contains "DONE"
            output = "DONE: analysis complete" if call_count >= 2 else "Still working..."
            return _make_result("t1", "analyst", output)

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        # Break when output contains "DONE"
        break_cond = Condition(eval_key="analyze", operator="contains", value="DONE")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Should have broken after round 2, not run all 5
        meta = result_state.shared_memory.get("__loop__loop")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["rounds_completed"] == 2
        assert meta["broke_early"] is True

    @pytest.mark.asyncio
    async def test_break_condition_does_not_see_blockresult_object(self):
        """Verify the break condition evaluates a string, not 'BlockResult(output=...)'.
        If it saw the object repr, a 'contains' check for 'DONE' against
        'BlockResult(output="DONE")' could still match — so we use 'equals' for precision."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="Analyze.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            # Exact match — "DONE" as the entire output
            return _make_result("t1", "analyst", "DONE" if call_count >= 2 else "working")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        # 'equals' operator: must match exactly "DONE", not "BlockResult(output='DONE')"
        break_cond = Condition(eval_key="analyze", operator="equals", value="DONE")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        meta = result_state.shared_memory["__loop__loop"]
        assert meta["rounds_completed"] == 2
        assert meta["broke_early"] is True

    @pytest.mark.asyncio
    async def test_break_condition_with_stateful_dispatch_output(self):
        """Break condition works when inner block is a stateful DispatchBlock
        that stores BlockResult with JSON output."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", role="A", system_prompt="A.")
        soul_b = Soul(id="soul_b", role="B", system_prompt="B.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", soul.id, f"{soul.id}_out")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("fan", [soul_a, soul_b], runner)
        # DispatchBlock output is JSON containing "soul_a_out" — use 'contains'
        break_cond = Condition(eval_key="fan", operator="contains", value="soul_a_out")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["fan"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks = {"fan": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Should break on round 1 since the output always contains "soul_a_out"
        meta = result_state.shared_memory["__loop__loop"]
        assert meta["rounds_completed"] == 1
        assert meta["broke_early"] is True

    @pytest.mark.asyncio
    async def test_stateful_history_preserved_after_early_break(self):
        """When break condition triggers early, the accumulated history
        up to that point must be preserved in the state."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="Analyze.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result(
                "t1", "analyst", "DONE" if call_count >= 3 else f"Progress {call_count}"
            )

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        break_cond = Condition(eval_key="analyze", operator="equals", value="DONE")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=10,
            break_condition=break_cond,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Broke on round 3 — history should have 3 rounds = 6 messages
        history = result_state.conversation_histories["analyze_analyst"]
        assert len(history) == 6, f"Expected 6 messages (3 rounds before break), got {len(history)}"
        # Last assistant message should be the break-trigger output
        assert history[-1]["content"] == "DONE"


# ===========================================================================
# 5. Combined scenario: stateful + windowing + break inside loop
# ===========================================================================


class TestCombinedStatefulWindowingBreak:
    """Full integration: stateful block with windowing and break condition inside a loop."""

    @pytest.mark.asyncio
    async def test_stateful_windowed_loop_with_early_break(self):
        """Stateful LinearBlock with windowing, breaking early at round 3 of 10."""
        runner = _make_mock_runner()
        soul = Soul(id="writer", role="Writer", system_prompt="Write.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return _make_result("t1", "writer", "FINAL: story complete")
            return _make_result("t1", "writer", f"Draft {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("write", soul, runner)
        break_cond = Condition(eval_key="write", operator="starts_with", value="FINAL")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["write"],
            max_rounds=10,
            break_condition=break_cond,
        )
        blocks = {"write": inner, "loop": loop}

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Verify break
        meta = result_state.shared_memory["__loop__loop"]
        assert meta["rounds_completed"] == 3
        assert meta["broke_early"] is True

        # Verify history (3 rounds = 6 messages)
        history = result_state.conversation_histories["write_writer"]
        assert len(history) == 6
        assert history[-1]["content"] == "FINAL: story complete"
