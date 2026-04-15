"""
Failing tests for RUN-158: Rename RetryBlock -> LoopBlock with multi-block support.

Tests cover:
- LoopBlockDef schema: type="loop", inner_block_refs, max_rounds defaults/validation
- LoopBlock unit: 1 ref runs max_rounds times, 3 refs sequential per round,
  max_rounds=1 runs once, round counter in shared_memory, empty refs rejected,
  invalid ref raises at runtime, self-reference detection
- YAML parsing: type=loop parses in single pass, type=retry raises clear error,
  parser produces correct block graph
- Integration: writer + critic pattern for 3 rounds inside LoopBlock
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import (
    BlockDef,
    RunsightWorkflowFile,
)

# ── Shared TypeAdapter for discriminated union ─────────────────────────────

block_adapter = TypeAdapter(BlockDef)


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


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ── Test helpers ───────────────────────────────────────────────────────────


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        state = ctx.state_snapshot
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        return BlockOutput(
            output=f"call_{len(calls)}",
            shared_memory_updates={f"{self.block_id}_calls": calls},
        )


class FailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx):
        raise RuntimeError(f"Block {self.block_id} failed")


class WriterBlock(BaseBlock):
    """Simulates a writer agent: appends a draft to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        state = ctx.state_snapshot
        drafts = list(state.shared_memory.get("drafts", []))
        round_num = state.shared_memory.get("loop_block_round", 0)
        drafts.append(f"draft_round_{round_num}")
        return BlockOutput(
            output=f"draft_round_{round_num}",
            shared_memory_updates={"drafts": drafts},
        )


