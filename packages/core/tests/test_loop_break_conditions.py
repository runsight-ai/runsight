"""
Failing tests for RUN-159: Add break conditions to LoopBlock.

Tests cover:
- Schema: LoopBlockDef accepts break_condition (ConditionDef | ConditionGroupDef)
- Unit: LoopBlock breaks early when condition met on round 2 of 5
- Unit: LoopBlock runs all max_rounds when condition never met
- Unit: LoopBlock with no break_condition runs all max_rounds (backward compat)
- Unit: ConditionGroupDef (AND/OR) works as break condition
- Unit: Break metadata in shared_memory records rounds_completed and broke_early
- Integration: Inner block output contains keyword -> break condition triggers
- Integration: GateBlock PASS -> break condition triggers exit
- Integration: Complex condition group works
- Edge: Break condition references missing field -> treat as False (continue)
- Edge: Break condition on round 1 -> loop exits after single execution
- Edge: Condition evaluation throws error -> propagate, don't swallow
"""

import pytest
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlockDef
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
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


# -- Test helpers --------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: f"call_{len(calls)}"},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class KeywordBlock(BaseBlock):
    """Block that outputs a keyword on a specific call number.

    Before the target call, outputs "working...".
    On and after the target call, outputs "DONE: finished".
    """

    def __init__(self, block_id: str, keyword_on_call: int = 2):
        super().__init__(block_id)
        self.keyword_on_call = keyword_on_call

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        call_num = len(calls)
        if call_num >= self.keyword_on_call:
            output = "DONE: finished"
        else:
            output = "working..."
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class JsonOutputBlock(BaseBlock):
    """Block that outputs structured JSON with a score field.

    Score increases by 20 each call: 20, 40, 60, 80, 100.
    """

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        call_num = len(calls)
        import json

        output = json.dumps(
            {"score": call_num * 20, "status": "complete" if call_num >= 3 else "pending"}
        )
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class GatePassBlock(BaseBlock):
    """Simulates a gate block that writes PASS/FAIL to results based on round number.

    Returns "PASS" starting from the target round, "FAIL: not ready" before that.
    """

    def __init__(self, block_id: str, pass_on_round: int = 2):
        super().__init__(block_id)
        self.pass_on_round = pass_on_round

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        call_num = len(calls)
        if call_num >= self.pass_on_round:
            output = "PASS"
        else:
            output = "FAIL: not ready"
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class BadFieldBlock(BaseBlock):
    """Block that outputs a dict without the field the break condition references."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        import json

        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        # Output has "name" but NOT "status" — condition referencing "status" should get None
        output = json.dumps({"name": "test", "round": len(calls)})
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
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
                "inner_block_refs": ["block_a"],
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
                "inner_block_refs": ["block_a"],
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
                "inner_block_refs": ["block_a"],
                "max_rounds": 5,
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_condition is None

    def test_break_condition_in_yaml_workflow_file(self):
        """break_condition should parse correctly inside a full RunsightWorkflowFile."""
        raw = {
            "version": "1.0",
            "id": "break_cond_test",
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
                "id": "break_cond_test",
                "kind": "workflow",
                "name": "break_cond_test",
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


class TestLoopBlockBreakEarly:
    """LoopBlock breaks early when break condition is met."""

    @pytest.mark.asyncio
    async def test_breaks_on_round_2_of_5(self):
        """LoopBlock with max_rounds=5 should break after round 2 when condition met."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # KeywordBlock outputs "DONE: finished" on call 2
        inner = KeywordBlock("inner_block", keyword_on_call=2)
        blocks = {"inner_block": inner}

        # Break when inner_block output contains "DONE"
        break_cond = Condition(eval_key="inner_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Should have executed only 2 rounds, not 5
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 2, f"Expected 2 calls (break on round 2), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_runs_all_max_rounds_when_condition_never_met(self):
        """LoopBlock should run all max_rounds when break condition never evaluates True."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # TrackingBlock never outputs "IMPOSSIBLE_VALUE"
        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        # Condition that will never match
        break_cond = Condition(eval_key="inner_block", operator="equals", value="IMPOSSIBLE_VALUE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=4,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Should run all 4 rounds
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 4, f"Expected 4 calls (all rounds), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_no_break_condition_runs_all_rounds(self):
        """LoopBlock with break_condition=None should run all max_rounds (backward compat)."""
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
        result_state = await loop.execute(state, blocks=blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 3, f"Expected 3 calls (all rounds, no break), got {len(calls)}"


class TestLoopBlockConditionGroupBreak:
    """ConditionGroupDef (AND/OR) works as break condition."""

    @pytest.mark.asyncio
    async def test_and_condition_group_breaks_when_all_met(self):
        """AND group: breaks only when all conditions in the group are True."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition, ConditionGroup

        # JsonOutputBlock: round 3 -> score=60, status="complete"
        inner = JsonOutputBlock("scorer")
        blocks = {"scorer": inner}

        # Break when score >= 60 AND status == "complete"
        break_cond = ConditionGroup(
            conditions=[
                Condition(eval_key="score", operator="gte", value=60),
                Condition(eval_key="status", operator="equals", value="complete"),
            ],
            combinator="and",
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["scorer"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Round 1: score=20, status=pending -> no break
        # Round 2: score=40, status=pending -> no break
        # Round 3: score=60, status=complete -> break!
        calls = result_state.shared_memory.get("scorer_calls", [])
        assert len(calls) == 3, f"Expected 3 rounds (AND group met on round 3), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_or_condition_group_breaks_when_any_met(self):
        """OR group: breaks when any condition in the group is True."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition, ConditionGroup

        # JsonOutputBlock: round 1 -> score=20
        inner = JsonOutputBlock("scorer")
        blocks = {"scorer": inner}

        # Break when score >= 80 OR status == "complete"
        # status becomes "complete" on round 3 (score=60)
        # score reaches 80 on round 4
        # But status == "complete" hits first on round 3
        break_cond = ConditionGroup(
            conditions=[
                Condition(eval_key="score", operator="gte", value=80),
                Condition(eval_key="status", operator="equals", value="complete"),
            ],
            combinator="or",
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["scorer"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Round 1: score=20, status=pending -> no break
        # Round 2: score=40, status=pending -> no break
        # Round 3: score=60, status=complete -> break (OR: status matches)
        calls = result_state.shared_memory.get("scorer_calls", [])
        assert len(calls) == 3, f"Expected 3 rounds (OR group met on round 3), got {len(calls)}"


# ==============================================================================
# 3. Break metadata in shared_memory
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
        result_state = await loop.execute(state, blocks=blocks)

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
        result_state = await loop.execute(state, blocks=blocks)

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
        result_state = await loop.execute(state, blocks=blocks)

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

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                meta = state.shared_memory.get("__loop__loop_block", {})
                return state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: f"broke_early={meta.get('broke_early')}",
                        },
                    }
                )

        downstream = DownstreamBlock("downstream")
        blocks["downstream"] = downstream

        wf = Workflow(name="meta_test")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_block(downstream)
        wf.add_transition("loop_block", "downstream")
        wf.add_transition("downstream", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        result_state = await wf.run(state)

        assert result_state.results["downstream"] == "broke_early=True"


# ==============================================================================
# 4. Integration tests -- SoulBlock output keyword triggers break
# ==============================================================================


class TestLoopBlockIntegrationKeywordBreak:
    """Inner block output contains keyword -> break condition triggers."""

    @pytest.mark.asyncio
    async def test_keyword_in_output_triggers_break(self):
        """When inner block output contains 'DONE', break condition with 'contains' triggers."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # KeywordBlock outputs "DONE: finished" on call 3
        inner = KeywordBlock("agent_block", keyword_on_call=3)
        blocks = {"agent_block": inner}

        break_cond = Condition(eval_key="agent_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["agent_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        calls = result_state.shared_memory.get("agent_block_calls", [])
        assert len(calls) == 3
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True


class TestLoopBlockIntegrationGateBreak:
    """GateBlock PASS -> break condition triggers exit."""

    @pytest.mark.asyncio
    async def test_gate_pass_triggers_break(self):
        """When gate block outputs 'PASS', break condition triggers loop exit."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        worker = TrackingBlock("worker")
        gate = GatePassBlock("gate", pass_on_round=3)
        blocks = {"worker": worker, "gate": gate}

        # Break when gate output starts with "PASS"
        break_cond = Condition(eval_key="gate", operator="starts_with", value="PASS")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Round 1: gate="FAIL: not ready" -> no break
        # Round 2: gate="FAIL: not ready" -> no break
        # Round 3: gate="PASS" -> break!
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        worker_calls = result_state.shared_memory.get("worker_calls", [])
        assert len(gate_calls) == 3, f"Expected gate called 3 times, got {len(gate_calls)}"
        assert len(worker_calls) == 3, f"Expected worker called 3 times, got {len(worker_calls)}"
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True


class TestLoopBlockIntegrationComplexConditionGroup:
    """Complex condition group works as break condition in integration context."""

    @pytest.mark.asyncio
    async def test_complex_and_group_with_multi_block_loop(self):
        """AND group with multiple inner blocks: condition evaluated against last block's output."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition, ConditionGroup

        worker = TrackingBlock("worker")
        scorer = JsonOutputBlock("scorer")
        blocks = {"worker": worker, "scorer": scorer}

        # Break when score >= 60 AND status == "complete" (happens on round 3)
        break_cond = ConditionGroup(
            conditions=[
                Condition(eval_key="score", operator="gte", value=60),
                Condition(eval_key="status", operator="equals", value="complete"),
            ],
            combinator="and",
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["worker", "scorer"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        scorer_calls = result_state.shared_memory.get("scorer_calls", [])
        assert len(scorer_calls) == 3
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True
        assert result_state.shared_memory["__loop__loop_block"]["rounds_completed"] == 3


# ==============================================================================
# 5. Edge cases
# ==============================================================================


class TestLoopBlockBreakEdgeCases:
    """Edge cases for break conditions."""

    @pytest.mark.asyncio
    async def test_missing_field_treated_as_false(self):
        """Break condition referencing a field not in output should treat as False (continue)."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # BadFieldBlock outputs {"name": "test", "round": N} -- no "status" field
        inner = BadFieldBlock("inner_block")
        blocks = {"inner_block": inner}

        # Condition references "status" which doesn't exist in output
        break_cond = Condition(eval_key="status", operator="equals", value="done")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Should run all 3 rounds because condition never matches
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 3, f"Expected 3 calls (missing field -> continue), got {len(calls)}"
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is False

    @pytest.mark.asyncio
    async def test_break_on_round_1(self):
        """Break condition met on round 1 should exit loop after single execution."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # KeywordBlock outputs "DONE: finished" on call 1
        inner = KeywordBlock("inner_block", keyword_on_call=1)
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
        result_state = await loop.execute(state, blocks=blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 1, f"Expected 1 call (break on round 1), got {len(calls)}"
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True
        assert result_state.shared_memory["__loop__loop_block"]["rounds_completed"] == 1

    @pytest.mark.asyncio
    async def test_condition_error_propagates(self):
        """If condition evaluation throws an error, it should propagate, not be swallowed."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        # Invalid regex pattern should cause ValueError during evaluation
        break_cond = Condition(eval_key="inner_block", operator="regex", value="[invalid")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        with pytest.raises(ValueError, match="[Rr]egex"):
            await loop.execute(state, blocks=blocks)

    @pytest.mark.asyncio
    async def test_break_condition_evaluates_against_last_inner_block_output(self):
        """Break condition should evaluate against the last inner block's output by default."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # Two inner blocks: first always outputs "working", second outputs "DONE" on call 2
        first = TrackingBlock("first_block")
        second = KeywordBlock("second_block", keyword_on_call=2)
        blocks = {"first_block": first, "second_block": second}

        # Condition checks second_block (last inner) output for "DONE"
        break_cond = Condition(eval_key="second_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["first_block", "second_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Round 1: second_block="working..." -> no break
        # Round 2: second_block="DONE: finished" -> break!
        second_calls = result_state.shared_memory.get("second_block_calls", [])
        assert len(second_calls) == 2, f"Expected 2 rounds, got {len(second_calls)}"


# ==============================================================================
# 6. Constructor accepts break_condition parameter
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
