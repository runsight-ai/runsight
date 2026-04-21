"""ExecutionService — launches workflow execution as background asyncio tasks."""

import asyncio
import copy
import logging
import subprocess
import time
import traceback
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional

from runsight_core.identity import EntityKind, EntityRef
from runsight_core.observer import CompositeObserver, LoggingObserver
from runsight_core.redaction import RunRedactor
from runsight_core.runner import FallbackRoute, RunsightTeamRunner
from runsight_core.workflow_input_schema import effective_workflow_input_schema
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile, WorkflowInputDef
from pydantic import ValidationError
import yaml

from ...core.secrets import SecretsEnvLoader
from ...domain.errors import ServiceUnavailable
from ...domain.entities.run import RunStatus
from ...domain.errors import InputValidationError, WorkflowNotFound
from ...domain.events import SSE_TERMINAL_EVENTS
from ..observers.eval_observer import EvalObserver
from ..observers.execution_observer import ExecutionObserver
from ..observers.streaming_observer import StreamingObserver

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedRunInputs(Mapping[str, Any]):
    normalized_inputs: Dict[str, Any]
    input_redactor: RunRedactor
    workflow_inputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    workflow_input_schema: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.normalized_inputs[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.normalized_inputs)

    def __len__(self) -> int:
        return len(self.normalized_inputs)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PreparedRunInputs):
            return (
                self.normalized_inputs == other.normalized_inputs
                and self.input_redactor is other.input_redactor
            )
        if isinstance(other, Mapping):
            return self.normalized_inputs == dict(other)
        return False


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


def _provider_ref(provider_id: str) -> str:
    return str(EntityRef(EntityKind.PROVIDER, provider_id))


