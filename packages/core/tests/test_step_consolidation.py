"""Step input-resolution consolidation coverage.

Behavior boundary: Step no longer resolves declared inputs itself, block
context construction owns declared input resolution, hook ordering stays stable,
and execution does not write _resolved_inputs into shared memory.
"""

from unittest.mock import MagicMock

import pytest
from runsight_core.block_io import BlockContext, BlockOutput, build_block_context
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState

MODEL_REQUIRED_SENTINEL = "__runsight_explicit_model_required__"

# ===========================================================================
# Helpers
# ===========================================================================


def make_state(results=None, shared_memory=None) -> WorkflowState:
    return WorkflowState(
        results=results or {},
        shared_memory=shared_memory or {},
    )


class CapturingBlock(BaseBlock):
    """Block that records the ctx it receives and returns a BlockOutput."""

    def __init__(self, block_id: str = "capture"):
        super().__init__(block_id=block_id)
        self.received_ctx: BlockContext | None = None

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.received_ctx = ctx
        return BlockOutput(output="captured")


# ===========================================================================
# Retired Step private resolver surface
# ===========================================================================


class TestResolveFromRefRetired:
    """_resolve_from_ref should stay absent from Step after input consolidation."""

    def test_step_has_no_resolve_from_ref_method(self):
        """Step class must not have a _resolve_from_ref attribute at all."""
        assert not hasattr(Step, "_resolve_from_ref"), "Step._resolve_from_ref still exists"

    def test_step_instance_has_no_resolve_from_ref(self):
        """A Step instance must not expose _resolve_from_ref."""
        block = CapturingBlock("capturing_block")
        step = Step(block=block, declared_inputs={"payload": "source_block.output"})
        assert not hasattr(step, "_resolve_from_ref"), "Step instance still has _resolve_from_ref"

    def test_resolve_from_ref_not_callable_on_step(self):
        """Calling step._resolve_from_ref must raise AttributeError."""
        block = CapturingBlock("capturing_block")
        step = Step(block=block)
        with pytest.raises(AttributeError):
            _ = step._resolve_from_ref("source", make_state())  # type: ignore[attr-defined]


# ===========================================================================
# Step.execute delegates without input-resolution side effects
# ===========================================================================


class TestStepExecuteDelegation:
    """Step.execute must not resolve inputs or write _resolved_inputs.

    These tests confirm that the Step.execute phases are:
      pre_hook -> block.execute -> post_hook
    """

    @pytest.mark.asyncio
    async def test_step_execute_does_not_write_resolved_inputs_to_shared_memory(self):
        """Step.execute with declared_inputs must not inject _resolved_inputs."""
        block = CapturingBlock("capturing_block")
        step = Step(
            block=block,
            declared_inputs={"data": "source_block.output"},
        )
        state = make_state(
            results={"source_block": BlockResult(output="hello")},
        )

        result_state = await step.execute(state)

        assert "_resolved_inputs" not in result_state.shared_memory, (
            "Step.execute still writes _resolved_inputs"
        )

    @pytest.mark.asyncio
    async def test_step_execute_calls_block_execute_and_returns_result(self):
        """Step.execute must still call the wrapped block and return its state."""
        block = CapturingBlock("capturing_block")
        step = Step(block=block)
        state = make_state()

        result_state = await step.execute(state)

        assert block.received_ctx is not None
        assert "capturing_block" in result_state.results

    @pytest.mark.asyncio
    async def test_step_execute_no_resolution_side_effects_with_empty_declared_inputs(self):
        """With empty declared_inputs, shared_memory must be completely untouched."""
        block = CapturingBlock("capturing_block")
        step = Step(block=block, declared_inputs={})
        initial_sm = {"existing_key": "existing_value"}
        state = make_state(
            shared_memory=dict(initial_sm),
        )

        result_state = await step.execute(state)

        # shared_memory should be identical (no writes)
        assert result_state.shared_memory == initial_sm

    @pytest.mark.asyncio
    async def test_step_execute_does_not_mutate_input_state_shared_memory(self):
        """Step.execute must not add any keys to shared_memory beyond what the block adds."""
        block = CapturingBlock("capturing_block")
        step = Step(
            block=block,
            declared_inputs={"key": "previous_block.field"},
        )
        state = make_state(
            results={"previous_block": BlockResult(output='{"field": "value"}')},
        )
        keys_before = set(state.shared_memory.keys())

        result_state = await step.execute(state)

        keys_after = set(result_state.shared_memory.keys())
        # No new keys should have been added by Step (block itself adds nothing here)
        assert keys_after == keys_before, (
            f"Unexpected shared_memory keys added by Step: {keys_after - keys_before}"
        )


