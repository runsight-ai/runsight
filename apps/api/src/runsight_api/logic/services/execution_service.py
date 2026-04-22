"""ExecutionService facade for execution collaborators."""

import copy
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional

from runsight_core.identity import EntityKind, EntityRef
from runsight_core.redaction import RunRedactor
from runsight_core.workflow_input_schema import effective_workflow_input_schema
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile, WorkflowInputDef
from pydantic import ValidationError
import yaml

from ...core.secrets import SecretsEnvLoader
from ...domain.entities.run import RunStatus
from ...domain.errors import InputValidationError, WorkflowNotFound
from .execution_persistence import ExecutionRunStore
from .execution_preparation import (
    ExecutionPreparationService,
    get_workflow_commit_sha,
    has_workflow_blocks,
)
from .execution_runtime import ExecutionRuntimeCoordinator, build_assertion_configs
from .execution_stream_registry import ExecutionStreamRegistry

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

    @staticmethod
    def _has_workflow_blocks(workflow_definition: Dict[str, Any]) -> bool:
        return has_workflow_blocks(workflow_definition)

    def fail_ghost_runs(self) -> None:
        self._run_store.fail_ghost_runs()

    def cancel_execution(self, run_id: str) -> bool:
        return self._runtime.cancel(run_id)

    async def subscribe_stream(self, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._streams.subscribe(run_id):
            yield event

    @staticmethod
    def _get_workflow_commit_sha(workflow_path: str) -> Optional[str]:
        return get_workflow_commit_sha(workflow_path)

    async def launch_execution(
        self,
        run_id: str,
        workflow_id: str,
        inputs: PreparedRunInputs,
        branch: str = "main",
    ) -> None:
        """Prepare a workflow snapshot, then schedule background execution."""
        if not isinstance(inputs, PreparedRunInputs):
            raise TypeError("launch_execution inputs must be PreparedRunInputs")

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

    def prepare_run_inputs(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        *,
        branch: str = "main",
    ) -> PreparedRunInputs:
        wf_entity = self.workflow_repo.get_by_id(workflow_id)
        workflow_path = str(self.workflow_repo._get_path(workflow_id))
        if self.git_service:
            yaml_content = self.git_service.read_file(workflow_path, branch)
        else:
            if wf_entity is None:
                raise WorkflowNotFound(f"Workflow {_workflow_ref(workflow_id)} not found")
            yaml_content = wf_entity.yaml
        return _prepare_run_inputs_from_schema(
            workflow_id,
            _workflow_input_schema_from_yaml(workflow_id, yaml_content),
            inputs,
        )

    async def _run_workflow(self, run_id: str, wf: Any, inputs: PreparedRunInputs) -> None:
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
