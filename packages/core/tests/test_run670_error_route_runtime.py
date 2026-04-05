"""Failing runtime tests for RUN-670 error_route handling in Workflow.run()."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig


class _AlwaysFailBlock(BaseBlock):
    """Block double that raises every time it executes."""

    def __init__(
        self,
        block_id: str,
        *,
        message: str,
        error_cls: type[Exception] = RuntimeError,
        retry_config: RetryConfig | None = None,
    ):
        super().__init__(block_id, retry_config=retry_config)
        self.message = message
        self.error_cls = error_cls
        self.call_count = 0

    async def execute(self, state: WorkflowState) -> WorkflowState:
        self.call_count += 1
        raise self.error_cls(self.message)


class _ControlFlowBlock(BaseBlock):
    """Block double that raises process-control exceptions unchanged."""

    def __init__(self, block_id: str, *, error: BaseException):
        super().__init__(block_id)
        self.error = error
        self.call_count = 0

    async def execute(self, state: WorkflowState) -> WorkflowState:
        self.call_count += 1
        raise self.error


class _WriteBlock(BaseBlock):
    """Block double that records its execution into results and shared memory."""

    def __init__(self, block_id: str, *, output: str | None = None):
        super().__init__(block_id)
        self.output = output or block_id
        self.call_count = 0

    async def execute(self, state: WorkflowState) -> WorkflowState:
        self.call_count += 1
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self.output),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"visited_{self.block_id}": self.call_count,
                },
            }
        )


class _ErrorAwareHandlerBlock(BaseBlock):
    """Handler block that snapshots routed error metadata for downstream assertions."""

    def __init__(self, block_id: str, *, failed_block_id: str):
        super().__init__(block_id)
        self.failed_block_id = failed_block_id
        self.call_count = 0

    async def execute(self, state: WorkflowState) -> WorkflowState:
        self.call_count += 1
        error_info = state.shared_memory.get(f"__error__{self.failed_block_id}")
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output="handled",
                        metadata={"seen_error": error_info},
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    "handler_seen_error": error_info,
                },
            }
        )


class _RecordingObserver:
    """Observer double that captures event order without depending on mocks."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.events.append(("workflow_start", workflow_name))

    def on_block_start(self, workflow_name: str, block_id: str, block_type: str, **kwargs) -> None:
        self.events.append(("block_start", block_id))

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        **kwargs,
    ) -> None:
        self.events.append(("block_complete", block_id))

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self.events.append(("block_error", block_id))

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self.events.append(("workflow_complete", workflow_name))

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.events.append(("workflow_error", workflow_name))


def _workflow_with_entry(name: str, *blocks: BaseBlock, entry: str) -> Workflow:
    wf = Workflow(name=name)
    for block in blocks:
        wf.add_block(block)
    wf.set_entry(entry)
    return wf


@pytest.mark.asyncio
class TestErrorRouteRuntimeHandling:
    """RUN-670 covers runtime error routing after block failures."""

    async def test_error_route_catches_failure_and_continues_at_handler(self):
        risky = _AlwaysFailBlock("risky", message="primary explosion")
        handler = _ErrorAwareHandlerBlock("handler", failed_block_id="risky")
        cleanup = _WriteBlock("cleanup")
        observer = _RecordingObserver()

        wf = _workflow_with_entry("error_route_runtime", risky, handler, cleanup, entry="risky")
        wf.set_error_route("risky", "handler")
        wf.add_transition("handler", "cleanup")

        final_state = await wf.run(WorkflowState(), observer=observer)

        risky_result = final_state.results["risky"]
        assert risky_result.exit_handle == "error"
        assert risky_result.metadata == {
            "error_type": "RuntimeError",
            "error_message": "primary explosion",
            "block_id": "risky",
        }
        assert final_state.shared_memory["__error__risky"] == {
            "type": "RuntimeError",
            "message": "primary explosion",
        }
        assert final_state.results["handler"].metadata == {
            "seen_error": {
                "type": "RuntimeError",
                "message": "primary explosion",
            }
        }
        assert "cleanup" in final_state.results
        assert observer.events.index(("block_error", "risky")) < observer.events.index(
            ("block_start", "handler")
        )

    async def test_block_without_error_route_still_reraises(self):
        risky = _AlwaysFailBlock("risky", message="no handler")
        observer = _RecordingObserver()
        wf = _workflow_with_entry("no_error_route", risky, entry="risky")

        with pytest.raises(RuntimeError, match="no handler"):
            await wf.run(WorkflowState(), observer=observer)

        assert ("block_error", "risky") in observer.events

    async def test_retry_exhaustion_routes_after_retries_are_spent(self):
        risky = _AlwaysFailBlock(
            "risky",
            message="retry me",
            retry_config=RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1),
        )
        handler = _ErrorAwareHandlerBlock("handler", failed_block_id="risky")

        wf = _workflow_with_entry("retry_then_route", risky, handler, entry="risky")
        wf.set_error_route("risky", "handler")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            final_state = await wf.run(WorkflowState())

        assert risky.call_count == 3
        assert final_state.results["risky"].exit_handle == "error"
        assert final_state.results["handler"].output == "handled"

    async def test_failing_handler_without_its_own_error_route_propagates(self):
        risky = _AlwaysFailBlock("risky", message="primary failure")
        handler = _AlwaysFailBlock("handler", message="handler failure")

        wf = _workflow_with_entry("handler_failure", risky, handler, entry="risky")
        wf.set_error_route("risky", "handler")

        with pytest.raises(RuntimeError, match="handler failure"):
            await wf.run(WorkflowState())

    async def test_successful_block_with_error_route_follows_normal_transition(self):
        safe = _WriteBlock("safe", output="ok")
        next_block = _WriteBlock("next", output="continued")
        handler = _WriteBlock("handler", output="should not run")

        wf = _workflow_with_entry("success_path", safe, next_block, handler, entry="safe")
        wf.set_error_route("safe", "handler")
        wf.add_transition("safe", "next")

        final_state = await wf.run(WorkflowState())

        assert final_state.results["safe"].output == "ok"
        assert final_state.results["next"].output == "continued"
        assert "handler" not in final_state.results
        assert "__error__safe" not in final_state.shared_memory

    @pytest.mark.parametrize(
        ("error", "expected_message"),
        [
            (KeyboardInterrupt("stop now"), "stop now"),
            (SystemExit("shutdown now"), "shutdown now"),
        ],
    )
    async def test_process_control_exceptions_bypass_error_route(
        self, error: BaseException, expected_message: str
    ):
        risky = _ControlFlowBlock("risky", error=error)
        handler = _WriteBlock("handler", output="should not run")

        wf = _workflow_with_entry("control_flow_bypass", risky, handler, entry="risky")
        wf.set_error_route("risky", "handler")

        with pytest.raises(type(error), match=expected_message):
            await wf.run(WorkflowState())

        assert risky.call_count == 1