class CriticBlock(BaseBlock):
    """Simulates a critic agent: appends feedback to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        state = ctx.state_snapshot
        feedback = list(state.shared_memory.get("feedback", []))
        round_num = state.shared_memory.get("loop_block_round", 0)
        feedback.append(f"feedback_round_{round_num}")
        return BlockOutput(
            output=f"feedback_round_{round_num}",
            shared_memory_updates={"feedback": feedback},
        )


# ===========================================================================
# 1. LoopBlockDef schema — model validation
# ===========================================================================


class TestLoopBlockDefSchema:
    """LoopBlockDef Pydantic model validates correctly via discriminated union."""

    def test_loop_type_discriminator_resolves(self):
        """type='loop' should resolve to LoopBlockDef in the BlockDef union."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block({"type": "loop", "inner_block_refs": ["block_a", "block_b"]})
        assert isinstance(block, LoopBlockDef)

    def test_loop_default_max_rounds(self):
        """LoopBlockDef default max_rounds should be 5."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block({"type": "loop", "inner_block_refs": ["block_a"]})
        assert isinstance(block, LoopBlockDef)
        assert block.max_rounds == 5

    def test_loop_custom_max_rounds(self):
        """LoopBlockDef should accept a custom max_rounds value."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block({"type": "loop", "inner_block_refs": ["block_a"], "max_rounds": 10})
        assert isinstance(block, LoopBlockDef)
        assert block.max_rounds == 10

    def test_loop_inner_block_refs_stored(self):
        """inner_block_refs should be stored as list[str]."""

        block = _validate_block({"type": "loop", "inner_block_refs": ["a", "b", "c"]})
        assert block.inner_block_refs == ["a", "b", "c"]

    def test_loop_max_rounds_minimum_1(self):
        """max_rounds must be >= 1."""
        with pytest.raises(ValidationError, match="max_rounds"):
            _validate_block({"type": "loop", "inner_block_refs": ["a"], "max_rounds": 0})

    def test_loop_max_rounds_maximum_50(self):
        """max_rounds must be <= 50."""
        with pytest.raises(ValidationError, match="max_rounds"):
            _validate_block({"type": "loop", "inner_block_refs": ["a"], "max_rounds": 51})

    def test_loop_empty_inner_block_refs_rejected(self):
        """Empty inner_block_refs should raise a validation error."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "loop", "inner_block_refs": []})

    def test_loop_missing_inner_block_refs_rejected(self):
        """Missing inner_block_refs should raise a validation error."""
        with pytest.raises(ValidationError, match="inner_block_refs"):
            _validate_block({"type": "loop"})

    def test_retry_type_no_longer_in_union(self):
        """type='retry' should NOT be in the BlockDef discriminated union anymore."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "retry", "inner_block_ref": "some_block", "max_retries": 3})

    def test_loop_supports_retry_config(self):
        """LoopBlockDef should support the inherited retry_config field."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["a"],
                "retry_config": {"max_attempts": 2, "backoff": "fixed"},
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_config is not None
        assert block.retry_config.max_attempts == 2


# ===========================================================================
# 2. LoopBlock unit tests — execution behavior
# ===========================================================================


class TestLoopBlockSingleRef:
    """LoopBlock with 1 inner block ref runs max_rounds times."""

    @pytest.mark.asyncio
    async def test_single_ref_runs_max_rounds_times(self):
        """A LoopBlock with 1 inner ref and max_rounds=3 should execute the inner block 3 times."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner, "loop_block": None}  # placeholder for loop

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Inner block should have been called 3 times
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_single_ref_default_max_rounds(self):
        """Default max_rounds=5 should execute the inner block 5 times."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 5


class TestLoopBlockMultiRef:
    """LoopBlock with multiple inner block refs runs all sequentially per round."""

    @pytest.mark.asyncio
    async def test_three_refs_sequential_per_round(self):
        """3 inner refs with max_rounds=2 should produce 6 total executions (3 per round)."""
        from runsight_core import LoopBlock

        block_a = TrackingBlock("block_a")
        block_b = TrackingBlock("block_b")
        block_c = TrackingBlock("block_c")
        blocks = {
            "block_a": block_a,
            "block_b": block_b,
            "block_c": block_c,
        }

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["block_a", "block_b", "block_c"],
            max_rounds=2,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Each block should have been called exactly 2 times (once per round)
        assert len(result_state.shared_memory.get("block_a_calls", [])) == 2
        assert len(result_state.shared_memory.get("block_b_calls", [])) == 2
        assert len(result_state.shared_memory.get("block_c_calls", [])) == 2


class TestLoopBlockMaxRoundsOne:
    """LoopBlock with max_rounds=1 runs inner blocks exactly once (no loop)."""

    @pytest.mark.asyncio
    async def test_max_rounds_one_runs_once(self):
        """max_rounds=1 means inner blocks execute exactly once."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=1,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 1


