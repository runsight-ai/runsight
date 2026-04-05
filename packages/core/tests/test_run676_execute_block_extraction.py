"""Red tests for RUN-676: extract module-level execute_block()."""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, Workflow
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RetryConfig

workflow_module = importlib.import_module("runsight_core.workflow")


class RecordingObserver:
    def __init__(self) -> None:
        self.events = []

    def on_block_start(self, workflow_name, block_id, block_type, **kwargs) -> None:
        self.events.append(("start", workflow_name, block_id, block_type, kwargs))

    def on_block_complete(
        self, workflow_name, block_id, block_type, duration_s, state, **kwargs
    ) -> None:
        self.events.append(("complete", workflow_name, block_id, block_type, state, kwargs))

    def on_block_error(self, workflow_name, block_id, block_type, duration_s, error) -> None:
        self.events.append(("error", workflow_name, block_id, block_type, error))


class RetryProbeBlock(BaseBlock):
    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state


def _require_execute_block():
    execute_block = getattr(workflow_module, "execute_block", None)
    if execute_block is None:
        pytest.fail(
            "RUN-676 requires module-level execute_block(block, state, ctx) in runsight_core.workflow"
        )
    return execute_block


def _make_linear_block(block_id: str = "linear_block") -> LinearBlock:
    soul = Soul(id="soul_1", role="Analyst", system_prompt="Analyze the task.")
    runner = MagicMock()
    runner.model_name = "gpt-4o-mini"
    return LinearBlock(block_id, soul, runner)


def _make_ctx(
    *,
    workflow_name: str = "parent_workflow",
    blocks=None,
    call_stack=None,
    workflow_registry=None,
    observer=None,
) -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name=workflow_name,
        blocks=blocks or {},
        call_stack=call_stack or ["root_workflow"],
        workflow_registry=workflow_registry,
        observer=observer,
    )


class TestExecuteBlockDispatch:
    @pytest.mark.asyncio
    async def test_linear_block_path_fires_observer_and_calls_execute_with_plain_state(self):
        execute_block = _require_execute_block()
        observer = RecordingObserver()
        block = _make_linear_block()
        initial_state = WorkflowState()
        final_state = initial_state.model_copy(
            update={"results": {block.block_id: BlockResult(output="linear ok")}}
        )
        block.execute = AsyncMock(return_value=final_state)
        ctx = _make_ctx(observer=observer)

        result = await execute_block(block, initial_state, ctx)

        assert result is final_state
        block.execute.assert_awaited_once_with(initial_state)
        assert [event[0] for event in observer.events] == ["start", "complete"]

    @pytest.mark.asyncio
    async def test_workflow_block_path_receives_call_stack_registry_and_observer(self):
        execute_block = _require_execute_block()
        observer = RecordingObserver()
        registry = WorkflowRegistry(allow_filesystem_fallback=False)
        child_workflow = Workflow("child_workflow")
        block = WorkflowBlock(
            block_id="workflow_block",
            child_workflow=child_workflow,
            inputs={},
            outputs={},
        )
        initial_state = WorkflowState()
        final_state = initial_state.model_copy(
            update={"results": {block.block_id: BlockResult(output="workflow ok")}}
        )
        block.execute = AsyncMock(return_value=final_state)
        ctx = _make_ctx(
            workflow_name="parent_workflow",
            call_stack=["grandparent_workflow"],
            workflow_registry=registry,
            observer=observer,
        )

        result = await execute_block(block, initial_state, ctx)

        assert result is final_state
        block.execute.assert_awaited_once()
        assert block.execute.await_args.args == (initial_state,)
        assert block.execute.await_args.kwargs["call_stack"] == [
            "grandparent_workflow",
            "parent_workflow",
        ]
        assert block.execute.await_args.kwargs["workflow_registry"] is registry
        assert block.execute.await_args.kwargs["observer"] is observer

    @pytest.mark.asyncio
    async def test_loop_block_path_receives_blocks_call_stack_registry_observer_and_ctx(self):
        execute_block = _require_execute_block()
        observer = RecordingObserver()
        registry = WorkflowRegistry(allow_filesystem_fallback=False)
        block = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["leaf_block"],
            max_rounds=1,
        )
        leaf = RetryProbeBlock("leaf_block")
        blocks = {block.block_id: block, leaf.block_id: leaf}
        initial_state = WorkflowState()
        final_state = initial_state.model_copy(
            update={"results": {block.block_id: BlockResult(output="loop ok")}}
        )
        block.execute = AsyncMock(return_value=final_state)
        ctx = _make_ctx(
            workflow_name="parent_workflow",
            blocks=blocks,
            call_stack=["root_workflow"],
            workflow_registry=registry,
            observer=observer,
        )

        result = await execute_block(block, initial_state, ctx)

        assert result is final_state
        block.execute.assert_awaited_once()
        assert block.execute.await_args.args == (initial_state,)
        assert block.execute.await_args.kwargs["blocks"] is blocks
        assert block.execute.await_args.kwargs["call_stack"] == [
            "root_workflow",
            "parent_workflow",
        ]
        assert block.execute.await_args.kwargs["workflow_registry"] is registry
        assert block.execute.await_args.kwargs["observer"] is observer
        assert block.execute.await_args.kwargs["ctx"] is ctx


class TestRetryHelpers:
    @pytest.mark.asyncio
    async def test_execute_block_retry_config_retries_three_times_and_completes_once(self):
        execute_block = _require_execute_block()
        observer = RecordingObserver()
        block = _make_linear_block("retrying_linear_block")
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)
        initial_state = WorkflowState()
        final_state = initial_state.model_copy(
            update={"results": {block.block_id: BlockResult(output="eventual success")}}
        )
        block.execute = AsyncMock(
            side_effect=[
                RuntimeError("fail attempt 1"),
                RuntimeError("fail attempt 2"),
                final_state,
            ]
        )
        ctx = _make_ctx(observer=observer)

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            result = await execute_block(block, initial_state, ctx)

        assert result is final_state
        assert block.execute.await_count == 3
        assert [event[0] for event in observer.events] == ["start", "complete"]
        assert sleep_mock.await_count == 2


class TestExecuteBlockErrors:
    @pytest.mark.asyncio
    async def test_error_path_fires_on_block_error_and_reraises(self):
        execute_block = _require_execute_block()
        observer = RecordingObserver()
        block = _make_linear_block("failing_linear_block")
        initial_state = WorkflowState()
        block.execute = AsyncMock(side_effect=RuntimeError("boom"))
        ctx = _make_ctx(observer=observer)

        with pytest.raises(RuntimeError, match="boom"):
            await execute_block(block, initial_state, ctx)

        assert block.execute.await_count == 1
        assert [event[0] for event in observer.events] == ["start", "error"]
        assert str(observer.events[-1][-1]) == "boom"

    @pytest.mark.asyncio
    async def test_observer_none_path_executes_normally(self):
        execute_block = _require_execute_block()
        block = _make_linear_block("headless_linear_block")
        initial_state = WorkflowState()
        final_state = initial_state.model_copy(
            update={"results": {block.block_id: BlockResult(output="headless success")}}
        )
        block.execute = AsyncMock(return_value=final_state)
        ctx = _make_ctx(observer=None)

        result = await execute_block(block, initial_state, ctx)

        assert result is final_state
        block.execute.assert_awaited_once_with(initial_state)
