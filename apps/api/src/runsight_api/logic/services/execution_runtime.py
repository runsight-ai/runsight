"""Runtime coordinator for scheduled workflow execution."""

import asyncio
import logging
import traceback
from collections.abc import Mapping
from typing import Any, Dict, Optional

from runsight_core.observer import CompositeObserver, LoggingObserver

from ...domain.entities.run import RunStatus
from ..observers.eval_observer import EvalObserver
from ..observers.execution_observer import ExecutionObserver
from ..observers.streaming_observer import StreamingObserver

logger = logging.getLogger(__name__)


def _split_runtime_inputs(inputs: Any) -> tuple[dict[str, Any], Any | None]:
    normalized_inputs = getattr(inputs, "normalized_inputs", None)
    if isinstance(normalized_inputs, Mapping):
        return dict(normalized_inputs), getattr(inputs, "input_redactor", None)
    if isinstance(inputs, Mapping):
        return dict(inputs), None
    raise TypeError("Workflow launch inputs must be a mapping or PreparedRunInputs")


def build_assertion_configs(wf: Any) -> Optional[Dict[str, list]]:
    """Extract block-owned assertion configs from runtime blocks."""
    getter = getattr(wf, "assertion_configs", None)
    if callable(getter):
        return getter()
    blocks = getattr(wf, "_blocks", None)
    if not blocks or not isinstance(blocks, dict):
        return None
    configs: Dict[str, list] = {}
    for block_id, block in blocks.items():
        block_assertions = getattr(block, "assertions", None)
        if block_assertions:
            configs[block_id] = list(block_assertions)
    return configs if configs else None


class ExecutionRuntimeCoordinator:
    """Owns running-task tracking and workflow execution coordination."""

    def __init__(self, *, engine=None, persistence, streams, max_concurrent_runs: int = 5):
        self.engine = engine
        self.persistence = persistence
        self.streams = streams
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent_runs)

    def track_background_task(self, run_id: str, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self.running_tasks[run_id] = task
        task.add_done_callback(lambda t: self.running_tasks.pop(run_id, None))

    def cancel(self, run_id: str) -> bool:
        task = self.running_tasks.get(run_id)
        if task is None:
            return False
        task.cancel()
        return True

    async def run_workflow(self, run_id: str, wf: Any, inputs: Any) -> None:
        """Execute a prepared workflow under concurrency and stream coordination."""
        from runsight_core.state import WorkflowState

        streaming_obs = StreamingObserver(
            run_id=run_id,
            register_stream=self.streams.register,
            unregister_stream=self.streams.unregister,
        )
        self.streams.register(run_id, streaming_obs)

        try:
            normalized_inputs, input_redactor = _split_runtime_inputs(inputs)
            try:
                async with self.semaphore:
                    if self.persistence.is_run_cancelled(run_id):
                        self.streams.close_stream(run_id, observer=streaming_obs)
                        return

                    if not self.persistence.set_status(run_id, RunStatus.running):
                        self.streams.close_stream(run_id, observer=streaming_obs)
                        return

                    observers = [LoggingObserver(), streaming_obs]
                    if self.engine:
                        observers.append(ExecutionObserver(engine=self.engine, run_id=run_id))
                        observers.append(
                            EvalObserver(
                                engine=self.engine,
                                run_id=run_id,
                                sse_queue=streaming_obs.queue,
                                assertion_configs=build_assertion_configs(wf),
                                child_sse_queue_factory=streaming_obs.child_queue_for_run,
                            )
                        )
                    observer = CompositeObserver(*observers)

                    from runsight_core.artifacts import InMemoryArtifactStore

                    artifact_store = InMemoryArtifactStore(run_id=run_id)
                    state = WorkflowState(
                        artifact_store=artifact_store,
                        input_redactor=input_redactor,
                    )

                    try:
                        await wf.run(
                            state,
                            observer=observer,
                            inputs=normalized_inputs,
                        )
                    except Exception as exc:
                        if input_redactor is None:
                            logger.exception("Workflow execution failed for run %s", run_id)
                        else:
                            tb_str = "".join(
                                traceback.format_exception(type(exc), exc, exc.__traceback__)
                            )
                            logger.error(
                                "Workflow execution failed for run %s\n%s",
                                run_id,
                                input_redactor.redact_text(tb_str),
                            )
                        self.streams.close_stream(run_id, observer=streaming_obs)
            except asyncio.CancelledError:
                self.streams.close_stream(run_id, observer=streaming_obs)
                raise
        finally:
            self.streams.unregister(run_id)
            self.running_tasks.pop(run_id, None)