class TestLoopBlockRoundCounter:
    """Round counter in shared_memory increments correctly."""

    @pytest.mark.asyncio
    async def test_round_counter_increments(self):
        """shared_memory should contain the current round number, incrementing each round."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # The round counter key should reflect completed rounds
        # Exact key name: "loop_block_round" or similar — implementation decides
        # but it must be present and equal to the final round number
        round_key = "loop_block_round"
        assert round_key in result_state.shared_memory
        assert result_state.shared_memory[round_key] == 3

    @pytest.mark.asyncio
    async def test_round_counter_available_to_inner_blocks(self):
        """Inner blocks should be able to read the current round from shared_memory."""
        from runsight_core import LoopBlock

        class RoundReaderBlock(BaseBlock):
            """Block that reads the current loop round from shared_memory."""

            def __init__(self, block_id: str):
                super().__init__(block_id)

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                state = ctx.state_snapshot
                # The LoopBlock should set 'loop_round' or similar before executing inner blocks
                rounds_seen = list(state.shared_memory.get("rounds_seen", []))
                current_round = state.shared_memory.get("loop_block_round", -1)
                rounds_seen.append(current_round)
                return BlockOutput(
                    output="ok",
                    shared_memory_updates={"rounds_seen": rounds_seen},
                )

        reader = RoundReaderBlock("reader_block")
        blocks = {"reader_block": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        rounds_seen = result_state.shared_memory.get("rounds_seen", [])
        assert len(rounds_seen) == 3
        # Rounds should be 1, 2, 3 (1-indexed)
        assert rounds_seen == [1, 2, 3]


class TestLoopBlockErrorHandling:
    """Error cases: empty refs, invalid ref, self-reference, inner failure."""

    def test_constructor_rejects_empty_refs(self):
        """LoopBlock constructor should reject empty inner_block_refs."""
        from runsight_core import LoopBlock

        with pytest.raises((ValueError, ValidationError)):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=[],
                max_rounds=3,
            )

    @pytest.mark.asyncio
    async def test_invalid_ref_raises_at_runtime(self):
        """Referencing a block ID that doesn't exist in the blocks dict should raise at runtime."""
        from runsight_core import LoopBlock

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["nonexistent_block"],
            max_rounds=3,
        )

        state = WorkflowState()
        # The blocks dict does NOT contain "nonexistent_block"
        with pytest.raises((ValueError, KeyError), match="nonexistent_block"):
            await _run_loop(loop, state, {"loop_block": loop})

    def test_self_reference_rejected(self):
        """LoopBlock referencing itself in inner_block_refs should be detected and rejected."""
        from runsight_core import LoopBlock

        with pytest.raises(ValueError, match="self-reference|itself|circular"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["loop_block"],
                max_rounds=3,
            )

    def test_self_reference_among_other_refs_rejected(self):
        """LoopBlock including itself among other refs should also be rejected."""
        from runsight_core import LoopBlock

        with pytest.raises(ValueError, match="self-reference|itself|circular"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["block_a", "loop_block", "block_b"],
                max_rounds=3,
            )

    @pytest.mark.asyncio
    async def test_inner_block_failure_propagates(self):
        """If an inner block fails mid-round, the error should propagate immediately."""
        from runsight_core import LoopBlock

        good_block = TrackingBlock("good_block")
        bad_block = FailingBlock("bad_block")
        blocks = {"good_block": good_block, "bad_block": bad_block}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["good_block", "bad_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        with pytest.raises(RuntimeError, match="Block bad_block failed"):
            await _run_loop(loop, state, blocks)

    @pytest.mark.asyncio
    async def test_shared_block_across_multiple_loops(self):
        """A single block referenced by multiple LoopBlocks should be allowed."""
        from runsight_core import LoopBlock

        shared_inner = TrackingBlock("shared_block")
        blocks = {"shared_block": shared_inner}

        loop_a = LoopBlock(
            block_id="loop_a",
            inner_block_refs=["shared_block"],
            max_rounds=2,
        )
        loop_b = LoopBlock(
            block_id="loop_b",
            inner_block_refs=["shared_block"],
            max_rounds=3,
        )
        blocks["loop_a"] = loop_a
        blocks["loop_b"] = loop_b

        state = WorkflowState()
        state = await _run_loop(loop_a, state, blocks)
        state = await _run_loop(loop_b, state, blocks)

        # shared_block should have been called 2 + 3 = 5 times total
        calls = state.shared_memory.get("shared_block_calls", [])
        assert len(calls) == 5


# ===========================================================================
# 3. YAML parsing tests — single-pass parser
# ===========================================================================


class TestLoopBlockYamlParsing:
    """YAML parsing: type=loop parses correctly, type=retry raises error."""

    def test_loop_type_parses_to_loop_block_def(self):
        """type: loop with inner_block_refs should parse to LoopBlockDef in a workflow file."""
        from runsight_core.blocks.loop import LoopBlockDef

        raw = {
            "version": "1.0",
            "id": "loop_test",
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
                    "max_rounds": 3,
                },
            },
            "workflow": {
                "id": "loop_test",
                "kind": "workflow",
                "name": "loop_test",
                "entry": "loop_block",
                "transitions": [{"from": "loop_block", "to": None}],
            },
        }
        file_def = RunsightWorkflowFile.model_validate(raw)
        loop_def = file_def.blocks["loop_block"]
        assert isinstance(loop_def, LoopBlockDef)
        assert loop_def.inner_block_refs == ["write_block"]
        assert loop_def.max_rounds == 3

    def test_retry_type_raises_clear_error(self):
        """type: retry in YAML should raise a clear error (clean break, no backward compat)."""
        raw = {
            "version": "1.0",
            "id": "retry_test",
            "kind": "workflow",
            "blocks": {
                "retry_block": {
                    "type": "retry",
                    "inner_block_ref": "some_block",
                    "max_retries": 3,
                },
            },
            "workflow": {
                "id": "retry_test",
                "kind": "workflow",
                "name": "retry_test",
                "entry": "retry_block",
                "transitions": [],
            },
        }
        # Should fail at schema validation since "retry" is no longer in the discriminated union
        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(raw)

    def test_retry_type_in_parser_raises_value_error(self):
        """parse_workflow_yaml with type: retry should raise ValueError with upgrade message."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """
