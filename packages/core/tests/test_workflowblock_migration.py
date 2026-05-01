"""WorkflowBlock BlockContext and BlockOutput migration coverage.

Boundary: WorkflowBlock execution and execute_block dispatch must preserve the
BlockContext to BlockOutput contract, invocation input mapping, child output
mapping, call-stack cycle/depth guards, catch-mode errors, cost/token
propagation, and WorkflowState application. Owner: packages/core runtime block
execution. Exit criteria: remove this migration guard once equivalent behavior
coverage lives in ordinary WorkflowBlock and execute_block suites.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block

pytestmark = pytest.mark.migration

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_mock_invoked_workflow(
    name: str = "invoked_workflow",
    cost: float = 0.0,
    tokens: int = 0,
    result_key: str = "invoked_result",
    result_output: str = "invoked output",
) -> MagicMock:
    """Return a mock invoked workflow whose run() resolves to a plausible WorkflowState."""
    workflow = MagicMock()
    workflow.name = name
    invoked_final_state = WorkflowState(
        results={result_key: BlockResult(output=result_output)},
        total_cost_usd=cost,
        total_tokens=tokens,
    )
    workflow.run = AsyncMock(return_value=invoked_final_state)
    return workflow


def _make_workflow_block(
    block_id: str = "call_invoked_workflow",
    invoked_workflow=None,
    inputs: dict | None = None,
    outputs: dict | None = None,
    on_error: str = "raise",
    max_depth: int = 10,
) -> WorkflowBlock:
    if invoked_workflow is None:
        invoked_workflow = _make_mock_invoked_workflow()
    return WorkflowBlock(
        block_id=block_id,
        child_workflow=invoked_workflow,
        inputs=inputs or {},
        outputs=outputs or {},
        on_error=on_error,
        max_depth=max_depth,
    )


def _make_block_context(
    block_id: str,
    state: WorkflowState,
    call_stack: list | None = None,
    workflow_registry=None,
) -> BlockContext:
    """Build a BlockContext for WorkflowBlock (as build_block_context will produce after migration).

    WorkflowBlock needs call_stack and workflow_registry passed via inputs, and state_snapshot
    provides the full parent WorkflowState for _map_inputs.
    """
    return BlockContext(
        block_id=block_id,
        instruction="call invoked workflow",
        context=None,
        inputs={
            "call_stack": call_stack or [],
            "workflow_registry": workflow_registry,
        },
        conversation_history=[],
        soul=None,
        model_name=None,
        state_snapshot=state,
    )


def _make_base_state(
    shared_memory: dict | None = None,
    results: dict | None = None,
    instruction: str = "run invoked workflow",
) -> WorkflowState:
    return WorkflowState(
        shared_memory=shared_memory or {},
        results=results or {},
    )


def _make_exec_ctx(
    call_stack: list | None = None,
    workflow_registry=None,
) -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name="caller_workflow",
        blocks={},
        call_stack=call_stack or [],
        workflow_registry=workflow_registry,
        observer=None,
    )


# ---------------------------------------------------------------------------
# BlockContext and BlockOutput contract
# ---------------------------------------------------------------------------


class TestAcceptsBlockContextAndReturnsBlockOutput:
    """WorkflowBlock.execute must accept a BlockContext and return BlockOutput."""

    @pytest.mark.asyncio
    async def test_execute_accepts_block_context_returns_block_output(self):
        """WorkflowBlock.execute(ctx: BlockContext) must return BlockOutput."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput), (
            f"Expected BlockOutput but got {type(result).__name__}. "
            "WorkflowBlock.execute must return BlockOutput after the migration."
        )

    @pytest.mark.asyncio
    async def test_execute_output_contains_completed_message(self):
        """BlockOutput.output must be \"WorkflowBlock '{name}' completed\"."""
        invoked_workflow = _make_mock_invoked_workflow(name="named_invoked_workflow")
        block = _make_workflow_block(
            block_id="call_named_invoked_workflow",
            invoked_workflow=invoked_workflow,
        )
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.output == "WorkflowBlock 'named_invoked_workflow' completed", (
            "Expected output \"WorkflowBlock 'named_invoked_workflow' completed\" "
            f"but got: {result.output!r}"
        )

    @pytest.mark.asyncio
    async def test_execute_exit_handle_is_completed(self):
        """BlockOutput.exit_handle must be 'completed' on success."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.exit_handle == "completed", (
            f"Expected exit_handle='completed' but got: {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_execute_metadata_contains_child_status(self):
        """BlockOutput.metadata must contain child_status='completed'."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert "child_status" in result.metadata, "BlockOutput.metadata must contain 'child_status'"
        assert result.metadata["child_status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_metadata_contains_child_cost_usd(self):
        """BlockOutput.metadata must contain child_cost_usd."""
        invoked_workflow = _make_mock_invoked_workflow(cost=0.07, tokens=350)
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert "child_cost_usd" in result.metadata
        assert result.metadata["child_cost_usd"] == pytest.approx(0.07)

    @pytest.mark.asyncio
    async def test_execute_metadata_contains_child_tokens(self):
        """BlockOutput.metadata must contain child_tokens."""
        invoked_workflow = _make_mock_invoked_workflow(cost=0.0, tokens=500)
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert "child_tokens" in result.metadata
        assert result.metadata["child_tokens"] == 500

    @pytest.mark.asyncio
    async def test_execute_does_not_return_workflow_state(self):
        """WorkflowBlock.execute(BlockContext) must return BlockOutput, not WorkflowState."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert not isinstance(result, WorkflowState), (
            "WorkflowBlock.execute(BlockContext) must return BlockOutput, not WorkflowState. "
            "After the migration, state mutation is the caller's responsibility via apply_block_output."
        )


# ---------------------------------------------------------------------------
# Invocation input and child output mapping
# ---------------------------------------------------------------------------


class TestWorkflowBlockInputOutputMapping:
    """WorkflowBlock mapping must align with public invocation input/output semantics."""

    @pytest.mark.asyncio
    async def test_input_mapping_resolves_from_state_snapshot(self):
        """Parent refs resolve from state_snapshot and pass as child invocation inputs."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(
            invoked_workflow=invoked_workflow,
            inputs={"topic": "shared_memory.research_topic"},
        )
        state = _make_base_state(shared_memory={"research_topic": "quantum computing"})
        ctx = _make_block_context(block.block_id, state)
        ctx = ctx.model_copy(
            update={
                "inputs": {
                    **ctx.inputs,
                    "topic": "quantum computing",
                }
            }
        )

        await block.execute(ctx)

        call_args = invoked_workflow.run.call_args
        child_state_arg = call_args[0][0]
        assert call_args.kwargs["inputs"] == {"topic": "quantum computing"}
        assert child_state_arg.shared_memory == {}
        assert child_state_arg.results == {}
        assert child_state_arg.metadata == {}

    @pytest.mark.asyncio
    async def test_output_mapping_written_to_block_output(self):
        """Output mappings from child state must appear in BlockOutput (extra_results or shared_memory_updates)."""
        invoked_workflow = _make_mock_invoked_workflow(
            result_key="analysis",
            result_output="analysis findings",
        )
        block = _make_workflow_block(
            invoked_workflow=invoked_workflow,
            outputs={"results.parent_analysis": "results.analysis"},
        )
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        # After migration, mapped outputs are carried in extra_results
        assert result.extra_results is not None, (
            "WorkflowBlock.execute must populate BlockOutput.extra_results with output-mapped data"
        )
        assert "parent_analysis" in result.extra_results, (
            "Expected 'parent_analysis' key in BlockOutput.extra_results from output mapping"
        )

    @pytest.mark.asyncio
    async def test_input_mapping_missing_key_raises_key_error(self):
        """Missing parent key in dotted path resolution raises KeyError (preserved behavior)."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(
            invoked_workflow=invoked_workflow,
            inputs={"topic": "shared_memory.nonexistent"},
        )
        state = _make_base_state(shared_memory={"other_key": "value"})
        ctx = _make_block_context(block.block_id, state)

        with pytest.raises(KeyError):
            await block.execute(ctx)

    @pytest.mark.asyncio
    async def test_shared_memory_output_mapping_written_to_shared_memory_updates(self):
        """shared_memory output mappings must appear in BlockOutput.shared_memory_updates."""
        invoked_final_state = WorkflowState(
            shared_memory={"invoked_output": "result value"},
            total_cost_usd=0.0,
            total_tokens=0,
        )
        invoked_workflow = MagicMock()
        invoked_workflow.name = "shared_memory_source_workflow"
        invoked_workflow.run = AsyncMock(return_value=invoked_final_state)

        block = _make_workflow_block(
            invoked_workflow=invoked_workflow,
            outputs={"shared_memory.mapped_output": "shared_memory.invoked_output"},
        )
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        # shared_memory mappings should appear in shared_memory_updates
        has_mapping = (
            result.shared_memory_updates is not None
            and "mapped_output" in result.shared_memory_updates
        ) or (result.extra_results is not None and "shared_memory" in (result.extra_results or {}))
        assert has_mapping, (
            "WorkflowBlock.execute must carry output-mapped shared_memory data "
            "in BlockOutput.shared_memory_updates or extra_results"
        )

    @pytest.mark.asyncio
    async def test_apply_block_output_merges_extra_results_into_state(self):
        """apply_block_output must merge extra_results from WorkflowBlock into state.results."""
        invoked_workflow = _make_mock_invoked_workflow(
            result_key="analysis",
            result_output="analysis findings",
        )
        block = _make_workflow_block(
            invoked_workflow=invoked_workflow,
            outputs={"results.parent_analysis": "results.analysis"},
        )
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)
        assert isinstance(result, BlockOutput)

        # apply_block_output is called in execute_block; simulate it here.
        new_state = apply_block_output(state, block.block_id, result)

        assert "parent_analysis" in new_state.results, (
            "After apply_block_output, output-mapped 'parent_analysis' must appear in state.results"
        )


# ---------------------------------------------------------------------------
# Call-stack cycle and depth limits
# ---------------------------------------------------------------------------


class TestWorkflowBlockCycleAndDepthLimits:
    """Cycle detection and depth limits must use call_stack from BlockContext.inputs."""

    @pytest.mark.asyncio
    async def test_cycle_detection_raises_recursion_error_when_child_in_call_stack(self):
        """RecursionError raised when child workflow name is already in call_stack from ctx."""
        invoked_workflow = _make_mock_invoked_workflow(name="recursive_invoked_workflow")
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        # call_stack already contains the child, so the cycle guard should fire.
        ctx = _make_block_context(
            block.block_id,
            state,
            call_stack=["caller_workflow", "recursive_invoked_workflow"],
        )

        with pytest.raises(RecursionError) as exc_info:
            await block.execute(ctx)

        assert "cycle" in str(exc_info.value).lower() or "recursive_invoked_workflow" in str(
            exc_info.value
        ), "RecursionError message must mention cycle or the child workflow name"

    @pytest.mark.asyncio
    async def test_depth_limit_raises_recursion_error_when_call_stack_at_max(self):
        """RecursionError raised when len(call_stack) >= max_depth."""
        invoked_workflow = _make_mock_invoked_workflow(name="new_invoked_workflow")
        block = _make_workflow_block(invoked_workflow=invoked_workflow, max_depth=3)
        state = _make_base_state()
        # Call stack already at depth 3 (== max_depth)
        ctx = _make_block_context(
            block.block_id,
            state,
            call_stack=["draft_workflow", "review_workflow", "publish_workflow"],
        )

        with pytest.raises(RecursionError) as exc_info:
            await block.execute(ctx)

        assert (
            "depth" in str(exc_info.value).lower() or "exceeded" in str(exc_info.value).lower()
        ), "RecursionError message must mention depth or exceeded"

    @pytest.mark.asyncio
    async def test_no_recursion_error_when_call_stack_below_max_depth(self):
        """No RecursionError when call_stack is below max_depth and child not in stack."""
        invoked_workflow = _make_mock_invoked_workflow(name="acyclic_invoked_workflow")
        block = _make_workflow_block(invoked_workflow=invoked_workflow, max_depth=5)
        state = _make_base_state()
        # Only two entries, max_depth is five, and child is not in stack.
        ctx = _make_block_context(
            block.block_id,
            state,
            call_stack=["draft_workflow", "review_workflow"],
        )

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)

    @pytest.mark.asyncio
    async def test_call_stack_extended_when_calling_child(self):
        """Child workflow.run() receives call_stack extended with child name."""
        invoked_workflow = _make_mock_invoked_workflow(name="stacked_invoked_workflow")
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state, call_stack=["caller_workflow"])

        await block.execute(ctx)

        call_args = invoked_workflow.run.call_args
        passed_call_stack = (
            call_args[1].get("call_stack") or call_args[0][1]
            if len(call_args[0]) > 1
            else call_args[1].get("call_stack")
        )
        assert "stacked_invoked_workflow" in passed_call_stack, (
            "child workflow.run() must receive call_stack containing child's own name"
        )
        assert "caller_workflow" in passed_call_stack, (
            "child workflow.run() must receive call_stack containing parent name"
        )


# ---------------------------------------------------------------------------
# Catch-mode error output
# ---------------------------------------------------------------------------


class TestWorkflowBlockOnErrorCatch:
    """on_error='catch' must swallow exceptions and return BlockOutput with exit_handle='error'."""

    @pytest.mark.asyncio
    async def test_on_error_catch_returns_block_output_with_error_exit_handle(self):
        """on_error='catch': exception swallowed, BlockOutput.exit_handle == 'error'."""
        invoked_workflow = MagicMock()
        invoked_workflow.name = "failing_invoked_workflow"
        invoked_workflow.run = AsyncMock(side_effect=RuntimeError("child timeout"))

        block = _make_workflow_block(invoked_workflow=invoked_workflow, on_error="catch")
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput), (
            f"on_error='catch' must return BlockOutput, not raise. Got {type(result).__name__}"
        )
        assert result.exit_handle == "error", (
            f"Expected exit_handle='error' for caught exception, got: {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_on_error_catch_output_contains_error_message(self):
        """BlockOutput.output must contain error information when on_error='catch'."""
        invoked_workflow = MagicMock()
        invoked_workflow.name = "failing_invoked_workflow"
        invoked_workflow.run = AsyncMock(side_effect=ValueError("Invalid configuration"))

        block = _make_workflow_block(invoked_workflow=invoked_workflow, on_error="catch")
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.output is not None and len(result.output) > 0, (
            "BlockOutput.output must not be empty when on_error='catch' catches an exception"
        )
        # Either the child name or failure marker should be present
        assert "failing_invoked_workflow" in result.output or "failed" in result.output.lower(), (
            f"BlockOutput.output should reference the failure. Got: {result.output!r}"
        )

    @pytest.mark.asyncio
    async def test_on_error_catch_metadata_child_status_failed(self):
        """BlockOutput.metadata must have child_status='failed' when on_error='catch' catches."""
        invoked_workflow = MagicMock()
        invoked_workflow.name = "failing_invoked_workflow"
        invoked_workflow.run = AsyncMock(side_effect=RuntimeError("child execution error"))

        block = _make_workflow_block(invoked_workflow=invoked_workflow, on_error="catch")
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.metadata.get("child_status") == "failed", (
            "metadata['child_status'] must be 'failed' when on_error='catch' catches exception"
        )

    @pytest.mark.asyncio
    async def test_on_error_raise_propagates_exception(self):
        """on_error='raise' propagates exceptions."""
        invoked_workflow = MagicMock()
        invoked_workflow.name = "failing_invoked_workflow"
        invoked_workflow.run = AsyncMock(side_effect=RuntimeError("fatal error"))

        block = _make_workflow_block(invoked_workflow=invoked_workflow, on_error="raise")
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        with pytest.raises(RuntimeError, match="fatal error"):
            await block.execute(ctx)

    @pytest.mark.asyncio
    async def test_on_error_catch_no_exception_propagated(self):
        """on_error='catch' must not propagate any exception to the caller."""
        invoked_workflow = MagicMock()
        invoked_workflow.name = "failing_invoked_workflow"
        invoked_workflow.run = AsyncMock(side_effect=Exception("anything at all"))

        block = _make_workflow_block(invoked_workflow=invoked_workflow, on_error="catch")
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        # Must not raise
        result = await block.execute(ctx)
        assert isinstance(result, BlockOutput)


# ---------------------------------------------------------------------------
# Child workflow cost and token propagation
# ---------------------------------------------------------------------------


class TestWorkflowBlockCostTokenPropagation:
    """Child cost/tokens must propagate correctly into BlockOutput fields."""

    @pytest.mark.asyncio
    async def test_block_output_cost_usd_reflects_child_cost(self):
        """BlockOutput.cost_usd must equal child workflow's total_cost_usd."""
        invoked_workflow = _make_mock_invoked_workflow(cost=0.15, tokens=750)
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.cost_usd == pytest.approx(0.15), (
            f"BlockOutput.cost_usd must equal child's total_cost_usd=0.15, got {result.cost_usd}"
        )

    @pytest.mark.asyncio
    async def test_block_output_total_tokens_reflects_child_tokens(self):
        """BlockOutput.total_tokens must equal child workflow's total_tokens."""
        invoked_workflow = _make_mock_invoked_workflow(cost=0.0, tokens=1200)
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.total_tokens == 1200, (
            f"BlockOutput.total_tokens must equal child's total_tokens=1200, got {result.total_tokens}"
        )

    @pytest.mark.asyncio
    async def test_apply_block_output_accumulates_cost_on_state(self):
        """apply_block_output must accumulate BlockOutput.cost_usd onto state.total_cost_usd."""
        invoked_workflow = _make_mock_invoked_workflow(cost=0.10, tokens=500)
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        state = state.model_copy(update={"total_cost_usd": 0.05, "total_tokens": 100})
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)
        assert isinstance(result, BlockOutput)

        new_state = apply_block_output(state, block.block_id, result)

        assert new_state.total_cost_usd == pytest.approx(0.15), (
            f"State total_cost_usd must be 0.05+0.10=0.15, got {new_state.total_cost_usd}"
        )
        assert new_state.total_tokens == 600, (
            f"State total_tokens must be 100+500=600, got {new_state.total_tokens}"
        )

    @pytest.mark.asyncio
    async def test_on_error_catch_zero_cost_when_child_fails(self):
        """When on_error='catch' catches an exception, BlockOutput.cost_usd must be 0."""
        invoked_workflow = MagicMock()
        invoked_workflow.name = "failing_invoked_workflow"
        invoked_workflow.run = AsyncMock(side_effect=RuntimeError("failure"))

        block = _make_workflow_block(invoked_workflow=invoked_workflow, on_error="catch")
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.cost_usd == 0.0, (
            f"BlockOutput.cost_usd must be 0.0 on exception-caught path, got {result.cost_usd}"
        )

    @pytest.mark.asyncio
    async def test_metadata_child_cost_matches_block_output_cost(self):
        """BlockOutput.metadata['child_cost_usd'] must match BlockOutput.cost_usd."""
        invoked_workflow = _make_mock_invoked_workflow(cost=0.03, tokens=150)
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        ctx = _make_block_context(block.block_id, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.metadata.get("child_cost_usd") == pytest.approx(result.cost_usd), (
            "metadata['child_cost_usd'] must equal BlockOutput.cost_usd"
        )


# ---------------------------------------------------------------------------
# execute_block dispatch contract
# ---------------------------------------------------------------------------


class TestExecuteBlockDispatch:
    """execute_block must dispatch WorkflowBlock through the new BlockContext path."""

    @pytest.mark.asyncio
    async def test_execute_block_calls_build_block_context_for_workflow_block(self):
        """execute_block must call build_block_context for WorkflowBlock (new dispatch path)."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        exec_ctx = _make_exec_ctx()

        with patch(
            "runsight_core.workflow.build_block_context",
            wraps=build_block_context,
        ) as mock_build_ctx:
            result_state = await execute_block(block, state, exec_ctx)

        assert mock_build_ctx.called, (
            "execute_block must call build_block_context for WorkflowBlock (new dispatch path)"
        )
        assert isinstance(result_state, WorkflowState), (
            "execute_block outer contract must still return WorkflowState"
        )

    @pytest.mark.asyncio
    async def test_execute_block_returns_workflow_state_after_workflow_block(self):
        """execute_block outer contract must still return WorkflowState for WorkflowBlock."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        exec_ctx = _make_exec_ctx()

        result_state = await execute_block(block, state, exec_ctx)

        assert isinstance(result_state, WorkflowState), (
            "execute_block must return WorkflowState (outer contract preserved)"
        )

    @pytest.mark.asyncio
    async def test_execute_block_records_block_result_in_state(self):
        """execute_block must record block_id in state.results after WorkflowBlock execution."""
        invoked_workflow = _make_mock_invoked_workflow(name="recorded_invoked_workflow")
        block = _make_workflow_block(
            block_id="record_invoked_workflow_result",
            invoked_workflow=invoked_workflow,
        )
        state = _make_base_state()
        exec_ctx = _make_exec_ctx()

        result_state = await execute_block(block, state, exec_ctx)

        assert "record_invoked_workflow_result" in result_state.results, (
            "execute_block must store block result under block_id in state.results"
        )
        assert isinstance(result_state.results["record_invoked_workflow_result"], BlockResult), (
            "state.results['record_invoked_workflow_result'] must be a BlockResult"
        )

    @pytest.mark.asyncio
    async def test_execute_block_calls_apply_block_output_for_workflow_block(self):
        """execute_block must call apply_block_output for WorkflowBlock (new path)."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        exec_ctx = _make_exec_ctx()

        apply_calls = []
        original_apply = apply_block_output

        def tracking_apply(s, block_id, output):
            apply_calls.append(block_id)
            return original_apply(s, block_id, output)

        with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
            await execute_block(block, state, exec_ctx)

        assert block.block_id in apply_calls, (
            "execute_block must call apply_block_output for WorkflowBlock (new dispatch path)"
        )

    @pytest.mark.asyncio
    async def test_execute_block_propagates_call_stack_to_workflow_block(self):
        """execute_block must pass call_stack from BlockExecutionContext to WorkflowBlock."""
        invoked_workflow = _make_mock_invoked_workflow(name="dispatch_invoked_workflow")
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        exec_ctx = _make_exec_ctx(call_stack=["root_workflow"])

        await execute_block(block, state, exec_ctx)

        call_args = invoked_workflow.run.call_args
        passed_call_stack = call_args[1].get("call_stack")
        # Child sees the extended call stack: root + parent + child.
        assert passed_call_stack is not None, (
            "WorkflowBlock must pass call_stack kwarg to child workflow.run()"
        )
        assert "dispatch_invoked_workflow" in passed_call_stack, (
            "call_stack passed to child must include child's own name"
        )

    @pytest.mark.asyncio
    async def test_execute_block_propagates_workflow_registry(self):
        """execute_block must pass workflow_registry to WorkflowBlock."""
        invoked_workflow = _make_mock_invoked_workflow()
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        mock_registry = MagicMock()
        exec_ctx = _make_exec_ctx(workflow_registry=mock_registry)

        await execute_block(block, state, exec_ctx)

        call_args = invoked_workflow.run.call_args
        passed_registry = call_args[1].get("workflow_registry")
        assert passed_registry is mock_registry, (
            "execute_block must pass workflow_registry to WorkflowBlock via BlockContext.inputs"
        )

    @pytest.mark.asyncio
    async def test_execute_block_accumulates_cost_in_state(self):
        """execute_block must accumulate child cost in the returned WorkflowState."""
        invoked_workflow = _make_mock_invoked_workflow(cost=0.12, tokens=600)
        block = _make_workflow_block(invoked_workflow=invoked_workflow)
        state = _make_base_state()
        state = state.model_copy(update={"total_cost_usd": 0.05, "total_tokens": 100})
        exec_ctx = _make_exec_ctx()

        result_state = await execute_block(block, state, exec_ctx)

        assert result_state.total_cost_usd == pytest.approx(0.17), (
            f"State total_cost_usd must be 0.05+0.12=0.17, got {result_state.total_cost_usd}"
        )
        assert result_state.total_tokens == 700, (
            f"State total_tokens must be 100+600=700, got {result_state.total_tokens}"
        )
