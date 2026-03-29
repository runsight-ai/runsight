"""
RUN-199: Cross-feature integration tests — stateful + artifacts + carry_context + windowing.

All individual features are already implemented. These tests verify they work
TOGETHER in a single workflow:

1. Stateful LinearBlock inside LoopBlock writing artifacts each round
2. carry_context with BlockResult compat + artifact_ref accessibility
3. Stateful block with windowing and artifacts under a low token budget
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core import LinearBlock, LoopBlock
from runsight_core.artifacts import InMemoryArtifactStore
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import CarryContextConfig
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_runner(prompt_fn=None):
    """Create a mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    runner.model_name = "gpt-4o"
    runner._build_prompt = MagicMock(
        side_effect=prompt_fn
        or (
            lambda task: (
                task.instruction
                if not task.context
                else f"{task.instruction}\n\nContext:\n{task.context}"
            )
        )
    )
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


class StatefulArtifactBlock(BaseBlock):
    """Custom block that is stateful AND writes artifacts each round.

    Mimics a stateful LinearBlock but uses the BaseBlock.write_artifact() helper
    to write an artifact per invocation. This lets us test stateful conversation
    history accumulation and artifact writing in the same block execution.
    """

    def __init__(self, block_id: str, soul: Soul, runner):
        super().__init__(block_id)
        self.stateful = True
        self.soul = soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        # Track round number via shared_memory
        call_key = f"__{self.block_id}_call_count"
        call_count = state.shared_memory.get(call_key, 0) + 1

        # -- Stateful: read / append conversation history --
        history_key = f"{self.block_id}_{self.soul.id}"
        history = list(state.conversation_histories.get(history_key, []))

        result = await self.runner.execute_task(state.current_task, self.soul, messages=history)
        prompt = self.runner._build_prompt(state.current_task)
        updated_history = history + [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": result.output},
        ]

        # -- Artifact: write one artifact per round --
        artifact_key = f"{self.block_id}_round_{call_count}"
        ref = await self.write_artifact(
            state,
            artifact_key,
            f"artifact content for round {call_count}",
            metadata={"round": call_count},
        )

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=result.output,
                        artifact_ref=ref,
                        artifact_type="text",
                        metadata={"round": call_count},
                    ),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] Round {call_count}: {result.output[:100]}",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
                "conversation_histories": {
                    **state.conversation_histories,
                    history_key: updated_history,
                },
                "shared_memory": {
                    **state.shared_memory,
                    call_key: call_count,
                },
            }
        )


class StatefulArtifactBlockWithWindowing(BaseBlock):
    """Like StatefulArtifactBlock but calls prune_messages after updating history.

    This mirrors what the real LinearBlock does when stateful=True: after appending
    the new user/assistant pair it runs prune_messages to enforce the token budget.
    """

    def __init__(self, block_id: str, soul: Soul, runner):
        super().__init__(block_id)
        self.stateful = True
        self.soul = soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        from runsight_core.memory.windowing import get_max_tokens, prune_messages

        call_key = f"__{self.block_id}_call_count"
        call_count = state.shared_memory.get(call_key, 0) + 1

        history_key = f"{self.block_id}_{self.soul.id}"
        history = list(state.conversation_histories.get(history_key, []))

        result = await self.runner.execute_task(state.current_task, self.soul, messages=history)
        prompt = self.runner._build_prompt(state.current_task)
        updated_history = history + [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": result.output},
        ]

        # Apply windowing — prune_messages will be mocked in tests
        model = self.soul.model_name or self.runner.model_name
        updated_history = prune_messages(updated_history, get_max_tokens(model), model)

        # Write artifact
        artifact_key = f"{self.block_id}_round_{call_count}"
        ref = await self.write_artifact(
            state,
            artifact_key,
            f"artifact content for round {call_count}",
            metadata={"round": call_count},
        )

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=result.output,
                        artifact_ref=ref,
                        artifact_type="text",
                        metadata={"round": call_count},
                    ),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] Round {call_count}: {result.output[:100]}",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
                "conversation_histories": {
                    **state.conversation_histories,
                    history_key: updated_history,
                },
                "shared_memory": {
                    **state.shared_memory,
                    call_key: call_count,
                },
            }
        )


# ===========================================================================
# 1. Stateful LoopBlock with Artifacts
# ===========================================================================