version: "1.0"
id: inline_test_workflow
kind: workflow
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "You write."
blocks:
  write_block:
    type: linear
    soul_ref: writer
  retry_block:
    type: retry
    inner_block_ref: write_block
    max_retries: 3
workflow:
  id: retry_test
  kind: workflow
  name: retry_test
  entry: retry_block
  transitions:
    - from: retry_block
      to:
"""
        with pytest.raises((ValidationError, ValueError), match="retry"):
            parse_workflow_yaml(yaml_str)

    def test_parser_produces_loop_block_instance(self):
        """parse_workflow_yaml with type: loop should produce a LoopBlock instance."""
        from runsight_core import LoopBlock
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """
version: "1.0"
id: inline_test_workflow
kind: workflow
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "You write."
blocks:
  write_block:
    type: linear
    soul_ref: writer
  loop_block:
    type: loop
    inner_block_refs:
      - write_block
    max_rounds: 3
workflow:
  id: loop_parse_test
  kind: workflow
  name: loop_parse_test
  entry: loop_block
  transitions:
    - from: loop_block
      to:
"""
        wf = parse_workflow_yaml(yaml_str)
        loop = wf.blocks.get("loop_block")
        assert loop is not None
        assert isinstance(loop, LoopBlock)

    def test_parser_single_pass_no_retry_in_registry(self):
        """BLOCK_TYPE_REGISTRY should have 'loop' and NOT have 'retry'."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert "loop" in BLOCK_TYPE_REGISTRY, "'loop' should be in BLOCK_TYPE_REGISTRY"
        assert "retry" not in BLOCK_TYPE_REGISTRY, "'retry' should NOT be in BLOCK_TYPE_REGISTRY"

    def test_parser_loop_block_stores_refs_as_strings(self):
        """LoopBlock built by parser should store inner_block_refs as strings, not resolved blocks."""
        from runsight_core import LoopBlock
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """
version: "1.0"
id: inline_test_workflow
kind: workflow
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "You write."
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Reviewer
    system_prompt: "You review."
blocks:
  write_block:
    type: linear
    soul_ref: writer
  review_block:
    type: linear
    soul_ref: reviewer
  loop_block:
    type: loop
    inner_block_refs:
      - write_block
      - review_block
    max_rounds: 2
workflow:
  id: loop_refs_test
  kind: workflow
  name: loop_refs_test
  entry: loop_block
  transitions:
    - from: loop_block
      to:
"""
        wf = parse_workflow_yaml(yaml_str)
        loop = wf.blocks.get("loop_block")
        assert isinstance(loop, LoopBlock)
        assert hasattr(loop, "inner_block_refs")
        assert loop.inner_block_refs == ["write_block", "review_block"]
        # Verify they are strings, not BaseBlock instances
        for ref in loop.inner_block_refs:
            assert isinstance(ref, str)


