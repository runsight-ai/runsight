"""LoopBlock schema, parsing, execution, and workflow integration behavior."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
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
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        return BlockOutput(
            output=f"call_{len(self.calls)}",
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class FailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"

    async def execute(self, ctx):
        raise RuntimeError(f"Block {self.block_id} failed")


class WriterBlock(BaseBlock):
    """Simulates a writer agent: appends a draft to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.declared_inputs = {"round_num": "shared_memory.loop_block_round"}
        self.drafts: list[str] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        round_num = ctx.inputs.get("round_num", 0)
        self.drafts.append(f"draft_round_{round_num}")
        return BlockOutput(
            output=f"draft_round_{round_num}",
            shared_memory_updates={"drafts": list(self.drafts)},
        )


class CriticBlock(BaseBlock):
    """Simulates a critic agent: appends feedback to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.declared_inputs = {"round_num": "shared_memory.loop_block_round"}
        self.feedback: list[str] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        round_num = ctx.inputs.get("round_num", 0)
        self.feedback.append(f"feedback_round_{round_num}")
        return BlockOutput(
            output=f"feedback_round_{round_num}",
            shared_memory_updates={"feedback": list(self.feedback)},
        )


# ===========================================================================
# 1. LoopBlockDef schema — model validation
# ===========================================================================


class TestLoopBlockYamlParsing:
    """YAML parsing: type=loop parses correctly, type=retry raises error."""

    def test_loop_type_parses_to_loop_block_def(self):
        """type: loop with inner_block_refs should parse to LoopBlockDef in a workflow file."""
        from runsight_core.blocks.loop import LoopBlockDef

        raw = {
            "version": "1.0",
            "id": "loop_schema_workflow",
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
                "id": "loop_schema_workflow",
                "kind": "workflow",
                "name": "loop schema workflow",
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
        """type: retry in YAML should raise a clear error with no legacy alias path."""
        raw = {
            "version": "1.0",
            "id": "legacy_retry_workflow",
            "kind": "workflow",
            "blocks": {
                "retry_block": {
                    "type": "retry",
                    "inner_block_ref": "some_block",
                    "max_retries": 3,
                },
            },
            "workflow": {
                "id": "legacy_retry_workflow",
                "kind": "workflow",
                "name": "legacy retry workflow",
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
id: inline_retry_workflow
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
  id: legacy_retry_workflow
  kind: workflow
  name: legacy retry workflow
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
id: inline_loop_workflow
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
  id: loop_parse_workflow
  kind: workflow
  name: loop parse workflow
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
id: inline_loop_refs_workflow
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
  id: loop_refs_workflow
  kind: workflow
  name: loop refs workflow
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
