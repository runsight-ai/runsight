"""LoopBlock exit-handle control tests.

The suite covers retry and break routing inside loops, mid-round skipping,
source-level exception-handling governance, break-condition compatibility,
metadata, schema fields, parser wiring, and carry_context propagation.
"""

from conftest import block_output_from_state
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock, LoopBlockDef
from runsight_core.state import BlockResult
from runsight_core.yaml.schema import BaseBlockDef, BlockDef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"call_{len(self.calls)}"),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class ExitHandleBlock(BaseBlock):
    """Block that returns a BlockResult with a configurable exit_handle.

    Returns exit_handle=None for the first (threshold - 1) calls,
    then returns the configured exit_handle from call number `threshold` onward.
    """

    def __init__(self, block_id: str, exit_handle: str, threshold: int = 1):
        super().__init__(block_id)
        self.context_access = "declared"
        self._exit_handle = exit_handle
        self._threshold = threshold
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)

        if call_num >= self._threshold:
            handle = self._exit_handle
        else:
            handle = None

        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f"call_{call_num}_handle_{handle}",
                        exit_handle=handle,
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ==============================================================================
# retry_on_exit starts the next loop round
# ==============================================================================


class TestLoopBlockDefExitHandleFields:
    """LoopBlockDef must have break_on_exit and retry_on_exit fields.
    BaseBlockDef must not have these fields."""

    def test_loop_block_def_has_break_on_exit(self):
        """LoopBlockDef should have an optional break_on_exit field."""
        assert "break_on_exit" in LoopBlockDef.model_fields, (
            "LoopBlockDef missing 'break_on_exit' field"
        )

    def test_loop_block_def_has_retry_on_exit(self):
        """LoopBlockDef should have an optional retry_on_exit field."""
        assert "retry_on_exit" in LoopBlockDef.model_fields, (
            "LoopBlockDef missing 'retry_on_exit' field"
        )

    def test_base_block_def_does_not_have_break_on_exit(self):
        """BaseBlockDef should not have break_on_exit (loop-specific field)."""
        assert "break_on_exit" not in BaseBlockDef.model_fields, (
            "break_on_exit should be on LoopBlockDef, not BaseBlockDef"
        )

    def test_base_block_def_does_not_have_retry_on_exit(self):
        """BaseBlockDef should not have retry_on_exit (loop-specific field)."""
        assert "retry_on_exit" not in BaseBlockDef.model_fields, (
            "retry_on_exit should be on LoopBlockDef, not BaseBlockDef"
        )

    def test_break_on_exit_defaults_to_none(self):
        """break_on_exit should default to None."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_on_exit is None

    def test_retry_on_exit_defaults_to_none(self):
        """retry_on_exit should default to None."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_on_exit is None

    def test_break_on_exit_accepts_string(self):
        """break_on_exit should accept a string value."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
                "break_on_exit": "pass",
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_on_exit == "pass"

    def test_retry_on_exit_accepts_string(self):
        """retry_on_exit should accept a string value."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
                "retry_on_exit": "fail",
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_on_exit == "fail"

    def test_both_fields_set_simultaneously(self):
        """Both break_on_exit and retry_on_exit can be set at the same time."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
                "break_on_exit": "pass",
                "retry_on_exit": "fail",
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_on_exit == "pass"
        assert block.retry_on_exit == "fail"


# ==============================================================================
# Constructor: LoopBlock accepts break_on_exit / retry_on_exit
# ==============================================================================


class TestLoopBlockConstructorExitHandleParams:
    """LoopBlock constructor must accept break_on_exit and retry_on_exit parameters."""

    def test_constructor_accepts_break_on_exit(self):
        """LoopBlock should accept break_on_exit parameter."""
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            break_on_exit="pass",
        )
        assert loop.break_on_exit == "pass"

    def test_constructor_accepts_retry_on_exit(self):
        """LoopBlock should accept retry_on_exit parameter."""
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        assert loop.retry_on_exit == "fail"

    def test_constructor_defaults_exit_handle_fields_to_none(self):
        """break_on_exit and retry_on_exit should default to None."""
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
        )
        assert loop.break_on_exit is None
        assert loop.retry_on_exit is None


# ==============================================================================
# Parser: break_on_exit / retry_on_exit wired from LoopBlockDef to LoopBlock
# ==============================================================================


class TestParserWiresExitHandleFields:
    """Parser must wire break_on_exit and retry_on_exit from LoopBlockDef
    to LoopBlock constructor via the build() function."""

    def test_build_passes_break_on_exit(self):
        """build() should pass break_on_exit from block_def to LoopBlock."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            break_on_exit="pass",
        )
        loop = build("review_loop", block_def, {}, None, {})
        assert loop.break_on_exit == "pass"

    def test_build_passes_retry_on_exit(self):
        """build() should pass retry_on_exit from block_def to LoopBlock."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        loop = build("review_loop", block_def, {}, None, {})
        assert loop.retry_on_exit == "fail"

    def test_build_defaults_exit_fields_to_none(self):
        """build() with no exit handle fields should produce a LoopBlock with both as None."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
        )
        loop = build("review_loop", block_def, {}, None, {})
        assert loop.break_on_exit is None
        assert loop.retry_on_exit is None

    def test_full_yaml_parsing_with_exit_handle_fields(self):
        """Full YAML parsing should wire break_on_exit and retry_on_exit to LoopBlock."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """
version: "1.0"
id: loop_exit_handle_fixture
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
  gate_block:
    type: gate
    soul_ref: reviewer
    eval_key: write_block
  loop_block:
    type: loop
    inner_block_refs:
      - write_block
      - gate_block
    max_rounds: 5
    break_on_exit: "pass"
    retry_on_exit: "fail"
workflow:
  id: loop_exit_handle_parse
  kind: workflow
  name: loop_exit_handle_parse
  entry: loop_block
  transitions:
    - from: loop_block
      to:
"""
        wf = parse_workflow_yaml(yaml_str)
        loop = wf.blocks.get("loop_block")
        assert isinstance(loop, LoopBlock)
        assert loop.break_on_exit == "pass"
        assert loop.retry_on_exit == "fail"


# ==============================================================================
# Combined: break_on_exit + retry_on_exit together
# ==============================================================================
