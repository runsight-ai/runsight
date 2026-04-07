"""ExecutionService — launches workflow execution as background asyncio tasks."""

import asyncio
import logging
import subprocess
import time
from typing import Any, AsyncGenerator, Dict, Optional

from runsight_core.observer import CompositeObserver, LoggingObserver
from runsight_core.runner import FallbackRoute, RunsightTeamRunner
from runsight_core.yaml.parser import parse_workflow_yaml
import yaml

from ...core.secrets import SecretsEnvLoader
from ...domain.entities.run import RunStatus
from ...domain.events import SSE_TERMINAL_EVENTS
from ..observers.eval_observer import EvalObserver
from ..observers.execution_observer import ExecutionObserver
from ..observers.streaming_observer import StreamingObserver

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
        git_service=None,
        settings_repo=None,
    ):
        self.run_repo = run_repo
        self.workflow_repo = workflow_repo
        self.provider_repo = provider_repo
        self.engine = engine
        self.secrets = secrets
        self.git_service = git_service
        self.settings_repo = settings_repo
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_runs)
        self._observers: Dict[str, StreamingObserver] = {}

    # ------------------------------------------------------------------
    # Ghost run detection
    # ------------------------------------------------------------------

    @staticmethod
    def _has_workflow_blocks(workflow_definition: Dict[str, Any]) -> bool:
        blocks = workflow_definition.get("blocks", {})
        if not isinstance(blocks, dict):
            return False
        return any(
            isinstance(block_def, dict) and block_def.get("type") == "workflow"
            for block_def in blocks.values()
        )

    def fail_ghost_runs(self) -> None:
        """Mark all runs stuck in 'running' status as failed.

        Called at server startup to clean up runs that were interrupted
        by a server restart.
        """
        ghost_runs = self.run_repo.get_by_status(RunStatus.running)
        for run in ghost_runs:
            run.status = RunStatus.failed
            run.error = "Ghost run: server restarted while running"
            self.run_repo.update(run)

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
            if event["event"] in SSE_TERMINAL_EVENTS:
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
        self, run_id: str, workflow_id: str, task_data: Dict[str, Any], branch: str = "main"
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

            workflow_path = str(self.workflow_repo._get_path(workflow_id))

            # When Git is configured, always load the workflow from the requested
            # branch snapshot instead of the working tree copy.
            if self.git_service:
                yaml_content = self.git_service.read_file(workflow_path, branch)
                commit_sha = self.git_service.get_sha(branch, workflow_path)
            else:
                yaml_content = wf_entity.yaml
                commit_sha = self._get_workflow_commit_sha(workflow_path)

            # Resolve API keys: provider repo -> env var fallback
            api_keys = self._resolve_api_keys()
            workflow_definition, runner = self._prepare_runtime_workflow(
                yaml_content=yaml_content,
                api_keys=api_keys,
            )
            workflow_registry = None
            if self._has_workflow_blocks(workflow_definition):
                workflow_registry = self.workflow_repo.build_runnable_workflow_registry(
                    workflow_id,
                    yaml_content,
                    git_ref=branch if self.git_service else None,
                    git_service=self.git_service,
                )

            # Parse workflow YAML into runnable Workflow
            wf = parse_workflow_yaml(
                yaml_content,
                workflow_registry=workflow_registry,
                api_keys=api_keys,
                runner=runner,
            )

            # Store branch + commit_sha on Run record
            self._store_branch_and_sha(run_id, branch, commit_sha)

        except Exception as e:
            logger.exception("Failed to prepare workflow for run %s", run_id)
            self._fail_run_on_prepare_error(run_id, e)
            return

        # Schedule background execution (task starts on next event-loop iteration)
        task = asyncio.create_task(self._run_workflow(run_id, wf, task_data))
        self._running_tasks[run_id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(run_id, None))

    async def _run_workflow(self, run_id: str, wf: Any, task_data: Dict[str, Any]) -> None:
        """Execute the workflow with CompositeObserver for status management.

        Acquires the concurrency semaphore before running. Status stays
        'pending' until the semaphore is acquired, then transitions to
        'running'. Terminal status (completed/failed) is written exclusively
        by ExecutionObserver via Workflow.run()'s observer callbacks.
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
                assertion_configs = self._build_assertion_configs(wf)
                observers.append(
                    EvalObserver(
                        engine=self.engine,
                        run_id=run_id,
                        sse_queue=streaming_obs.queue,
                        assertion_configs=assertion_configs,
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
            except Exception:
                logger.exception("Workflow execution failed for run %s", run_id)
            finally:
                self.unregister_observer(run_id)

        # Eagerly remove from running tasks after semaphore is released.
        # The done_callback is a safety net for cancellation paths.
        self._running_tasks.pop(run_id, None)

    @staticmethod
    def _build_assertion_configs(wf: Any) -> Optional[Dict[str, list]]:
        """Extract block-owned assertion configs from the workflow's runtime blocks.

        Returns a dict keyed by block_id mapping to a list of assertion dicts,
        or None if no assertions are defined anywhere in the workflow.
        """
        blocks = getattr(wf, "_blocks", None)
        if not blocks or not isinstance(blocks, dict):
            return None
        configs: Dict[str, list] = {}
        for block_id, block in blocks.items():
            block_assertions = getattr(block, "assertions", None)
            if block_assertions:
                configs[block_id] = list(block_assertions)
        return configs if configs else None

    def _fail_run_on_prepare_error(self, run_id: str, error: Exception) -> None:
        """Mark a run as failed when preparation fails (before task creation).

        Uses a fresh Session via self.engine when available (preferred path).
        Falls back to self.run_repo for backward compatibility when no engine
        is configured (e.g. in unit tests without a DB).
        """
        if self.engine is not None:
            try:
                from sqlmodel import Session

                from ...domain.entities.run import Run

                with Session(self.engine) as session:
                    run = session.get(Run, run_id)
                    if run:
                        run.status = RunStatus.failed
                        run.error = str(error)
                        run.completed_at = time.time()
                        session.add(run)
                        session.commit()
            except Exception:
                logger.exception("Failed to mark run %s as failed via engine session", run_id)
        else:
            try:
                run = self.run_repo.get_run(run_id)
                if run:
                    run.status = RunStatus.failed
                    run.error = str(error)
                    run.completed_at = time.time()
                    self.run_repo.update_run(run)
            except Exception:
                logger.exception("Failed to mark run %s as failed via run_repo", run_id)

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

    def _store_branch_and_sha(self, run_id: str, branch: str, commit_sha: Optional[str]) -> None:
        """Persist branch and the canonical commit SHA on the Run record."""
        if self.engine is None:
            return
        try:
            from sqlmodel import Session

            from ...domain.entities.run import Run

            with Session(self.engine) as session:
                run = session.get(Run, run_id)
                if run:
                    run.branch = branch
                    run.commit_sha = commit_sha
                    run.updated_at = time.time()
                    session.add(run)
                    session.commit()
        except Exception:
            logger.exception("Failed to store branch/commit_sha for run %s", run_id)

    def _resolve_api_keys(self) -> Dict[str, str]:
        """Resolve API keys from all providers, with env var fallback.

        Returns a Dict[str, str] mapping provider_type -> resolved API key.
        """
        import os

        result: Dict[str, str] = {}
        configured_provider_types: set[str] = set()
        disabled_provider_types: set[str] = set()

        # Collect keys from all providers
        try:
            providers = self.provider_repo.list_all()
            for provider in providers:
                provider_type = getattr(provider, "type", None)
                if not provider_type:
                    continue
                configured_provider_types.add(provider_type)
                if not getattr(provider, "is_active", True):
                    disabled_provider_types.add(provider_type)
                    continue
                if provider.api_key and self.secrets:
                    resolved = self.secrets.resolve(provider.api_key)
                    if resolved:
                        result[provider_type] = resolved
        except (TypeError, AttributeError):
            # list_all() not available or not iterable (e.g. repo not configured)
            pass

        # Env var fallback for known provider types not already in result
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        for provider_type, env_var in env_var_map.items():
            if provider_type in disabled_provider_types:
                continue
            if provider_type in configured_provider_types and provider_type not in result:
                continue
            if provider_type not in result:
                val = os.environ.get(env_var)
                if val:
                    result[provider_type] = val

        return result

    def _prepare_runtime_workflow(
        self,
        *,
        yaml_content: str,
        api_keys: Dict[str, str],
    ) -> tuple[dict[str, Any], RunsightTeamRunner | None]:
        raw = yaml.safe_load(yaml_content)
        if not isinstance(raw, dict):
            raise ValueError("Workflow YAML must parse to a mapping")

        provider_by_id: dict[str, Any] = {}
        try:
            providers = self.provider_repo.list_all()
        except (AttributeError, TypeError):
            providers = []
        if not isinstance(providers, list):
            providers = []
        provider_by_id = {
            provider.id: provider for provider in providers if getattr(provider, "is_active", True)
        }
        fallback_routes = self._fallback_routes_by_provider(provider_by_id=provider_by_id)
        souls_section = raw.get("souls")
        if not isinstance(souls_section, dict):
            souls_section = {}
            raw["souls"] = souls_section

        for soul_key, soul_data in souls_section.items():
            if not isinstance(soul_data, dict):
                continue

            provider_id = soul_data.get("provider")
            model_name = soul_data.get("model_name")

            if not isinstance(provider_id, str) or not provider_id.strip():
                raise ValueError(f"Soul '{soul_key}' must define an explicit provider")

            provider = provider_by_id.get(provider_id)
            if provider is None:
                raise ValueError(
                    f"Soul '{soul_key}' references disabled or missing provider '{provider_id}'"
                )

            if not isinstance(model_name, str) or not model_name.strip():
                raise ValueError(f"Soul '{soul_key}' must define an explicit model_name")

            if model_name not in self._provider_models(provider):
                raise ValueError(
                    f"Soul '{soul_key}' model '{model_name}' does not belong to provider '{provider_id}'"
                )

        runner_model_name = next(
            (
                soul_data.get("model_name")
                for soul_data in souls_section.values()
                if isinstance(soul_data, dict)
                and isinstance(soul_data.get("model_name"), str)
                and soul_data.get("model_name").strip()
            ),
            None,
        )
        if runner_model_name is None:
            if souls_section:
                raise ValueError(
                    "Workflow must include at least one soul with explicit provider and model_name"
                )
            return raw, None

        runner = RunsightTeamRunner(
            model_name=runner_model_name,
            api_keys=api_keys,
            fallback_routes=fallback_routes,
        )
        return raw, runner

    def _fallback_routes_by_provider(
        self, *, provider_by_id: dict[str, Any]
    ) -> dict[str, FallbackRoute]:
        if self.settings_repo is None:
            return {}
        try:
            settings_config = self.settings_repo.get_settings()
        except (AttributeError, TypeError):
            return {}
        if not getattr(settings_config, "fallback_enabled", False):
            return {}

        routes: dict[str, FallbackRoute] = {}
        try:
            fallback_map = self.settings_repo.get_fallback_map()
        except (AttributeError, TypeError):
            fallback_map = []
        if not isinstance(fallback_map, list):
            fallback_map = []
        for entry in fallback_map:
            if entry.provider_id not in provider_by_id:
                continue
            target_provider = provider_by_id.get(entry.fallback_provider_id)
            if target_provider is None:
                continue
            if entry.fallback_model_id not in self._provider_models(target_provider):
                continue
            routes[entry.provider_id] = FallbackRoute(
                source_provider_id=entry.provider_id,
                target_provider_id=entry.fallback_provider_id,
                target_model_name=entry.fallback_model_id,
            )
        return routes

    @staticmethod
    def _provider_models(provider: Any) -> list[str]:
        models = getattr(provider, "models", None)
        if isinstance(models, list):
            return [str(model) for model in models]
        return []
