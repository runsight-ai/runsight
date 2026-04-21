"""ExecutionService facade for execution collaborators."""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

from runsight_core.identity import EntityKind, EntityRef
from runsight_core.yaml.parser import parse_workflow_yaml

from ...core.secrets import SecretsEnvLoader
from ...domain.entities.run import RunStatus
from ..observers.streaming_observer import StreamingObserver
from .execution_persistence import ExecutionRunStore
from .execution_preparation import (
    ExecutionPreparationService,
    get_workflow_commit_sha,
    has_workflow_blocks,
)
from .execution_runtime import ExecutionRuntimeCoordinator, build_assertion_configs
from .execution_stream_registry import ExecutionStreamRegistry

logger = logging.getLogger(__name__)


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


def _provider_ref(provider_id: str) -> str:
    return str(EntityRef(EntityKind.PROVIDER, provider_id))


class ExecutionService:
    """Public execution facade with explicit internal collaborators."""

    _OBSERVER_REGISTRATION_TIMEOUT_S = ExecutionStreamRegistry.OBSERVER_REGISTRATION_TIMEOUT_S
    _STREAM_CLOSED_EVENT = ExecutionStreamRegistry.STREAM_CLOSED_EVENT

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

        self._run_store = ExecutionRunStore(run_repo=run_repo, engine=engine)
        self._streams = ExecutionStreamRegistry()
        self._preparation = ExecutionPreparationService(
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            git_service=git_service,
            secrets=secrets,
            settings_repo=settings_repo,
        )
        self._runtime = ExecutionRuntimeCoordinator(
            engine=engine,
            persistence=self._run_store,
            streams=self._streams,
            max_concurrent_runs=max_concurrent_runs,
        )

        # Compatibility aliases used directly by existing tests and call sites.
        self._running_tasks = self._runtime.running_tasks
        self._semaphore = self._runtime.semaphore

    @staticmethod
    def _has_workflow_blocks(workflow_definition: Dict[str, Any]) -> bool:
        return has_workflow_blocks(workflow_definition)

    def fail_ghost_runs(self) -> None:
        self._run_store.fail_ghost_runs()

    def cancel_execution(self, run_id: str) -> bool:
        return self._runtime.cancel(run_id)

    def register_observer(self, run_id: str, observer: StreamingObserver) -> None:
        self._streams.register(run_id, observer)

    def get_observer(self, run_id: str) -> Optional[StreamingObserver]:
        return self._streams.get(run_id)

    def unregister_observer(self, run_id: str) -> None:
        self._streams.unregister(run_id)

    async def subscribe_stream(self, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._streams.subscribe(run_id):
            yield event

    @staticmethod
    def _get_workflow_commit_sha(workflow_path: str) -> Optional[str]:
        return get_workflow_commit_sha(workflow_path)

    async def launch_execution(
        self, run_id: str, workflow_id: str, inputs: Dict[str, Any], branch: str = "main"
    ) -> None:
        """Prepare a workflow snapshot, then schedule background execution."""
        try:
            prepared = self._preparation.prepare_for_launch(
                workflow_id=workflow_id,
                branch=branch,
                parser=parse_workflow_yaml,
                prepare_runtime_workflow=self._prepare_runtime_workflow,
                get_workflow_commit_sha=self._get_workflow_commit_sha,
            )
            self._store_branch_and_sha(run_id, branch, prepared.commit_sha)
            if self._is_run_cancelled(run_id):
                logger.info(
                    "Run %s was cancelled during prepare; skipping execution launch", run_id
                )
                return
        except Exception as e:
            logger.exception("Failed to prepare workflow for run %s", run_id)
            self._fail_run_on_prepare_error(run_id, e)
            return

        self._runtime.track_background_task(
            run_id, self._run_workflow(run_id, prepared.workflow, inputs)
        )

    async def _run_workflow(self, run_id: str, wf: Any, inputs: Dict[str, Any]) -> None:
        await self._runtime.run_workflow(run_id, wf, inputs)

    @staticmethod
    def _build_assertion_configs(wf: Any) -> Optional[Dict[str, list]]:
        return build_assertion_configs(wf)

    def _fail_run_on_prepare_error(self, run_id: str, error: Exception) -> None:
        self._run_store.fail_prepare(run_id, error)

    def _set_run_status(
        self, run_id: str, status: RunStatus, *, error: Optional[Exception] = None
    ) -> None:
        self._run_store.set_status(run_id, status, error=error)

    def _store_branch_and_sha(self, run_id: str, branch: str, commit_sha: Optional[str]) -> None:
        self._run_store.store_branch_and_sha(run_id, branch, commit_sha)

    def _is_run_cancelled(self, run_id: str) -> bool:
        return self._run_store.is_run_cancelled(run_id)

    def _resolve_api_keys(self) -> Dict[str, str]:
        return self._preparation.resolve_api_keys()

    def _prepare_runtime_workflow(
        self,
        *,
        yaml_content: str,
        api_keys: Dict[str, str],
    ):
        return self._preparation.prepare_runtime_workflow(
            yaml_content=yaml_content,
            api_keys=api_keys,
        )
