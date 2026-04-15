"""
Failing tests for RUN-892: Remove Step._resolve_from_ref, consolidate input resolution.

After this ticket:
- Step._resolve_from_ref is deleted
- Step.execute does: pre_hook → block.execute → post_hook only (no Phase 2)
- build_block_context receives declared_inputs from Step wrapper, resolves them
- _resolved_inputs key is NOT written to shared_memory

All tests currently fail because the old code still exists. They should pass
once the implementation is complete.

AC coverage:
  AC-1: Step._resolve_from_ref deleted (structural check)
  AC-2: Step.execute simplified — no input resolution, no _resolved_inputs side-effect
  AC-3: build_block_context with Step declared_inputs resolves correctly
  AC-4: Pre/post hooks still fire in correct order
  AC-5: _resolved_inputs no longer appears in shared_memory after execute_block
"""

from unittest.mock import MagicMock

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Step, Task
from runsight_core.state import BlockResult, WorkflowState

# ===========================================================================
# Helpers
# ===========================================================================


def make_state(results=None, shared_memory=None, current_task=None) -> WorkflowState:
    return WorkflowState(
        results=results or {},
        shared_memory=shared_memory or {},
        current_task=current_task,
    )


class CapturingBlock(BaseBlock):
    """Block that records the state it receives and returns it unchanged."""

    def __init__(self, block_id: str = "capture"):
        super().__init__(block_id=block_id)
        self.received_state: WorkflowState | None = None

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.received_state = state
        return state.model_copy(
            update={"results": {**state.results, self.block_id: BlockResult(output="captured")}}
        )


# ===========================================================================
# AC-1: Step._resolve_from_ref deleted
# ===========================================================================


class TestAC1ResolveFromRefDeleted:
    """_resolve_from_ref must not exist on Step after cleanup.

    These tests CURRENTLY FAIL because Step still has _resolve_from_ref.
    After RUN-892 implementation they should pass.
    """

    def test_step_has_no_resolve_from_ref_method(self):
        """Step class must not have a _resolve_from_ref attribute at all."""
        # This assertion currently FAILS because the method exists.
        assert not hasattr(Step, "_resolve_from_ref"), (
            "Step._resolve_from_ref still exists — delete it as part of RUN-892"
        )

    def test_step_instance_has_no_resolve_from_ref(self):
        """A Step instance must not expose _resolve_from_ref."""
        block = CapturingBlock("inner")
        step = Step(block=block, declared_inputs={"x": "src.output"})
        # Fail while method exists on the class (and therefore on the instance)
        assert not hasattr(step, "_resolve_from_ref"), (
            "Step instance still has _resolve_from_ref — expected it to be removed"
        )

    def test_resolve_from_ref_not_callable_on_step(self):
        """Calling step._resolve_from_ref must raise AttributeError."""
        block = CapturingBlock("inner")
        step = Step(block=block)
        with pytest.raises(AttributeError):
            # After deletion this should raise; currently it does NOT raise.
            _ = step._resolve_from_ref("source", make_state())  # type: ignore[attr-defined]


# ===========================================================================
# AC-2: Step.execute simplified — no input resolution
# ===========================================================================


class TestAC2StepExecuteSimplified:
    """Step.execute must not resolve inputs or write _resolved_inputs.

    These tests confirm that the ONLY phases in Step.execute are:
      pre_hook → block.execute → post_hook
    """

    @pytest.mark.asyncio
    async def test_step_execute_does_not_write_resolved_inputs_to_shared_memory(self):
        """Step.execute with declared_inputs must NOT inject _resolved_inputs into shared_memory.

        Currently FAILS because Phase 2 still writes this key.
        """
        block = CapturingBlock("inner")
        step = Step(
            block=block,
            declared_inputs={"data": "source_block.output"},
        )
        state = make_state(
            results={"source_block": BlockResult(output="hello")},
        )

        result_state = await step.execute(state)

        # The key must not appear — old code injects it, new code must not.
        assert "_resolved_inputs" not in result_state.shared_memory, (
            "Step.execute still writes _resolved_inputs — Phase 2 must be removed"
        )

    @pytest.mark.asyncio
    async def test_step_execute_calls_block_execute_and_returns_result(self):
        """Step.execute must still call the wrapped block and return its state."""
        block = CapturingBlock("inner")
        step = Step(block=block)
        state = make_state()

        result_state = await step.execute(state)

        assert block.received_state is not None
        assert "inner" in result_state.results

    @pytest.mark.asyncio
    async def test_step_execute_no_resolution_side_effects_with_empty_declared_inputs(self):
        """With empty declared_inputs, shared_memory must be completely untouched."""
        block = CapturingBlock("inner")
        step = Step(block=block, declared_inputs={})
        initial_sm = {"existing_key": "existing_value"}
        state = make_state(shared_memory=dict(initial_sm))

        result_state = await step.execute(state)

        # shared_memory should be identical (no writes)
        assert result_state.shared_memory == initial_sm

    @pytest.mark.asyncio
    async def test_step_execute_does_not_mutate_input_state_shared_memory(self):
        """Step.execute must not add any keys to shared_memory beyond what the block adds."""
        block = CapturingBlock("inner")
        step = Step(
            block=block,
            declared_inputs={"key": "prev.field"},
        )
        state = make_state(
            results={"prev": BlockResult(output='{"field": "value"}')},
        )
        keys_before = set(state.shared_memory.keys())

        result_state = await step.execute(state)

        keys_after = set(result_state.shared_memory.keys())
        # No new keys should have been added by Step (block itself adds nothing here)
        assert keys_after == keys_before, (
            f"Unexpected shared_memory keys added by Step: {keys_after - keys_before}"
        )


