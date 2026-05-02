"""LoopBlock break-condition schema, execution, metadata, and workflow behavior."""

from __future__ import annotations

from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlockDef
from runsight_core.state import WorkflowState
from runsight_core.yaml.schema import (
    BlockDef,
    ConditionDef,
    ConditionGroupDef,
    RunsightWorkflowFile,
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


class TestLoopBlockDefBreakConditionSchema:
    """LoopBlockDef should accept an optional break_condition field."""

    def test_break_condition_accepts_condition_def(self):
        """break_condition should accept a ConditionDef."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "max_rounds": 5,
                "break_condition": {
                    "eval_key": "status",
                    "operator": "equals",
                    "value": "done",
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_condition is not None
        assert isinstance(block.break_condition, ConditionDef)
        assert block.break_condition.eval_key == "status"
        assert block.break_condition.operator == "equals"
        assert block.break_condition.value == "done"

    def test_break_condition_accepts_condition_group_def(self):
        """break_condition should accept a ConditionGroupDef."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "max_rounds": 5,
                "break_condition": {
                    "combinator": "and",
                    "conditions": [
                        {"eval_key": "score", "operator": "gte", "value": 80},
                        {"eval_key": "status", "operator": "equals", "value": "complete"},
                    ],
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_condition is not None
        assert isinstance(block.break_condition, ConditionGroupDef)
        assert block.break_condition.combinator == "and"
        assert len(block.break_condition.conditions) == 2

    def test_break_condition_defaults_to_none(self):
        """break_condition should default to None when not specified."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "max_rounds": 5,
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_condition is None

    def test_break_condition_in_yaml_workflow_file(self):
        """break_condition should parse correctly inside a full RunsightWorkflowFile."""
        raw = {
            "version": "1.0",
            "id": "break_condition_workflow",
            "kind": "workflow",
            "souls": {
                "writer": {
                    "id": "writer",
                    "kind": "soul",
                    "name": "Writer",
                    "role": "Writer",
                    "system_prompt": "You write.",
                }
            },
            "blocks": {
                "write_block": {"type": "linear", "soul_ref": "writer"},
                "loop_block": {
                    "type": "loop",
                    "inner_block_refs": ["write_block"],
                    "max_rounds": 5,
                    "break_condition": {
                        "eval_key": "status",
                        "operator": "equals",
                        "value": "done",
                    },
                },
            },
            "workflow": {
                "id": "break_condition_workflow",
                "kind": "workflow",
                "name": "break condition workflow",
                "entry": "loop_block",
                "transitions": [{"from": "loop_block", "to": None}],
            },
        }
        file_def = RunsightWorkflowFile.model_validate(raw)
        loop_def = file_def.blocks["loop_block"]
        assert isinstance(loop_def, LoopBlockDef)
        assert loop_def.break_condition is not None


# ==============================================================================
# 2. Unit tests -- break condition behavior
# ==============================================================================


class TestLoopBlockConstructorBreakCondition:
    """LoopBlock constructor should accept break_condition parameter."""

    def test_constructor_accepts_condition(self):
        """LoopBlock should accept a break_condition Condition parameter."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        cond = Condition(eval_key="status", operator="equals", value="done")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=3,
            break_condition=cond,
        )
        assert loop.break_condition is cond

    def test_constructor_accepts_condition_group(self):
        """LoopBlock should accept a break_condition ConditionGroup parameter."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition, ConditionGroup

        group = ConditionGroup(
            conditions=[
                Condition(eval_key="score", operator="gte", value=80),
            ],
            combinator="and",
        )
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=3,
            break_condition=group,
        )
        assert loop.break_condition is group

    def test_constructor_defaults_break_condition_to_none(self):
        """LoopBlock without break_condition should default to None."""
        from runsight_core import LoopBlock

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=3,
        )
        assert loop.break_condition is None
