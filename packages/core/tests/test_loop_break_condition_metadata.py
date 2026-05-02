"""LoopBlock break-condition schema, execution, metadata, and workflow behavior."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import (
    BlockDef,
)

# -- Shared TypeAdapter for discriminated union --------------------------------

block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


async def _run_loop(loop, state: WorkflowState, blocks: dict) -> WorkflowState:
    """Helper: build BlockContext, run LoopBlock, apply output → WorkflowState."""
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


# -- Test helpers --------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        return BlockOutput(
            output=f"call_{len(self.calls)}",
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class KeywordBlock(BaseBlock):
    """Block that outputs a keyword on a specific call number.

    Before the target call, outputs "working...".
    On and after the target call, outputs "DONE: finished".
    """

    def __init__(self, block_id: str, keyword_on_call: int = 2):
        super().__init__(block_id)
        self.context_access = "declared"
        self.keyword_on_call = keyword_on_call
        self.calls: list[int] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        if call_num >= self.keyword_on_call:
            output = "DONE: finished"
        else:
            output = "working..."
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class JsonOutputBlock(BaseBlock):
    """Block that outputs structured JSON with a score field.

    Score increases by 20 each call: 20, 40, 60, 80, 100.
    """

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        import json

        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        output = json.dumps(
            {"score": call_num * 20, "status": "complete" if call_num >= 3 else "pending"}
        )
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class GatePassBlock(BaseBlock):
    """Simulates a gate block that writes PASS/FAIL to results based on round number.

    Returns "PASS" starting from the target round, "FAIL: not ready" before that.
    """

    def __init__(self, block_id: str, pass_on_round: int = 2):
        super().__init__(block_id)
        self.context_access = "declared"
        self.pass_on_round = pass_on_round
        self.calls: list[int] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        if call_num >= self.pass_on_round:
            output = "PASS"
        else:
            output = "FAIL: not ready"
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class BadFieldBlock(BaseBlock):
    """Block that outputs a dict without the field the break condition references."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        import json

        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        # Output has "name" but NOT "status" — condition referencing "status" should get None
        output = json.dumps({"name": "status source", "round": len(self.calls)})
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


# ==============================================================================
# 1. Schema tests -- LoopBlockDef accepts break_condition
# ==============================================================================


class TestLoopBlockBreakMetadata:
    """Break metadata in shared_memory records rounds_completed and broke_early."""

    @pytest.mark.asyncio
    async def test_metadata_on_early_break(self):
        """When breaking early, shared_memory should record broke_early=True and rounds_completed."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        inner = KeywordBlock("inner_block", keyword_on_call=2)
        blocks = {"inner_block": inner}

        break_cond = Condition(eval_key="inner_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Check metadata under __loop__loop_block key
        meta_key = "__loop__loop_block"
        assert meta_key in result_state.shared_memory, (
            f"Expected '{meta_key}' in shared_memory, got keys: {list(result_state.shared_memory.keys())}"
        )
        meta = result_state.shared_memory[meta_key]
        assert meta["rounds_completed"] == 2
        assert meta["broke_early"] is True
        assert "break_reason" in meta

    @pytest.mark.asyncio
    async def test_metadata_on_full_run(self):
        """When running all rounds, shared_memory should record broke_early=False."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        # Condition that never matches
        break_cond = Condition(eval_key="inner_block", operator="equals", value="NEVER_MATCHES")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        meta_key = "__loop__loop_block"
        assert meta_key in result_state.shared_memory
        meta = result_state.shared_memory[meta_key]
        assert meta["rounds_completed"] == 3
        assert meta["broke_early"] is False

    @pytest.mark.asyncio
    async def test_metadata_on_no_break_condition(self):
        """When no break_condition is set, metadata should still be present with broke_early=False."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
            break_condition=None,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        meta_key = "__loop__loop_block"
        assert meta_key in result_state.shared_memory
        meta = result_state.shared_memory[meta_key]
        assert meta["rounds_completed"] == 3
        assert meta["broke_early"] is False

    @pytest.mark.asyncio
    async def test_metadata_accessible_by_downstream_blocks(self):
        """Downstream blocks should be able to read loop break metadata from shared_memory."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        inner = KeywordBlock("inner_block", keyword_on_call=2)
        blocks = {"inner_block": inner}

        break_cond = Condition(eval_key="inner_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        # Downstream block that reads loop metadata
        class DownstreamBlock(BaseBlock):
            def __init__(self, block_id: str):
                super().__init__(block_id)
                self.context_access = "declared"
                self.declared_inputs = {"loop_meta": "shared_memory.__loop__loop_block"}

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                meta = ctx.inputs.get("loop_meta", {})
                return BlockOutput(
                    output=f"broke_early={meta.get('broke_early')}",
                )

        downstream = DownstreamBlock("downstream")
        blocks["downstream"] = downstream

        wf = Workflow(name="loop_metadata_workflow")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_block(downstream)
        wf.add_transition("loop_block", "downstream")
        wf.add_transition("downstream", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        result_state = await wf.run(state)

        from runsight_core.state import BlockResult

        downstream_result = result_state.results["downstream"]
        downstream_output = (
            downstream_result.output
            if isinstance(downstream_result, BlockResult)
            else downstream_result
        )
        assert downstream_output == "broke_early=True"


# ==============================================================================
# 4. Integration tests -- SoulBlock output keyword triggers break
# ==============================================================================