class TestStatefulLoopWithArtifacts:
    """Stateful LinearBlock inside LoopBlock, writing artifacts each round.
    Verifies conversation history accumulates (6 msgs for 3 rounds) and
    artifacts are written to the InMemoryArtifactStore."""

    @pytest.mark.asyncio
    async def test_stateful_loop_with_artifacts(self):
        """3 rounds: 6 conversation messages + 3 artifacts in store."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")
        task = Task(id="t1", instruction="Analyze data")
        store = InMemoryArtifactStore(run_id="test-run-1")

        call_count = 0

        async def _side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Analysis round {call_count}")

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        inner = StatefulArtifactBlock("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState(current_task=task, artifact_store=store)
        result_state = await loop.execute(state, blocks=blocks)

        # -- Conversation history: 3 rounds * 2 messages = 6 --
        history_key = "analyze_analyst"
        assert history_key in result_state.conversation_histories
        history = result_state.conversation_histories[history_key]
        assert len(history) == 6, f"Expected 6 messages (3 rounds x 2), got {len(history)}"

        # Verify alternating user/assistant
        for i, msg in enumerate(history):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role

        # -- Artifacts: 3 artifacts in the store --
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 3, f"Expected 3 artifacts, got {len(artifacts)}"

        # Verify each artifact was written with correct keys
        artifact_keys = {a["key"] for a in artifacts}
        for round_num in range(1, 4):
            expected_key = f"analyze_round_{round_num}"
            assert expected_key in artifact_keys, f"Missing artifact key: {expected_key}"

        # Verify artifact content is readable
        for artifact in artifacts:
            content = await store.read(artifact["ref"])
            assert "artifact content for round" in content

        # -- artifact_store survived through all rounds --
        assert result_state.artifact_store is store

    @pytest.mark.asyncio
    async def test_artifact_refs_in_block_results(self):
        """BlockResult objects in state.results should carry artifact_ref."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")
        task = Task(id="t1", instruction="Analyze data")
        store = InMemoryArtifactStore(run_id="test-run-refs")

        call_count = 0

        async def _side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Round {call_count}")

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        inner = StatefulArtifactBlock("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState(current_task=task, artifact_store=store)
        result_state = await loop.execute(state, blocks=blocks)

        # The final BlockResult should have artifact_ref from the last round
        block_result = result_state.results["analyze"]
        assert isinstance(block_result, BlockResult)
        assert block_result.artifact_ref is not None
        assert block_result.artifact_ref.startswith("mem://test-run-refs/")
        assert block_result.output == "Round 3"


# ===========================================================================
# 2. carry_context with BlockResult and Artifacts
# ===========================================================================


class TestCarryContextWithBlockResultAndArtifacts:
    """LoopBlock with carry_context enabled, inner block returns BlockResult
    with artifact_ref. Verifies carry_context extracts .output (not BlockResult)
    and artifact_ref is accessible in results."""

    @pytest.mark.asyncio
    async def test_carry_context_extracts_output_from_blockresult(self):
        """carry_context must extract .output string, not pass BlockResult object."""
        runner = _make_mock_runner()
        soul = Soul(id="writer", role="Writer", system_prompt="You write.")
        task = Task(id="t1", instruction="Write report")
        store = InMemoryArtifactStore(run_id="test-carry")

        call_count = 0

        async def _side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "writer", f"draft_v{call_count}")

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        inner = StatefulArtifactBlock("write", soul, runner)
        config = CarryContextConfig(mode="last", inject_as="prev_draft")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["write"],
            max_rounds=3,
            carry_context=config,
        )
        blocks = {"write": inner, "loop": loop}

        state = WorkflowState(current_task=task, artifact_store=store)
        result_state = await loop.execute(state, blocks=blocks)

        # carry_context should inject string values, not BlockResult objects
        carried = result_state.shared_memory["prev_draft"]
        assert carried is not None

        write_value = carried["write"]
        assert isinstance(write_value, str), (
            f"Expected string in carried context, got {type(write_value).__name__}. "
            f"carry_context must extract .output from BlockResult."
        )
        # Should be the last round's output
        assert write_value == "draft_v3"

        # No BlockResult repr should leak into carried context
        assert "BlockResult" not in repr(carried)

    @pytest.mark.asyncio
    async def test_carry_context_all_mode_with_artifacts(self):
        """mode='all' accumulates string outputs across rounds, not BlockResult objects."""
        runner = _make_mock_runner()
        soul = Soul(id="writer", role="Writer", system_prompt="You write.")
        task = Task(id="t1", instruction="Write report")
        store = InMemoryArtifactStore(run_id="test-carry-all")

        call_count = 0

        async def _side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "writer", f"iteration_{call_count}")

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        inner = StatefulArtifactBlock("write", soul, runner)
        config = CarryContextConfig(mode="all", inject_as="all_drafts")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["write"],
            max_rounds=3,
            carry_context=config,
        )
        blocks = {"write": inner, "loop": loop}

        state = WorkflowState(current_task=task, artifact_store=store)
        result_state = await loop.execute(state, blocks=blocks)

        # mode="all" injects a list of dicts (one per round)
        history = result_state.shared_memory["all_drafts"]
        assert isinstance(history, list)
        assert len(history) == 3

        for round_idx, entry in enumerate(history):
            value = entry["write"]
            assert isinstance(value, str), (
                f"Round {round_idx + 1}: expected string, got {type(value).__name__}"
            )
            assert value == f"iteration_{round_idx + 1}"

        # Artifacts should still be in the store despite carry_context
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 3

    @pytest.mark.asyncio
    async def test_artifact_ref_accessible_in_results_with_carry_context(self):
        """artifact_ref remains accessible on BlockResult in state.results
        even when carry_context is active."""
        runner = _make_mock_runner()
        soul = Soul(id="writer", role="Writer", system_prompt="You write.")
        task = Task(id="t1", instruction="Write report")
        store = InMemoryArtifactStore(run_id="test-ref-access")

        call_count = 0

        async def _side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "writer", f"output_{call_count}")

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        inner = StatefulArtifactBlock("write", soul, runner)
        config = CarryContextConfig(mode="last", inject_as="ctx")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["write"],
            max_rounds=2,
            carry_context=config,
        )
        blocks = {"write": inner, "loop": loop}

        state = WorkflowState(current_task=task, artifact_store=store)
        result_state = await loop.execute(state, blocks=blocks)

        # BlockResult in state.results retains full artifact_ref
        block_result = result_state.results["write"]
        assert isinstance(block_result, BlockResult)
        assert block_result.artifact_ref is not None
        assert "mem://test-ref-access/" in block_result.artifact_ref
        assert block_result.artifact_type == "text"
        assert block_result.metadata["round"] == 2

        # But carried context only has the string output
        carried = result_state.shared_memory["ctx"]
        assert isinstance(carried["write"], str)
        assert carried["write"] == "output_2"
        assert "artifact_ref" not in str(carried)


