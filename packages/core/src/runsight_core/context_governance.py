"""Context governance contracts for workflow input resolution."""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from runsight_core.state import BlockResult, WorkflowState

_REDACTED_PREVIEW = "[redacted]"
_MAX_PREVIEW_LENGTH = 200
_WHOLE_OUTPUT_ALIASES = {"output", "result"}
_SECRET_REF_MARKERS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "token",
    "credential",
    "private_key",
)


class ContextAccess(StrEnum):
    """Block-level context access policy declared in workflow YAML."""

    DECLARED = "declared"
    ALL = "all"


class ContextAuditNamespace(StrEnum):
    """Supported namespaces for context audit records."""

    RESULTS = "results"
    SHARED_MEMORY = "shared_memory"
    METADATA = "metadata"


class ContextAuditMode(StrEnum):
    """Context governance enforcement mode."""

    STRICT = "strict"
    DEV = "dev"


class ContextAuditStatus(StrEnum):
    """Resolution outcome for one requested context reference."""

    RESOLVED = "resolved"
    MISSING = "missing"
    DENIED = "denied"
    ALL_ACCESS = "all_access"
    EMPTY = "empty"


class ContextAuditSeverity(StrEnum):
    """Audit severity for one resolution record."""

    ALLOW = "allow"
    WARN = "warn"
    ERROR = "error"


class ParsedContextRef(BaseModel):
    """Normalized context reference split into namespace, source, and field path."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    namespace: ContextAuditNamespace
    source: str
    field_path: str | None = None


class ContextGovernancePolicy(BaseModel):
    """Runtime context governance policy."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    mode: ContextAuditMode = ContextAuditMode.STRICT


class ContextDeclaration(BaseModel):
    """Block-level context declaration consumed by ContextResolver."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    block_id: str
    block_type: str
    access: ContextAccess = ContextAccess.DECLARED
    declared_inputs: dict[str, str] = Field(default_factory=dict)
    internal_inputs: dict[str, str] = Field(default_factory=dict)


class ContextAuditRecordV1(BaseModel):
    """Audit record for a single block input context reference."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    input_name: str | None
    from_ref: str | None
    namespace: ContextAuditNamespace | None
    source: str | None
    field_path: str | None = None
    status: ContextAuditStatus
    severity: ContextAuditSeverity
    value_type: str | None = None
    preview: str | None = None
    reason: str | None = None
    internal: bool = False

    @model_validator(mode="after")
    def _redact_secret_like_preview(self) -> Self:
        if self.preview is not None and (
            _is_secret_like_ref(
                self.input_name,
                self.from_ref,
                self.source,
                self.field_path,
            )
            or _is_secret_like_value(self.preview)
        ):
            self.preview = _REDACTED_PREVIEW
        return self


class ContextAuditEventV1(BaseModel):
    """Audit event emitted after resolving context for one block."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    schema_version: Literal["context_audit.v1"] = "context_audit.v1"
    event: Literal["context_resolution"] = "context_resolution"
    run_id: str
    workflow_name: str
    node_id: str
    block_type: str
    access: ContextAccess
    mode: ContextAuditMode
    sequence: int | None = None
    records: list[ContextAuditRecordV1] = Field(default_factory=list)
    resolved_count: int = Field(default=0, ge=0)
    denied_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    emitted_at: datetime


class ScopedContextData(BaseModel):
    """Least-privilege context resolved for a single block."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, object] = Field(default_factory=dict)
    scoped_results: dict[str, BlockResult] = Field(default_factory=dict)
    scoped_shared_memory: dict[str, object] = Field(default_factory=dict)
    scoped_metadata: dict[str, object] = Field(default_factory=dict)
    state_snapshot: WorkflowState | None = None
    audit_event: ContextAuditEventV1


class ContextResolutionError(ValueError, KeyError):
    """Raised when declared context cannot be resolved."""


class ContextResolutionAuditError(ContextResolutionError):
    """Raised when context resolution fails after producing an audit event."""

    def __init__(self, message: str, *, audit_event: ContextAuditEventV1) -> None:
        super().__init__(message)
        self.audit_event = audit_event