# ===========================================================================
# build_block_context resolves Step declared inputs
# ===========================================================================


class TestStepBlockContextBuilder:
    """build_block_context must resolve declared_inputs from a Step wrapper.

    This pins block context construction as the owner of input resolution.
    """

    def _make_linear_block(self, block_id: str = "analyze"):
        """Return a minimal LinearBlock-like block that build_block_context can handle."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.primitives import Soul

        soul = Soul(
            id="analyst",
            kind="soul",
            name="Analyst Soul",
            role="Analyst",
            system_prompt="You analyze.",
            model_name=MODEL_REQUIRED_SENTINEL,
        )
        runner = MagicMock()
        runner.model_name = MODEL_REQUIRED_SENTINEL
        return LinearBlock(block_id=block_id, soul=soul, runner=runner)

    def test_build_block_context_resolves_declared_inputs_from_step(self):
        """build_block_context(block, state, step=step) resolves step.declared_inputs."""
        block = self._make_linear_block("analyze")
        step = Step(block=block, declared_inputs={"data": "fetch"})

        state = make_state(
            results={"fetch": BlockResult(output="fetched content")},
        )

        ctx = build_block_context(block, state, step=step)

        assert ctx.inputs.get("data") == "fetched content"

    def test_build_block_context_resolves_dotted_path_from_step_declared_inputs(self):
        """build_block_context resolves dot-paths in declared_inputs via the Step."""
        import json

        block = self._make_linear_block("summarize")
        step = Step(block=block, declared_inputs={"status": "api_call.response.status"})

        state = make_state(
            results={
                "api_call": BlockResult(
                    output=json.dumps({"response": {"status": "ok", "code": 200}})
                )
            },
        )

        ctx = build_block_context(block, state, step=step)

        assert ctx.inputs.get("status") == "ok"

    def test_build_block_context_empty_declared_inputs_produces_empty_inputs(self):
        """Step with no declared_inputs produces empty BlockContext.inputs."""
        block = self._make_linear_block("analyze")
        step = Step(block=block, declared_inputs={})

        state = make_state(
            results={"fetch": BlockResult(output="data")},
        )

        ctx = build_block_context(block, state, step=step)

        assert ctx.inputs == {}

    def test_build_block_context_missing_source_raises_value_error(self):
        """build_block_context must raise ValueError if declared_inputs ref is missing."""
        block = self._make_linear_block("analyze")
        step = Step(block=block, declared_inputs={"data": "missing_block.output"})

        state = make_state(
            results={},
        )

        with pytest.raises(ValueError, match="missing_block"):
            build_block_context(block, state, step=step)


# ===========================================================================
# Pre/post hook ordering
# ===========================================================================


class TestStepHookOrdering:
    """Pre/post hooks must fire in pre, block, post order."""

    @pytest.mark.asyncio
    async def test_pre_hook_fires_before_block(self):
        """pre_hook must run before block.execute."""
        call_order: list[str] = []

        class OrderBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                call_order.append("block")
                return BlockOutput(output="done")

        def pre_hook(state: WorkflowState) -> WorkflowState:
            call_order.append("pre")
            return state

        block = OrderBlock("order_block")
        step = Step(block=block, pre_hook=pre_hook)

        await step.execute(make_state())

        assert call_order == ["pre", "block"]

    @pytest.mark.asyncio
    async def test_post_hook_fires_after_block(self):
        """post_hook must run after block.execute."""
        call_order: list[str] = []

        class OrderBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                call_order.append("block")
                return BlockOutput(output="done")

        def post_hook(state: WorkflowState) -> WorkflowState:
            call_order.append("post")
            return state

        block = OrderBlock("order_block")
        step = Step(block=block, post_hook=post_hook)

        await step.execute(make_state())

        assert call_order == ["block", "post"]

    @pytest.mark.asyncio
    async def test_both_hooks_fire_in_correct_order(self):
        """When both hooks are present, order is pre, block, post."""
        call_order: list[str] = []

        class OrderBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                call_order.append("block")
                return BlockOutput(output="done")

        def pre_hook(state: WorkflowState) -> WorkflowState:
            call_order.append("pre")
            return state

        def post_hook(state: WorkflowState) -> WorkflowState:
            call_order.append("post")
            return state

        block = OrderBlock("order_block")
        step = Step(block=block, pre_hook=pre_hook, post_hook=post_hook)

        await step.execute(make_state())

        assert call_order == ["pre", "block", "post"]

    @pytest.mark.asyncio
    async def test_pre_hook_state_modification_is_visible_to_block(self):
        """State modified by pre_hook must reach the block (reflected in result state)."""

        class InspectBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                return BlockOutput(output="ok")

        block = InspectBlock("inspect")

        call_order: list[str] = []

        def pre_hook(state: WorkflowState) -> WorkflowState:
            call_order.append("pre")
            return state.model_copy(
                update={"shared_memory": {**state.shared_memory, "hook_flag": True}}
            )

        step = Step(block=block, pre_hook=pre_hook)

        result = await step.execute(make_state())

        # pre_hook ran and inspect block ran (call_order shows pre happened)
        assert "pre" in call_order
        # The pre_hook change to shared_memory survives to the result state
        assert result.shared_memory.get("hook_flag") is True

    @pytest.mark.asyncio
    async def test_post_hook_receives_state_from_block(self):
        """post_hook must receive the state that apply_block_output returned."""
        captured_state: list[WorkflowState] = []

        class WritingBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                return BlockOutput(
                    output="block_out",
                    shared_memory_updates={"block_wrote": "yes"},
                )

        def post_hook(state: WorkflowState) -> WorkflowState:
            captured_state.append(state)
            return state

        block = WritingBlock("writer")
        step = Step(block=block, post_hook=post_hook)

        await step.execute(make_state())

        assert len(captured_state) == 1
        assert captured_state[0].shared_memory.get("block_wrote") == "yes"

    @pytest.mark.asyncio
    async def test_hooks_and_declared_inputs_together_no_resolved_inputs_key(self):
        """With both hooks and declared_inputs, _resolved_inputs must not appear."""
        call_order: list[str] = []

        class TrackBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                call_order.append("block")
                return BlockOutput(output="ok")

        def pre_hook(s: WorkflowState) -> WorkflowState:
            call_order.append("pre")
            return s

        def post_hook(s: WorkflowState) -> WorkflowState:
            call_order.append("post")
            return s

        block = TrackBlock("track")
        step = Step(
            block=block,
            pre_hook=pre_hook,
            post_hook=post_hook,
            declared_inputs={"payload": "source_value"},
        )
        state = make_state(
            results={"source_value": BlockResult(output="value")},
        )

        result = await step.execute(state)

        assert call_order == ["pre", "block", "post"]
        assert "_resolved_inputs" not in result.shared_memory


# ===========================================================================
# execute_block keeps resolved inputs out of shared memory
# ===========================================================================


class TestResolvedInputsStayOutOfSharedMemory:
    """After execute_block processes a Step-wrapped block, shared_memory must
    not contain _resolved_inputs.
    """

    @pytest.mark.asyncio
    async def test_execute_block_step_wrapped_no_resolved_inputs(self):
        """execute_block with a Step-wrapped LinearBlock must not write _resolved_inputs."""
        from runsight_core.workflow import BlockExecutionContext, execute_block

        block = CapturingBlock("capture_block")
        step = Step(
            block=block,
            declared_inputs={"data": "upstream"},
        )

        state = make_state(
            results={"upstream": BlockResult(output="upstream_value")},
        )
        ctx = BlockExecutionContext(
            workflow_name="step_consolidation_workflow",
            blocks={"capture_block": step},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(step, state, ctx)

        assert "_resolved_inputs" not in result_state.shared_memory, (
            "_resolved_inputs should not exist in shared_memory after execute_block; "
            "Step.execute still writes it"
        )

    @pytest.mark.asyncio
    async def test_shared_memory_pristine_after_step_with_declared_inputs(self):
        """shared_memory must contain exactly the keys that were there before execution.

        This verifies no side-effect keys leak from the old Phase 2 resolver.
        """
        block = CapturingBlock("capture_block")
        step = Step(
            block=block,
            declared_inputs={"alpha": "alpha_source", "beta": "beta_source"},
        )
        initial_sm = {"pre_existing": 42}
        state = make_state(
            results={
                "alpha_source": BlockResult(output="alpha"),
                "beta_source": BlockResult(output="beta"),
            },
            shared_memory=dict(initial_sm),
        )

        result_state = await step.execute(state)

        assert set(result_state.shared_memory.keys()) == {"pre_existing"}, (
            f"shared_memory has unexpected keys: {set(result_state.shared_memory.keys())}"
        )

    @pytest.mark.asyncio
    async def test_no_resolved_inputs_even_with_json_path(self):
        """JSON-path declared_input must not produce _resolved_inputs in shared_memory."""
        import json

        block = CapturingBlock("capture_block")
        step = Step(
            block=block,
            declared_inputs={"status": "api.response.status"},
        )
        state = make_state(
            results={"api": BlockResult(output=json.dumps({"response": {"status": "ok"}}))},
        )

        result_state = await step.execute(state)

        assert "_resolved_inputs" not in result_state.shared_memory