def _actual_input_type(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "json"
    return type(value).__name__


def _matches_input_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return not isinstance(value, bool) and isinstance(value, int | float)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "json":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    return False


def _type_label(input_def: WorkflowInputDef) -> str:
    article = "an" if input_def.type == "array" else "a"
    return f"{article} {input_def.type}"


def _workflow_input_field_error(
    field: str,
    code: str,
    message: str,
    *,
    expected_type: str | None,
    actual_type: str | None,
) -> dict[str, Any]:
    return {
        "field": field,
        "code": code,
        "message": message,
        "input_path": ["inputs", field],
        "expected_type": expected_type,
        "actual_type": actual_type,
    }


def _raise_workflow_input_validation(workflow_id: str, fields: list[dict[str, Any]]) -> None:
    raise InputValidationError(
        "Workflow input validation failed",
        error_code="WORKFLOW_INPUT_VALIDATION_ERROR",
        status_code=422,
        details={
            "kind": "workflow_input_validation",
            "workflow_id": workflow_id,
            "fields": fields,
        },
    )


def _workflow_schema_error_field(error: Exception) -> dict[str, Any]:
    message = "Workflow input schema is invalid."
    code = "invalid"
    if isinstance(error, ValueError) and str(error) == "legacy workflow interface is unsupported":
        message = str(error)
        code = "unsupported"
    elif isinstance(error, ValidationError):
        for item in error.errors():
            context_error = item.get("ctx", {}).get("error")
            if (
                isinstance(context_error, ValueError)
                and str(context_error) == "legacy workflow interface is unsupported"
            ):
                message = str(context_error)
                code = "unsupported"
                break

    return {
        "field": "__schema__",
        "code": code,
        "message": message,
        "input_path": ["inputs"],
        "expected_type": None,
        "actual_type": None,
    }


def _raise_workflow_schema_validation(workflow_id: str, error: Exception) -> None:
    raise InputValidationError(
        "Workflow input validation failed",
        error_code="WORKFLOW_INPUT_VALIDATION_ERROR",
        status_code=422,
        details={
            "kind": "workflow_input_validation",
            "workflow_id": workflow_id,
            "fields": [_workflow_schema_error_field(error)],
        },
    ) from error


def _prepared_run_inputs(
    input_schema: Mapping[str, WorkflowInputDef],
    normalized_inputs: Dict[str, Any],
    sources: Mapping[str, str] | None = None,
) -> PreparedRunInputs:
    input_redactor = RunRedactor()
    for name, input_def in input_schema.items():
        if input_def.sensitive and name in normalized_inputs:
            input_redactor.register_named(name, normalized_inputs[name])
    return PreparedRunInputs(
        normalized_inputs=normalized_inputs,
        input_redactor=input_redactor,
        workflow_inputs=_workflow_input_values_snapshot(
            input_schema,
            normalized_inputs,
            sources,
            redactor=input_redactor,
        ),
        workflow_input_schema=_workflow_input_schema_snapshot(input_schema),
    )


def _workflow_input_schema_snapshot(
    input_schema: Mapping[str, WorkflowInputDef],
) -> Dict[str, Dict[str, Any]]:
    return {
        name: {
            "type": input_def.type,
            "required": input_def.required,
            "default": copy.deepcopy(input_def.default),
            "description": input_def.description,
            "sensitive": input_def.sensitive,
        }
        for name, input_def in input_schema.items()
    }


def _workflow_input_source(
    name: str,
    value: Any,
    input_def: WorkflowInputDef,
    sources: Mapping[str, str] | None,
) -> str:
    if sources is not None and name in sources:
        return sources[name]
    if input_def.default is not None and value == input_def.default:
        return "defaulted"
    return "provided"


def _redactor_marks_runtime_value_sensitive(redactor: RunRedactor, value: Any) -> bool:
    return redactor.contains_runtime_sensitive_value(value)


def _workflow_input_values_snapshot(
    input_schema: Mapping[str, WorkflowInputDef],
    normalized_inputs: Mapping[str, Any],
    sources: Mapping[str, str] | None = None,
    *,
    redactor: RunRedactor | None = None,
) -> Dict[str, Dict[str, Any]]:
    snapshot: Dict[str, Dict[str, Any]] = {}
    for name, input_def in input_schema.items():
        if name not in normalized_inputs:
            continue

        value = normalized_inputs[name]
        runtime_sensitive = False
        if redactor is not None:
            runtime_sensitive = _redactor_marks_runtime_value_sensitive(redactor, value)
        sensitive = input_def.sensitive or runtime_sensitive
        item: Dict[str, Any] = {
            "type": input_def.type,
            "sensitive": sensitive,
            "source": _workflow_input_source(name, value, input_def, sources),
        }
        if not sensitive:
            item["value"] = copy.deepcopy(value)
        snapshot[name] = item
    return snapshot


def workflow_input_snapshots_from_yaml(
    workflow_id: str,
    yaml_content: str,
    normalized_inputs: Mapping[str, Any],
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    input_schema = _workflow_input_schema_from_yaml(workflow_id, yaml_content)
    return (
        _workflow_input_values_snapshot(input_schema, normalized_inputs),
        _workflow_input_schema_snapshot(input_schema),
    )


def _workflow_input_schema_from_yaml(
    workflow_id: str,
    yaml_content: str,
) -> Mapping[str, WorkflowInputDef]:
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        _raise_workflow_schema_validation(workflow_id, exc)
    if not isinstance(data, dict):
        _raise_workflow_schema_validation(workflow_id, ValueError("YAML content is not a mapping"))
    try:
        workflow_file = RunsightWorkflowFile.model_validate(data)
    except ValidationError as exc:
        _raise_workflow_schema_validation(workflow_id, exc)
    try:
        return effective_workflow_input_schema(workflow_file) or {}
    except ValueError as exc:
        _raise_workflow_schema_validation(workflow_id, exc)


def _prepare_run_inputs_from_schema(
    workflow_id: str,
    input_schema: Mapping[str, WorkflowInputDef],
    inputs: Mapping[str, Any],
) -> PreparedRunInputs:
    raw_inputs = dict(inputs or {})

    fields: list[dict[str, Any]] = []
    normalized: Dict[str, Any] = {}
    sources: Dict[str, str] = {}

    for name, value in raw_inputs.items():
        if name not in input_schema:
            fields.append(
                _workflow_input_field_error(
                    name,
                    "unknown",
                    f"Input '{name}' is not declared by this workflow.",
                    expected_type=None,
                    actual_type=_actual_input_type(value),
                )
            )

    for name, input_def in input_schema.items():
        if name not in raw_inputs:
            if input_def.default is not None:
                normalized[name] = copy.deepcopy(input_def.default)
                sources[name] = "defaulted"
                continue
            if input_def.required:
                fields.append(
                    _workflow_input_field_error(
                        name,
                        "required",
                        f"Input '{name}' is required.",
                        expected_type=input_def.type,
                        actual_type=None,
                    )
                )
            continue

        value = raw_inputs[name]
        if not _matches_input_type(value, input_def.type):
            fields.append(
                _workflow_input_field_error(
                    name,
                    "type_mismatch",
                    f"Input '{name}' must be {_type_label(input_def)}.",
                    expected_type=input_def.type,
                    actual_type=_actual_input_type(value),
                )
            )
            continue
        normalized[name] = value
        sources[name] = "provided"

    if fields:
        _raise_workflow_input_validation(workflow_id, fields)

    return _prepared_run_inputs(input_schema, normalized, sources)


def _split_prepared_inputs(inputs: PreparedRunInputs) -> PreparedRunInputs:
    if isinstance(inputs, PreparedRunInputs):
        return inputs
    raise TypeError("Workflow launch inputs must be PreparedRunInputs")


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

    @staticmethod
    def _can_fallback_to_working_tree(error: Exception) -> bool:
        if isinstance(error, ServiceUnavailable):
            return True
        if not isinstance(error, subprocess.CalledProcessError):
            return False

        detail = (error.stderr or "").lower()
        return (
            "not a git repository" in detail
            or "ambiguous argument 'head'" in detail
            or "needed a single revision" in detail
        )

    async def launch_execution(
        self,
        run_id: str,
        workflow_id: str,
        inputs: PreparedRunInputs,
        branch: str,
    ) -> None:
        """Launch workflow execution as a background asyncio task.

        Parses the workflow synchronously (so patches/mocks are active),
        then schedules the actual run as a background asyncio task.
        """
        if not isinstance(inputs, PreparedRunInputs):
            raise TypeError("launch_execution inputs must be PreparedRunInputs")

        try:
            # Load workflow entity
            wf_entity = self.workflow_repo.get_by_id(workflow_id)
            if wf_entity is None:
                raise ValueError(f"Workflow {_workflow_ref(workflow_id)} not found")

            workflow_path = str(self.workflow_repo._get_path(workflow_id))
            workflow_registry_git_ref = branch if self.git_service else None
            workflow_registry_git_service = self.git_service

            # When Git is configured, always load the workflow from the requested
            # branch snapshot instead of the working tree copy.
            if self.git_service:
                try:
                    yaml_content = self.git_service.read_file(workflow_path, branch)
                    commit_sha = self.git_service.get_sha(branch, workflow_path)
                except Exception as exc:
                    if not self._can_fallback_to_working_tree(exc):
                        raise
                    logger.warning(
                        "Git workflow snapshot unavailable; falling back to working tree YAML",
                        extra={"run_id": run_id, "workflow_id": workflow_id, "branch": branch},
                        exc_info=True,
                    )
                    yaml_content = wf_entity.yaml
                    commit_sha = self._get_workflow_commit_sha(workflow_path)
                    workflow_registry_git_ref = None
                    workflow_registry_git_service = None
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
                    git_ref=workflow_registry_git_ref,
                    git_service=workflow_registry_git_service,
                )

            # Parse workflow YAML into runnable Workflow
            wf = parse_workflow_yaml(
                yaml_content,
                workflow_registry=workflow_registry,
                api_keys=api_keys,
                runner=runner,
                _base_dir=str(self.workflow_repo.base_path),
            )

            # Store branch + commit_sha on Run record
            self._store_branch_and_sha(run_id, branch, commit_sha)

        except Exception as e:
            logger.exception("Failed to prepare workflow for run %s", run_id)
            self._fail_run_on_prepare_error(run_id, e)
            return

        # Schedule background execution (task starts on next event-loop iteration)
        task = asyncio.create_task(self._run_workflow(run_id, wf, inputs))
        self._running_tasks[run_id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(run_id, None))

    def prepare_run_inputs(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        *,
        branch: str = "main",
    ) -> PreparedRunInputs:
        wf_entity = self.workflow_repo.get_by_id(workflow_id)
        if wf_entity is None:
            raise WorkflowNotFound(f"Workflow {_workflow_ref(workflow_id)} not found")

        workflow_path = str(self.workflow_repo._get_path(workflow_id))
        yaml_content = (
            self.git_service.read_file(workflow_path, branch)
            if self.git_service
            else wf_entity.yaml
        )
        return _prepare_run_inputs_from_schema(
            workflow_id,
            _workflow_input_schema_from_yaml(workflow_id, yaml_content),
            inputs,
        )

    async def _run_workflow(self, run_id: str, wf: Any, inputs: PreparedRunInputs) -> None:
        """Execute the workflow with CompositeObserver for status management.

        Acquires the concurrency semaphore before running. Status stays
        'pending' until the semaphore is acquired, then transitions to
        'running'. Terminal status (completed/failed) is written exclusively
        by ExecutionObserver via Workflow.run()'s observer callbacks.
        """
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
            prepared_inputs = _split_prepared_inputs(inputs)
            state = WorkflowState(
                artifact_store=artifact_store,
                input_redactor=prepared_inputs.input_redactor,
            )

            try:
                state = await wf.run(
                    state,
                    observer=observer,
                    inputs=prepared_inputs.normalized_inputs,
                )
            except Exception as exc:
                tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                logger.error(
                    "Workflow execution failed for run %s\n%s",
                    run_id,
                    prepared_inputs.input_redactor.redact_text(tb_str),
                )
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
                    f"Soul '{soul_key}' references disabled or missing provider "
                    f"{_provider_ref(provider_id)}"
                )

            if not isinstance(model_name, str) or not model_name.strip():
                raise ValueError(f"Soul '{soul_key}' must define an explicit model_name")

            if model_name not in self._provider_models(provider):
                raise ValueError(
                    f"Soul '{soul_key}' model '{model_name}' does not belong to provider "
                    f"{_provider_ref(provider_id)}"
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