class ContextReadDeniedError(ContextResolutionError):
    """Raised when a context read violates the declared access policy."""


class ContextResolver:
    """Resolve declared block inputs into least-privilege scoped context."""

    def __init__(
        self,
        *,
        policy: ContextGovernancePolicy | None = None,
        run_id: str,
        workflow_name: str,
    ) -> None:
        self.policy = policy or ContextGovernancePolicy()
        self.run_id = run_id
        self.workflow_name = workflow_name

    def resolve(
        self,
        *,
        declaration: ContextDeclaration,
        state: WorkflowState,
    ) -> ScopedContextData:
        inputs: dict[str, object] = {}
        scoped_results: dict[str, BlockResult] = {}
        scoped_shared_memory: dict[str, object] = {}
        scoped_metadata: dict[str, object] = {}
        records: list[ContextAuditRecordV1] = []

        if declaration.access == ContextAccess.ALL.value:
            if declaration.declared_inputs or declaration.internal_inputs:
                raise ContextReadDeniedError(
                    f"Context access 'all' cannot be combined with declared inputs for {declaration.block_id}"
                )
            inputs = _all_access_inputs(state)
            records.append(
                ContextAuditRecordV1(
                    input_name=None,
                    from_ref=None,
                    namespace=None,
                    source=None,
                    field_path=None,
                    status=ContextAuditStatus.ALL_ACCESS,
                    severity=ContextAuditSeverity.ALLOW,
                    value_type="dict",
                    preview=None,
                    reason="explicit all access",
                    internal=False,
                )
            )
            audit_event = ContextAuditEventV1(
                run_id=self.run_id,
                workflow_name=self.workflow_name,
                node_id=declaration.block_id,
                block_type=declaration.block_type,
                access=declaration.access,
                mode=self.policy.mode,
                records=records,
                resolved_count=0,
                denied_count=0,
                warning_count=0,
                emitted_at=datetime.now().astimezone(),
            )
            return ScopedContextData(
                inputs=inputs,
                scoped_results=dict(state.results),
                scoped_shared_memory=dict(state.shared_memory),
                scoped_metadata=dict(state.metadata),
                audit_event=audit_event,
            )

        if declaration.access != ContextAccess.DECLARED.value:
            raise ContextReadDeniedError(
                f"Context access '{declaration.access}' is not implemented for {declaration.block_id}"
            )

        for input_name, from_ref, internal in _iter_declared_and_internal_inputs(declaration):
            parsed = parse_context_ref(from_ref)
            try:
                value = _resolve_parsed_ref(parsed, state)
            except ContextResolutionError as exc:
                if self.policy.mode == ContextAuditMode.DEV.value:
                    records.append(
                        _audit_record(
                            input_name=input_name,
                            from_ref=from_ref,
                            parsed=parsed,
                            status=ContextAuditStatus.MISSING,
                            severity=ContextAuditSeverity.WARN,
                            reason=str(exc),
                            internal=internal,
                        )
                    )
                    continue
                status = (
                    ContextAuditStatus.DENIED
                    if isinstance(exc, ContextReadDeniedError)
                    else ContextAuditStatus.MISSING
                )
                records.append(
                    _audit_record(
                        input_name=input_name,
                        from_ref=from_ref,
                        parsed=parsed,
                        status=status,
                        severity=ContextAuditSeverity.ERROR,
                        reason=str(exc),
                        internal=internal,
                    )
                )
                raise ContextResolutionAuditError(
                    str(exc),
                    audit_event=ContextAuditEventV1(
                        run_id=self.run_id,
                        workflow_name=self.workflow_name,
                        node_id=declaration.block_id,
                        block_type=declaration.block_type,
                        access=declaration.access,
                        mode=self.policy.mode,
                        records=records,
                        resolved_count=sum(
                            1
                            for record in records
                            if record.status == ContextAuditStatus.RESOLVED.value
                        ),
                        denied_count=sum(
                            1
                            for record in records
                            if record.status == ContextAuditStatus.DENIED.value
                        ),
                        warning_count=sum(
                            1
                            for record in records
                            if record.severity == ContextAuditSeverity.WARN.value
                        ),
                        emitted_at=datetime.now().astimezone(),
                    ),
                ) from exc

            inputs[input_name] = value
            _scope_value(
                parsed=parsed,
                value=value,
                whole_output_alias=_is_non_json_result_alias(parsed, state),
                scoped_results=scoped_results,
                scoped_shared_memory=scoped_shared_memory,
                scoped_metadata=scoped_metadata,
            )
            records.append(
                _audit_record(
                    input_name=input_name,
                    from_ref=from_ref,
                    parsed=parsed,
                    status=ContextAuditStatus.RESOLVED,
                    severity=ContextAuditSeverity.ALLOW,
                    value=value,
                    internal=internal,
                )
            )

        warning_count = sum(
            1 for record in records if record.severity == ContextAuditSeverity.WARN.value
        )
        audit_event = ContextAuditEventV1(
            run_id=self.run_id,
            workflow_name=self.workflow_name,
            node_id=declaration.block_id,
            block_type=declaration.block_type,
            access=declaration.access,
            mode=self.policy.mode,
            records=records,
            resolved_count=sum(
                1 for record in records if record.status == ContextAuditStatus.RESOLVED.value
            ),
            denied_count=sum(
                1 for record in records if record.status == ContextAuditStatus.DENIED.value
            ),
            warning_count=warning_count,
            emitted_at=datetime.now().astimezone(),
        )
        return ScopedContextData(
            inputs=inputs,
            scoped_results=scoped_results,
            scoped_shared_memory=scoped_shared_memory,
            scoped_metadata=scoped_metadata,
            audit_event=audit_event,
        )


