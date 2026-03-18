"""ExecutionService — launches workflow execution as background asyncio tasks."""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

from runsight_core.observer import CompositeObserver, LoggingObserver
from runsight_core.yaml.parser import parse_workflow_yaml

from ...core.encryption import decrypt
from ...domain.entities.run import RunStatus
from ..observers.execution_observer import ExecutionObserver
from ..observers.streaming_observer import StreamingObserver

logger = logging.getLogger(__name__)


class ExecutionService:
    """Wires POST /runs to workflow.run() with background execution."""

    def __init__(
        self, run_repo, workflow_repo, provider_repo, engine=None, max_concurrent_runs: int = 5
    ):
        self.run_repo = run_repo
        self.workflow_repo = workflow_repo
        self.provider_repo = provider_repo
        self.engine = engine
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_runs)
        self._observers: Dict[str, StreamingObserver] = {}

    # ------------------------------------------------------------------
    # Observer registry
    # ------------------------------------------------------------------

    def register_observer(self, run_id: str, observer: StreamingObserver) -> None:
        """Register a StreamingObserver for a given run_id."""
        self._observers[run_id] = observer

    def get_observer(self, run_id: str) -> Optional[StreamingObserver]:
        """Return the observer for run_id, or None."""
        return self._observers.get(run_id)

    def unregister_observer(self, run_id: str) -> None:
        """Remove the observer for run_id."""
        self._observers.pop(run_id, None)

    async def subscribe_stream(self, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Async generator that yields events from the observer's queue until done."""
        observer = self._observers.get(run_id)
        if observer is None:
            return

        while True:
            try:
                event = await asyncio.wait_for(observer.queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive or just continue
                continue

            yield event

            # Terminal events end the stream
            if event["event"] in ("run_completed", "run_failed"):
                break

    async def launch_execution(
        self, run_id: str, workflow_id: str, task_data: Dict[str, Any]
    ) -> None:
        """Launch workflow execution as a background asyncio task.

        Parses the workflow synchronously (so patches/mocks are active),
        then schedules the actual run as a background asyncio task.
        """
        try:
            # Validate instruction
            if "instruction" not in task_data:
                raise ValueError("task_data missing required 'instruction' key")

            # Load workflow entity
            wf_entity = self.workflow_repo.get_by_id(workflow_id)
            if wf_entity is None:
                raise ValueError(f"Workflow {workflow_id} not found")

            yaml_content = wf_entity.yaml

            # Resolve API keys: provider DB -> env var fallback
            api_keys = self._resolve_api_keys()

            # Parse workflow YAML into runnable Workflow
            wf = parse_workflow_yaml(yaml_content, api_keys=api_keys)

        except Exception as e:
            logger.exception("Failed to prepare workflow for run %s", run_id)
            run = self.run_repo.get_run(run_id)
            if run:
                run.status = RunStatus.failed
                run.error = str(e)
                run.completed_at = time.time()
                self.run_repo.update_run(run)
            return

        # Schedule background execution (task starts on next event-loop iteration)
        task = asyncio.create_task(self._run_workflow(run_id, wf, task_data))
        self._running_tasks[run_id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(run_id, None))

    async def _run_workflow(self, run_id: str, wf: Any, task_data: Dict[str, Any]) -> None:
        """Execute the workflow with CompositeObserver for status management.

        Acquires the concurrency semaphore before running. Status stays
        'pending' until the semaphore is acquired, then transitions to
        'running'. The semaphore is released in a finally block to prevent
        deadlocks on errors or cancellation.
        """
        from runsight_core.state import WorkflowState

        async with self._semaphore:
            # Transition status from pending -> running now that we have a slot
            self._set_run_status(run_id, RunStatus.running)

            # Build observer chain: LoggingObserver + ExecutionObserver (DB persistence)
            observers = [LoggingObserver()]
            if self.engine:
                observers.append(ExecutionObserver(engine=self.engine, run_id=run_id))
            observer = CompositeObserver(*observers)

            start_time = time.time()
            state = WorkflowState()
            observer.on_workflow_start("workflow", state)

            try:
                state = await wf.run(task_data["instruction"], observer=observer)
                duration = time.time() - start_time
                observer.on_workflow_complete("workflow", state, duration)
            except Exception as e:
                duration = time.time() - start_time
                observer.on_workflow_error("workflow", e, duration)
                logger.exception("Workflow execution failed for run %s", run_id)

        # Eagerly remove from running tasks after semaphore is released.
        # The done_callback is a safety net for cancellation paths.
        self._running_tasks.pop(run_id, None)

    def _set_run_status(self, run_id: str, status: RunStatus) -> None:
        """Update the run status in the database if an engine is available."""
        if self.engine is None:
            return
        try:
            from sqlmodel import Session

            from ...domain.entities.run import Run

            with Session(self.engine) as session:
                run = session.get(Run, run_id)
                if run:
                    run.status = status
                    run.updated_at = time.time()
                    session.add(run)
                    session.commit()
        except Exception:
            logger.exception("Failed to update run %s status to %s", run_id, status)

    def _resolve_api_keys(self) -> Dict[str, str]:
        """Resolve API keys from all providers in DB, with env var fallback.

        Returns a Dict[str, str] mapping provider_type -> decrypted API key.
        """
        import os

        result: Dict[str, str] = {}

        # Collect keys from all DB providers
        try:
            providers = self.provider_repo.list_all()
            for provider in providers:
                if provider.api_key_encrypted:
                    result[provider.type] = decrypt(provider.api_key_encrypted)
        except (TypeError, AttributeError):
            # list_all() not available or not iterable (e.g. repo not configured)
            pass

        # Env var fallback for known provider types not already in result
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        for provider_type, env_var in env_var_map.items():
            if provider_type not in result:
                val = os.environ.get(env_var)
                if val:
                    result[provider_type] = val

        return result

    def _resolve_api_key(self) -> str | None:
        """Resolve API key from provider DB or environment."""
        import os

        # Try provider DB first
        for provider_type in ("openai", "anthropic"):
            provider = self.provider_repo.get_by_type(provider_type)
            if provider and provider.api_key_encrypted:
                return decrypt(provider.api_key_encrypted)

        # Fallback to env vars
        for env_var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            val = os.environ.get(env_var)
            if val:
                return val

        return None