# ===========================================================================
# 3. Stateful with Windowing and Artifacts
# ===========================================================================


class TestStatefulWithWindowingAndArtifacts:
    """Stateful block with a very low token budget forces FIFO windowing.
    Verifies history is pruned but artifacts are still written correctly."""

    @pytest.mark.asyncio
    async def test_windowing_prunes_history_but_artifacts_persist(self):
        """With aggressive pruning, history is capped but all artifacts are written."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="You analyze.")
        task = Task(id="t1", instruction="Analyze data")
        store = InMemoryArtifactStore(run_id="test-windowing")

        call_count = 0

        async def _side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Response {call_count}")

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        inner = StatefulArtifactBlockWithWindowing("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=5,
        )
        blocks = {"analyze": inner, "loop": loop}

        # Mock prune_messages to keep only the last 4 messages (2 rounds)
        def _aggressive_prune(msgs, max_tok, model):
            if len(msgs) > 4:
                return msgs[-4:]
            return msgs

        state = WorkflowState(current_task=task, artifact_store=store)

        with patch(
            "runsight_core.memory.windowing.prune_messages",
            side_effect=_aggressive_prune,
        ):
            # Also patch within implementations if windowing is called there
            # The StatefulArtifactBlockWithWindowing imports from windowing directly
            result_state = await loop.execute(state, blocks=blocks)

        # -- History was pruned: should be 4 messages, not 10 --
        history = result_state.conversation_histories["analyze_analyst"]
        assert len(history) <= 4, (
            f"Expected at most 4 messages after aggressive pruning, got {len(history)}"
        )

        # Latest round's output must be the last assistant message
        assert history[-1]["role"] == "assistant"
        assert history[-1]["content"] == "Response 5"

        # -- Artifacts: all 5 rounds wrote artifacts despite pruning --
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 5, f"Expected 5 artifacts (one per round), got {len(artifacts)}"

        # Verify artifact content for each round
        for round_num in range(1, 6):
            ref = f"mem://test-windowing/analyze_round_{round_num}"
            content = await store.read(ref)
            assert f"round {round_num}" in content

        # artifact_store survived
        assert result_state.artifact_store is store

    @pytest.mark.asyncio
    async def test_windowing_with_carry_context_and_artifacts(self):
        """Windowing + carry_context + artifacts all working together."""
        runner = _make_mock_runner()
        soul = Soul(id="writer", role="Writer", system_prompt="Write.")
        task = Task(id="t1", instruction="Write story")
        store = InMemoryArtifactStore(run_id="test-all-features")

        call_count = 0

        async def _side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "writer", f"Draft {call_count}")

        runner.execute_task = AsyncMock(side_effect=_side_effect)

        inner = StatefulArtifactBlockWithWindowing("write", soul, runner)
        config = CarryContextConfig(mode="all", inject_as="all_rounds")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["write"],
            max_rounds=4,
            carry_context=config,
        )
        blocks = {"write": inner, "loop": loop}

        # Aggressive prune: keep at most 2 messages
        def _prune_to_2(msgs, max_tok, model):
            if len(msgs) > 2:
                return msgs[-2:]
            return msgs

        state = WorkflowState(current_task=task, artifact_store=store)

        with patch(
            "runsight_core.memory.windowing.prune_messages",
            side_effect=_prune_to_2,
        ):
            result_state = await loop.execute(state, blocks=blocks)

        # -- History was pruned to 2 messages --
        history = result_state.conversation_histories["write_writer"]
        assert len(history) <= 2, (
            f"Expected at most 2 messages after aggressive pruning, got {len(history)}"
        )

        # -- carry_context accumulated all 4 rounds as strings --
        all_rounds = result_state.shared_memory["all_rounds"]
        assert isinstance(all_rounds, list)
        assert len(all_rounds) == 4

        for round_idx, entry in enumerate(all_rounds):
            value = entry["write"]
            assert isinstance(value, str), (
                f"Round {round_idx + 1}: carry_context has {type(value).__name__}, expected str"
            )
            assert value == f"Draft {round_idx + 1}"

        # -- All 4 artifacts written despite windowing --
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 4

        # -- artifact_store survived the full execution --
        assert result_state.artifact_store is store

    @pytest.mark.asyncio
    async def test_llm_receives_pruned_history_each_round(self):
        """The LLM should receive the pruned (shorter) history on subsequent rounds."""
        runner = _make_mock_runner()
        soul = Soul(id="analyst", role="Analyst", system_prompt="Analyze.")
        task = Task(id="t1", instruction="Analyze")
        store = InMemoryArtifactStore(run_id="test-llm-history")

        messages_received_per_call = []

        async def _capture_side_effect(t, s, **kwargs):
            msgs = kwargs.get("messages", [])
            messages_received_per_call.append(list(msgs))
            return _make_result("t1", "analyst", f"Output {len(messages_received_per_call)}")

        runner.execute_task = AsyncMock(side_effect=_capture_side_effect)

        inner = StatefulArtifactBlockWithWindowing("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=4,
        )
        blocks = {"analyze": inner, "loop": loop}

        # Prune to last 2 messages after round 2 onward
        def _prune_to_2(msgs, max_tok, model):
            if len(msgs) > 2:
                return msgs[-2:]
            return msgs

        state = WorkflowState(current_task=task, artifact_store=store)

        with patch(
            "runsight_core.memory.windowing.prune_messages",
            side_effect=_prune_to_2,
        ):
            await loop.execute(state, blocks=blocks)

        assert len(messages_received_per_call) == 4

        # Round 1: empty history
        assert len(messages_received_per_call[0]) == 0
        # Round 2: 2 messages from round 1 (not pruned yet, exactly 2)
        assert len(messages_received_per_call[1]) == 2
        # Round 3: pruned to 2 (had 4 -> pruned to 2)
        assert len(messages_received_per_call[2]) == 2
        # Round 4: pruned to 2 (had 4 -> pruned to 2)
        assert len(messages_received_per_call[3]) == 2

        # All 4 artifacts should still be in the store
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 4