# ===========================================================================
# 4. Workflow runner integration — LoopBlock in workflow context
# ===========================================================================


class TestLoopBlockWorkflowIntegration:
    """LoopBlock works correctly when executed through Workflow.run()."""

    @pytest.mark.asyncio
    async def test_workflow_passes_blocks_to_loop_execute(self):
        """Workflow.run() should pass blocks=self._blocks to LoopBlock.execute() via kwargs."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=2,
        )

        wf = Workflow(name="loop_wf_test")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        result_state = await wf.run(state)

        # Inner block should have been called 2 times
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_isinstance_check_uses_loop_block(self):
        """Workflow runner should use isinstance(block, LoopBlock), not RetryBlock."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=1,
        )

        wf = Workflow(name="isinstance_test")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        # Should not raise — workflow should recognize LoopBlock and pass kwargs
        result_state = await wf.run(state)
        assert "inner_block" in result_state.results


# ===========================================================================
# 5. Integration tests — writer + critic pattern
# ===========================================================================


class TestLoopBlockWriterCriticIntegration:
    """Integration: Two blocks inside LoopBlock in writer + critic pattern for 3 rounds."""

    @pytest.mark.asyncio
    async def test_writer_critic_three_rounds(self):
        """Writer + critic pattern: 3 rounds produces 3 drafts and 3 feedbacks."""
        from runsight_core import LoopBlock

        writer = WriterBlock("writer")
        critic = CriticBlock("critic")
        blocks = {"writer": writer, "critic": critic}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        drafts = result_state.shared_memory.get("drafts", [])
        feedback = result_state.shared_memory.get("feedback", [])

        assert len(drafts) == 3, f"Expected 3 drafts, got {len(drafts)}: {drafts}"
        assert len(feedback) == 3, f"Expected 3 feedback, got {len(feedback)}: {feedback}"

    @pytest.mark.asyncio
    async def test_writer_critic_workflow_integration(self):
        """Full workflow integration: LoopBlock as entry, writer+critic pattern, 3 rounds."""
        from runsight_core import LoopBlock

        writer = WriterBlock("writer")
        critic = CriticBlock("critic")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
        )

        wf = Workflow(name="writer_critic_wf")
        wf.add_block(writer)
        wf.add_block(critic)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        result_state = await wf.run(state)

        drafts = result_state.shared_memory.get("drafts", [])
        feedback = result_state.shared_memory.get("feedback", [])

        assert len(drafts) == 3
        assert len(feedback) == 3

    @pytest.mark.asyncio
    async def test_loop_result_stored_under_loop_block_id(self):
        """LoopBlock should store its own result in state.results[loop_block_id]."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=2,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        assert "loop_block" in result_state.results


# ===========================================================================
# 6. __init__.py exports
# ===========================================================================


class TestLoopBlockExports:
    """LoopBlock should be exported from runsight_core package."""

    def test_loop_block_importable_from_implementations(self):
        """LoopBlock should be importable from runsight_core.blocks.implementations."""
        from runsight_core import LoopBlock

        assert LoopBlock is not None

    def test_loop_block_importable_from_package(self):
        """LoopBlock should be in runsight_core.__all__ and importable from the package."""
        import runsight_core

        assert hasattr(runsight_core, "LoopBlock")

    def test_retry_block_removed_from_exports(self):
        """RetryBlock should no longer be exported from runsight_core."""
        import runsight_core

        assert "RetryBlock" not in runsight_core.__all__

    def test_loop_block_def_importable_from_schema(self):
        """LoopBlockDef should be importable from runsight_core.yaml.schema."""
        from runsight_core.blocks.loop import LoopBlockDef

        assert LoopBlockDef is not None

    def test_retry_block_def_removed_from_schema(self):
        """RetryBlockDef should no longer exist in runsight_core.yaml.schema."""
        import runsight_core.yaml.schema as schema

        assert not hasattr(schema, "RetryBlockDef")
