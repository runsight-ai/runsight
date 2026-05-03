"""Smoke coverage for the artifact + carry_context + windowing integration path."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.artifacts import InMemoryArtifactStore
from runsight_core.block_io import BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState


async def _run_loop(loop: LoopBlock, state: WorkflowState, blocks: dict) -> WorkflowState:
    from runsight_core.block_io import BlockContext, BlockOutput, apply_block_output

    ctx = BlockContext(
        block_id=loop.block_id,
        instruction="loop",
        inputs={"blocks": blocks},
        state_snapshot=state,
    )
    output = await loop.execute(ctx)
    if isinstance(output, WorkflowState):
        return output
    if isinstance(output, BlockOutput):
        return apply_block_output(state, loop.block_id, output)
    return state


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.model_name = "gpt-4o-mini"
    runner.execute = AsyncMock()
    return runner


class StatefulArtifactBlockWithWindowing(BaseBlock):
    def __init__(self, block_id: str, soul: Soul, runner):
        super().__init__(block_id)
        self.context_access = "declared"
        self.stateful = True
        self.soul = soul
        self.runner = runner
        self.call_count = 0

    async def execute(self, ctx) -> BlockOutput:
        from runsight_core.memory.windowing import get_max_tokens, prune_messages

        state = ctx.state_snapshot
        self.call_count += 1

        history_key = f"{self.block_id}_{self.soul.id}"
        history = list(state.conversation_histories.get(history_key, []))

        result = await self.runner.execute("", None, self.soul, messages=history)
        updated_history = history + [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": result.output},
        ]
        updated_history = prune_messages(
            updated_history,
            get_max_tokens(self.soul.model_name or self.runner.model_name),
            self.soul.model_name or self.runner.model_name,
        )

        artifact_key = f"{self.block_id}_round_{self.call_count}"
        ref = await self.write_artifact(
            state,
            artifact_key,
            f"artifact content for round {self.call_count}",
            metadata={"round": self.call_count},
        )

        return BlockOutput(
            output=result.output,
            artifact_ref=ref,
            artifact_type="text",
            metadata={"round": self.call_count},
            cost_usd=result.cost_usd,
            total_tokens=result.total_tokens,
            conversation_replacements={history_key: updated_history},
        )


@pytest.mark.asyncio
async def test_loop_preserves_artifacts_while_carrying_pruned_stateful_outputs():
    runner = _make_runner()
    soul = Soul(
        id="writer",
        kind="soul",
        name="Writer",
        role="Writer",
        system_prompt="Write.",
        model_name="gpt-4o-mini",
    )
    store = InMemoryArtifactStore(run_id="cross-feature-smoke-run")
    call_count = 0

    async def _side_effect(instruction, context, soul, **kwargs):
        nonlocal call_count
        call_count += 1
        return ExecutionResult(
            task_id="cross-feature-smoke",
            soul_id=soul.id,
            output=f"Draft {call_count}",
            cost_usd=0.0,
            total_tokens=0,
        )

    runner.execute.side_effect = _side_effect
    inner = StatefulArtifactBlockWithWindowing("write", soul, runner)
    loop = LoopBlock(
        block_id="loop",
        inner_block_refs=["write"],
        max_rounds=3,
        carry_context=CarryContextConfig(mode="all", inject_as="all_rounds"),
    )
    blocks = {"write": inner, "loop": loop}

    def _prune_to_last_exchange(messages, max_tokens, model):
        return messages[-2:] if len(messages) > 2 else messages

    with patch(
        "runsight_core.memory.windowing.prune_messages", side_effect=_prune_to_last_exchange
    ):
        result_state = await _run_loop(loop, WorkflowState(artifact_store=store), blocks)

    history = result_state.conversation_histories["write_writer"]
    assert len(history) == 2
    assert history[-1]["content"] == "Draft 3"

    carried = result_state.shared_memory["all_rounds"]
    assert [entry["write"] for entry in carried] == ["Draft 1", "Draft 2", "Draft 3"]

    artifacts = await store.list_artifacts()
    assert len(artifacts) == 3
    assert (
        result_state.results["write"].artifact_ref == "mem://cross-feature-smoke-run/write_round_3"
    )
    assert await store.read("mem://cross-feature-smoke-run/write_round_1") == (
        "artifact content for round 1"
    )