def collect_context_declaration(block: object, step: object | None = None) -> ContextDeclaration:
    """Collect user and special-block context declarations for one runtime block."""

    declared_inputs = _user_declared_inputs(block, step)
    internal_inputs = _special_internal_inputs(block)
    collisions = sorted(set(declared_inputs) & set(internal_inputs))
    if collisions:
        raise ValueError(
            f"Block '{getattr(block, 'block_id', '<unknown>')}' input(s) {collisions} "
            "collide with internal context inputs"
        )

    return ContextDeclaration(
        block_id=str(getattr(block, "block_id")),
        block_type=_context_block_type(block),
        access=str(getattr(block, "context_access", getattr(block, "access", "declared"))),
        declared_inputs=declared_inputs,
        internal_inputs=internal_inputs,
    )


def parse_context_ref(ref: str) -> ParsedContextRef:
    """Parse a context reference into the supported governance namespaces."""

    parts = ref.split(".")
    if not parts or any(part == "" for part in parts):
        raise ValueError("context ref must be a non-empty dot path")

    if parts[0] in {namespace.value for namespace in ContextAuditNamespace}:
        if len(parts) < 2:
            raise ValueError("context ref must include a source")
        namespace = parts[0]
        source = parts[1]
        field_path = ".".join(parts[2:]) or None
        return ParsedContextRef(namespace=namespace, source=source, field_path=field_path)

    source = parts[0]
    field_path = ".".join(parts[1:]) or None
    return ParsedContextRef(
        namespace=ContextAuditNamespace.RESULTS,
        source=source,
        field_path=field_path,
    )


def _is_secret_like_ref(*parts: str | None) -> bool:
    normalized = ".".join(part.lower().replace("-", "_") for part in parts if part)
    return any(marker in normalized for marker in _SECRET_REF_MARKERS)


def _is_secret_like_value(value: str) -> bool:
    normalized = value.strip().strip('"').lower()
    if not normalized:
        return False

    secret_patterns = (
        r"\bsk-[a-z0-9][a-z0-9._-]{6,}\b",
        r"\b[a-z0-9_]*(api[_-]?key|secret|token|credential|password)[a-z0-9_]*\s*[:=]",
        r"-----begin [a-z ]*private key-----",
        r"\bakia[0-9a-z]{16}\b",
    )
    return any(re.search(pattern, normalized) for pattern in secret_patterns)


