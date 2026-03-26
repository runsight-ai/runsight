"""ExecutionService — launches workflow execution as background asyncio tasks."""

import asyncio
import logging
import subprocess
import time
from typing import Any, AsyncGenerator, Dict, Optional

from runsight_core.observer import CompositeObserver, LoggingObserver
from runsight_core.yaml.parser import parse_workflow_yaml

from ...core.secrets import SecretsEnvLoader
from ...domain.entities.run import RunStatus
from ..observers.eval_observer import EvalObserver
from ..observers.execution_observer import ExecutionObserver
from ..observers.streaming_observer import StreamingObserver

# Legacy stub — kept so negative-assertion tests can patch it to verify it's never called
decrypt = None

logger = logging.getLogger(__name__)


class ExecutionService:
    """Wires POST /runs to workflow.run() with background execution."""

    def __init__(
        self,
        run_repo,
        workflow_repo,
        provider_repo,
        engine=None,
        max_concurrent_runs: int = 5,
        secrets: SecretsEnvLoader | None = None,
    ):
        self.run_repo = run_repo
        self.workflow_repo = workflow_repo
        self.provider_repo = provider_repo
        self.engine = engine
        self.secrets = secrets
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_runs)
        self._observers: Dict[str, StreamingObserver] = {}

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel_execution(self, run_id: str) -> bool:
        """Cancel the asyncio task for a given run_id.

        Returns True if the task was found and cancel() was called,
        False if no task was found (already finished or never existed).
        """
        task = self._running_tasks.get(run_id)
        if task is None:
            return False
        task.cancel()
        return True

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

    # ------------------------------------------------------------------
    # Git SHA capture
    # ------------------------------------------------------------------

    @staticmethod
    def _get_workflow_commit_sha(workflow_path: str) -> Optional[str]:
        """Return the latest git commit SHA that touched *workflow_path*.

        Runs ``git log -1 --format=%H -- <path>`` and returns the 40-char
        hex SHA.  Returns ``None`` gracefully when:
        - the file is not inside a git repository
        - git is not installed
        - the file has never been committed (untracked)
        - any other unexpected error occurs
        """
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%H", "--", workflow_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None
            sha = result.stdout.strip()
            return sha if sha else None
        except Exception:
            return None

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

            # Resolve API keys: provider repo -> env var fallback
            api_keys = self._resolve_api_keys()

            # Parse workflow YAML into runnable Workflow
            wf = parse_workflow_yaml(yaml_content, api_keys=api_keys)

            # Capture the latest git commit SHA for this workflow file
            workflow_path = str(self.workflow_repo._get_path(workflow_id))
            commit_sha = self._get_workflow_commit_sha(workflow_path)
            self._store_workflow_commit_sha(run_id, commit_sha)

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
        'running'. Workflow.run() is the single source of observer events;
        this method does not call observer methods directly.
        """
        from runsight_core.primitives import Task
        from runsight_core.state import WorkflowState

        async with self._semaphore:
            # Transition status from pending -> running now that we have a slot
            self._set_run_status(run_id, RunStatus.running)

            # Build observer chain: LoggingObserver + ExecutionObserver (DB persistence)
            # + StreamingObserver (SSE event streaming)
            streaming_obs = StreamingObserver(run_id=run_id)
            self.register_observer(run_id, streaming_obs)

            observers = [LoggingObserver(), streaming_obs]
            if self.engine:
                observers.append(ExecutionObserver(engine=self.engine, run_id=run_id))
                observers.append(
                    EvalObserver(
                        engine=self.engine,
                        run_id=run_id,
                        sse_queue=streaming_obs.queue,
                        assertion_configs=None,
                    )
                )
            observer = CompositeObserver(*observers)

            from runsight_core.artifacts import InMemoryArtifactStore

            artifact_store = InMemoryArtifactStore(run_id=run_id)
            state = WorkflowState(
                current_task=Task(id=run_id, instruction=task_data["instruction"]),
                artifact_store=artifact_store,
            )

            try:
                state = await wf.run(state, observer=observer)
                self._set_run_status(run_id, RunStatus.completed)
            except Exception as e:
                self._set_run_status(run_id, RunStatus.failed, error=e)
                logger.exception("Workflow execution failed for run %s", run_id)
            finally:
                self.unregister_observer(run_id)

        # Eagerly remove from running tasks after semaphore is released.
        # The done_callback is a safety net for cancellation paths.
        self._running_tasks.pop(run_id, None)

    def _set_run_status(
        self, run_id: str, status: RunStatus, *, error: Optional[Exception] = None
    ) -> None:
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
                    if error is not None:
                        run.error = str(error)
                    session.add(run)
                    session.commit()
        except Exception:
            logger.exception("Failed to update run %s status to %s", run_id, status)

    def _store_workflow_commit_sha(self, run_id: str, commit_sha: Optional[str]) -> None:
        """Persist the workflow commit SHA on the Run record."""
        if self.engine is None:
            return
        try:
            from sqlmodel import Session

            from ...domain.entities.run import Run

            with Session(self.engine) as session:
                run = session.get(Run, run_id)
                if run:
                    run.workflow_commit_sha = commit_sha
                    run.updated_at = time.time()
                    session.add(run)
                    session.commit()
        except Exception:
            logger.exception("Failed to store workflow_commit_sha for run %s", run_id)

    def _resolve_api_keys(self) -> Dict[str, str]:
        """Resolve API keys from all providers, with env var fallback.

        Returns a Dict[str, str] mapping provider_type -> resolved API key.
        """
        import os

        result: Dict[str, str] = {}

        # Collect keys from all providers
        try:
            providers = self.provider_repo.list_all()
            for provider in providers:
                if provider.api_key and self.secrets:
                    resolved = self.secrets.resolve(provider.api_key)
                    if resolved:
                        result[provider.type] = resolved
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

        return None