# ===========================================================================
# AC-3: build_block_context with Step declared_inputs
# ===========================================================================


class TestAC3BuildBlockContextWithStep:
    """build_block_context must resolve declared_inputs from a Step wrapper.

    This path already works (RUN-884), but we verify it continues to work
    and is the CANONICAL way to do input resolution post-RUN-892.
    """

    def _make_linear_block(self, block_id: str = "analyze"):
        """Return a minimal LinearBlock-like block that build_block_context can handle."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.primitives import Soul

        soul = Soul(
            id="analyst",
            role="Analyst",
            system_prompt="You analyze.",
            model_name="gpt-4o",
        )
        runner = MagicMock()
        runner.model_name = "gpt-4o"
        return LinearBlock(block_id=block_id, soul=soul, runner=runner)

    def test_build_block_context_resolves_declared_inputs_from_step(self):
        """build_block_context(block, state, step=step) resolves step.declared_inputs."""
        block = self._make_linear_block("analyze")
        step = Step(block=block, declared_inputs={"data": "fetch"})

        state = make_state(
            results={"fetch": BlockResult(output="fetched content")},
            current_task=Task(id="t1", instruction="analyze it"),
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
            current_task=Task(id="t1", instruction="summarize"),
        )

        ctx = build_block_context(block, state, step=step)

        assert ctx.inputs.get("status") == "ok"

    def test_build_block_context_empty_declared_inputs_produces_empty_inputs(self):
        """Step with no declared_inputs → BlockContext.inputs is empty."""
        block = self._make_linear_block("analyze")
        step = Step(block=block, declared_inputs={})

        state = make_state(
            results={"fetch": BlockResult(output="data")},
            current_task=Task(id="t1", instruction="go"),
        )

        ctx = build_block_context(block, state, step=step)

        assert ctx.inputs == {}

    def test_build_block_context_missing_source_raises_value_error(self):
        """build_block_context must raise ValueError if declared_inputs ref is missing."""
        block = self._make_linear_block("analyze")
        step = Step(block=block, declared_inputs={"data": "missing_block.output"})

        state = make_state(
            results={},
            current_task=Task(id="t1", instruction="do it"),
        )

        with pytest.raises(ValueError, match="missing_block"):
            build_block_context(block, state, step=step)


# ===========================================================================
# AC-4: Pre/post hooks still fire in correct order
# ===========================================================================


class TestAC4HooksFireInCorrectOrder:
    """Pre/post hooks must fire: pre → block → post."""

    @pytest.mark.asyncio
    async def test_pre_hook_fires_before_block(self):
        """pre_hook must run before block.execute."""
        call_order: list[str] = []

        class OrderBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                call_order.append("block")
                return state.model_copy(
                    update={"results": {**state.results, self.block_id: BlockResult(output="done")}}
                )

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
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                call_order.append("block")
                return state.model_copy(
                    update={"results": {**state.results, self.block_id: BlockResult(output="done")}}
                )

        def post_hook(state: WorkflowState) -> WorkflowState:
            call_order.append("post")
            return state

        block = OrderBlock("order_block")
        step = Step(block=block, post_hook=post_hook)

        await step.execute(make_state())

        assert call_order == ["block", "post"]

    @pytest.mark.asyncio
    async def test_both_hooks_fire_in_correct_order(self):
        """When both hooks present: pre → block → post."""
        call_order: list[str] = []

        class OrderBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                call_order.append("block")
                return state.model_copy(
                    update={"results": {**state.results, self.block_id: BlockResult(output="done")}}
                )

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
        """State modified by pre_hook must reach block.execute."""

        class InspectBlock(BaseBlock):
            def __init__(self, block_id: str):
                super().__init__(block_id=block_id)
                self.seen_memory: dict = {}

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                self.seen_memory = dict(state.shared_memory)
                return state.model_copy(
                    update={"results": {**state.results, self.block_id: BlockResult(output="ok")}}
                )

        block = InspectBlock("inspect")

        def pre_hook(state: WorkflowState) -> WorkflowState:
            return state.model_copy(
                update={"shared_memory": {**state.shared_memory, "hook_flag": True}}
            )

        step = Step(block=block, pre_hook=pre_hook)

        await step.execute(make_state())

        assert block.seen_memory.get("hook_flag") is True

    @pytest.mark.asyncio
    async def test_post_hook_receives_state_from_block(self):
        """post_hook must receive the state that block.execute returned."""
        captured_state: list[WorkflowState] = []

        class WritingBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                return state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: BlockResult(output="block_out"),
                        },
                        "shared_memory": {**state.shared_memory, "block_wrote": "yes"},
                    }
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
        """With both hooks and declared_inputs, _resolved_inputs must not appear.

        Currently FAILS because Phase 2 still injects _resolved_inputs.
        """
        call_order: list[str] = []

        class TrackBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                call_order.append("block")
                return state.model_copy(
                    update={"results": {**state.results, self.block_id: BlockResult(output="ok")}}
                )

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
            declared_inputs={"x": "src"},
        )
        state = make_state(results={"src": BlockResult(output="value")})

        result = await step.execute(state)

        assert call_order == ["pre", "block", "post"]
        assert "_resolved_inputs" not in result.shared_memory


# ===========================================================================
# AC-5: _resolved_inputs never appears in shared_memory after execute_block
# ===========================================================================


class TestAC5NoResolvedInputsInSharedMemory:
    """After execute_block processes a Step-wrapped block, shared_memory must
    not contain _resolved_inputs.

    Currently FAILS because Step.execute Phase 2 writes it.
    """

    @pytest.mark.asyncio
    async def test_execute_block_step_wrapped_no_resolved_inputs(self):
        """execute_block with a Step-wrapped LinearBlock must not write _resolved_inputs."""
        from runsight_core.workflow import BlockExecutionContext, execute_block

        block = CapturingBlock("cap")
        step = Step(
            block=block,
            declared_inputs={"data": "upstream"},
        )

        state = make_state(results={"upstream": BlockResult(output="upstream_value")})
        ctx = BlockExecutionContext(
            workflow_name="test_wf",
            blocks={"cap": step},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(step, state, ctx)

        assert "_resolved_inputs" not in result_state.shared_memory, (
            "_resolved_inputs should not exist in shared_memory after execute_block; "
            "old Step.execute Phase 2 still writes it"
        )

    @pytest.mark.asyncio
    async def test_shared_memory_pristine_after_step_with_declared_inputs(self):
        """shared_memory must contain exactly the keys that were there before execution.

        This verifies no side-effect keys leak from the old Phase 2 resolver.
        Currently FAILS because _resolved_inputs is injected.
        """
        block = CapturingBlock("cap")
        step = Step(
            block=block,
            declared_inputs={"a": "block_a", "b": "block_b"},
        )
        initial_sm = {"pre_existing": 42}
        state = make_state(
            results={
                "block_a": BlockResult(output="alpha"),
                "block_b": BlockResult(output="beta"),
            },
            shared_memory=dict(initial_sm),
        )

        result_state = await step.execute(state)

        # Only pre_existing should be present — no _resolved_inputs injected
        assert set(result_state.shared_memory.keys()) == {"pre_existing"}, (
            f"shared_memory has unexpected keys: {set(result_state.shared_memory.keys())}"
        )

    @pytest.mark.asyncio
    async def test_no_resolved_inputs_even_with_json_path(self):
        """JSON-path declared_input must not produce _resolved_inputs in shared_memory.

        Currently FAILS — the old resolver resolves AND writes to shared_memory.
        """
        import json

        block = CapturingBlock("cap")
        step = Step(
            block=block,
            declared_inputs={"status": "api.response.status"},
        )
        state = make_state(
            results={"api": BlockResult(output=json.dumps({"response": {"status": "ok"}}))}
        )

        result_state = await step.execute(state)

        assert "_resolved_inputs" not in result_state.shared_memory