def _iter_declared_and_internal_inputs(
    declaration: ContextDeclaration,
) -> list[tuple[str, str, bool]]:
    return [
        *((name, from_ref, False) for name, from_ref in declaration.declared_inputs.items()),
        *((name, from_ref, True) for name, from_ref in declaration.internal_inputs.items()),
    ]


def _all_access_inputs(state: WorkflowState) -> dict[str, object]:
    return {
        "results": {
            key: value.output if isinstance(value, BlockResult) else value
            for key, value in state.results.items()
        },
        "metadata": dict(state.metadata),
        "shared_memory": dict(state.shared_memory),
    }


def _user_declared_inputs(block: object, step: object | None) -> dict[str, str]:
    if step is not None and hasattr(step, "declared_inputs"):
        return dict(getattr(step, "declared_inputs") or {})
    declared_inputs = getattr(block, "declared_inputs", None)
    if declared_inputs:
        return dict(declared_inputs)
    workflow_inputs = getattr(block, "inputs", None)
    if isinstance(workflow_inputs, dict):
        return dict(workflow_inputs)
    return {}


def _special_internal_inputs(block: object) -> dict[str, str]:
    eval_key = getattr(block, "eval_key", None)
    if eval_key is not None:
        return {"content": str(eval_key)}

    input_block_ids = getattr(block, "input_block_ids", None)
    if input_block_ids is not None:
        return {str(block_id): str(block_id) for block_id in input_block_ids}

    return {}


def _context_block_type(block: object) -> str:
    if getattr(block, "eval_key", None) is not None:
        return "gate"
    if getattr(block, "input_block_ids", None) is not None:
        return "synthesize"
    if getattr(block, "branches", None) is not None:
        return "dispatch"
    if getattr(block, "child_workflow", None) is not None:
        return "workflow"
    if getattr(block, "inner_block_refs", None) is not None:
        return "loop"
    if getattr(block, "code", None) is not None:
        return "code"
    return block.__class__.__name__


def _resolve_parsed_ref(parsed: ParsedContextRef, state: WorkflowState) -> object:
    if parsed.namespace == ContextAuditNamespace.RESULTS.value:
        if parsed.source not in state.results:
            raise ContextResolutionError(
                f"Context resolution failed for {parsed.source}"
                f"{'.' + parsed.field_path if parsed.field_path else ''}: source result missing. "
                f"Available: {sorted(state.results.keys())}"
            )
        result = state.results[parsed.source]
        raw_output = result.output if isinstance(result, BlockResult) else result
        if parsed.field_path is None:
            return raw_output
        return _resolve_field_path(raw_output, parsed.field_path, parsed)

    if parsed.namespace == ContextAuditNamespace.SHARED_MEMORY.value:
        return _resolve_mapping_path(state.shared_memory, parsed)

    if parsed.namespace == ContextAuditNamespace.METADATA.value:
        return _resolve_mapping_path(state.metadata, parsed)

    raise ContextReadDeniedError(f"Unsupported context namespace: {parsed.namespace}")


def _resolve_mapping_path(data: dict[str, object], parsed: ParsedContextRef) -> object:
    if parsed.source not in data:
        raise ContextResolutionError(
            f"Context resolution failed for {parsed.namespace}.{parsed.source}: source missing"
        )
    value = data[parsed.source]
    if parsed.field_path is None:
        return value
    return _resolve_field_path(value, parsed.field_path, parsed)


def _resolve_field_path(value: object, field_path: str, parsed: ParsedContextRef) -> object:
    parsed_value = value
    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
        except (json.JSONDecodeError, TypeError) as exc:
            if field_path in _WHOLE_OUTPUT_ALIASES:
                return value
            raise ContextResolutionError(
                f"Context resolution failed: non-JSON output cannot satisfy "
                f"{parsed.source}.{field_path}"
            ) from exc

    if isinstance(parsed_value, str) or parsed_value is None:
        raise ContextResolutionError(
            f"Context resolution failed: non-JSON output cannot satisfy {parsed.source}.{field_path}"
        )

    from runsight_core.conditions.engine import resolve_dotted_path

    resolved = resolve_dotted_path(parsed_value, field_path)
    if resolved is None and not _has_explicit_none(parsed_value, field_path):
        raise ContextResolutionError(
            f"Context resolution failed for {parsed.source}.{field_path}: field path missing"
        )
    return resolved


def _has_explicit_none(value: object, field_path: str) -> bool:
    current = value
    for part in field_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return False
    return current is None


def _scope_value(
    *,
    parsed: ParsedContextRef,
    value: object,
    whole_output_alias: bool,
    scoped_results: dict[str, BlockResult],
    scoped_shared_memory: dict[str, object],
    scoped_metadata: dict[str, object],
) -> None:
    if parsed.namespace == ContextAuditNamespace.RESULTS.value:
        if parsed.field_path is None or whole_output_alias:
            output = value if isinstance(value, str) else json.dumps(value)
        else:
            output = _merge_result_slice(
                existing=scoped_results.get(parsed.source),
                slice_value=_nest_field_path(parsed.field_path, value),
            )
        scoped_results[parsed.source] = BlockResult(output=output)
        return

    target = (
        scoped_shared_memory
        if parsed.namespace == ContextAuditNamespace.SHARED_MEMORY.value
        else scoped_metadata
    )
    if parsed.field_path is None:
        target[parsed.source] = value
    else:
        target[parsed.source] = _merge_mapping_slice(
            existing=target.get(parsed.source),
            slice_value=_nest_field_path(parsed.field_path, value),
        )


def _merge_result_slice(existing: BlockResult | None, slice_value: dict[str, object]) -> str:
    if existing is None:
        return json.dumps(slice_value)

    existing_value = _json_object_or_none(existing.output)
    if existing_value is None:
        return json.dumps(slice_value)

    return json.dumps(_deep_merge_dicts(existing_value, slice_value))


def _merge_mapping_slice(
    existing: object | None,
    slice_value: dict[str, object],
) -> object:
    if isinstance(existing, dict):
        return _deep_merge_dicts(existing, slice_value)
    return slice_value


def _json_object_or_none(value: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _deep_merge_dicts(
    left: dict[str, object],
    right: dict[str, object],
) -> dict[str, object]:
    merged = dict(left)
    for key, value in right.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(existing, value)
        else:
            merged[key] = value
    return merged


def _nest_field_path(field_path: str, value: object) -> dict[str, object]:
    parts = field_path.split(".")
    nested: object = value
    for part in reversed(parts):
        nested = {part: nested}
    return nested if isinstance(nested, dict) else {}


def _is_non_json_result_alias(parsed: ParsedContextRef, state: WorkflowState) -> bool:
    if (
        parsed.namespace != ContextAuditNamespace.RESULTS.value
        or parsed.field_path not in _WHOLE_OUTPUT_ALIASES
        or parsed.source not in state.results
    ):
        return False
    raw = state.results[parsed.source]
    raw_output = raw.output if isinstance(raw, BlockResult) else raw
    if not isinstance(raw_output, str):
        return False
    try:
        json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        return True
    return False


def _audit_record(
    *,
    input_name: str,
    from_ref: str,
    parsed: ParsedContextRef,
    status: ContextAuditStatus,
    severity: ContextAuditSeverity,
    value: object | None = None,
    reason: str | None = None,
    internal: bool = False,
) -> ContextAuditRecordV1:
    return ContextAuditRecordV1(
        input_name=input_name,
        from_ref=from_ref,
        namespace=parsed.namespace,
        source=parsed.source,
        field_path=parsed.field_path,
        status=status,
        severity=severity,
        value_type=None if value is None else type(value).__name__,
        preview=None if value is None else bounded_context_preview(value),
        reason=reason,
        internal=internal,
    )


def bounded_context_preview(value: object, *, max_length: int = _MAX_PREVIEW_LENGTH) -> str:
    """Return a deterministic bounded preview for audit records."""

    if isinstance(value, str):
        preview = value
    else:
        try:
            preview = json.dumps(value, sort_keys=True, separators=(",", ":"))
        except TypeError:
            preview = repr(value)
    if len(preview) <= max_length:
        return preview
    return preview[: max_length - 3] + "..."
