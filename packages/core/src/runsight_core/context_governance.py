"""Context governance contracts for workflow input resolution."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from runsight_core.state import BlockResult, WorkflowState

_REDACTED_PREVIEW = "[redacted]"
_MAX_PREVIEW_LENGTH = 200
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
        if self.preview is not None and _is_secret_like_ref(
            self.input_name,
            self.from_ref,
            self.source,
            self.field_path,
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
    state_snapshot: None = None
    audit_event: ContextAuditEventV1


class ContextResolutionError(ValueError):
    """Raised when declared context cannot be resolved."""


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

        if declaration.access != ContextAccess.DECLARED.value:
            raise ContextReadDeniedError(
                f"Context access '{declaration.access}' is not implemented for {declaration.block_id}"
            )

        for input_name, from_ref in declaration.declared_inputs.items():
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
                        )
                    )
                    continue
                raise

            inputs[input_name] = value
            _scope_value(
                parsed=parsed,
                value=value,
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


def _resolve_parsed_ref(parsed: ParsedContextRef, state: WorkflowState) -> object:
    if parsed.namespace == ContextAuditNamespace.RESULTS.value:
        if parsed.source not in state.results:
            raise ContextResolutionError(
                f"Context resolution failed for {parsed.source}"
                f"{'.' + parsed.field_path if parsed.field_path else ''}: source result missing"
            )
        result = state.results[parsed.source]
        raw_output = result.output if isinstance(result, BlockResult) else str(result)
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
            if field_path == "output":
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
    scoped_results: dict[str, BlockResult],
    scoped_shared_memory: dict[str, object],
    scoped_metadata: dict[str, object],
) -> None:
    if parsed.namespace == ContextAuditNamespace.RESULTS.value:
        if parsed.field_path is None:
            output = value if isinstance(value, str) else json.dumps(value)
        else:
            output = json.dumps(_nest_field_path(parsed.field_path, value))
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
        target[parsed.source] = _nest_field_path(parsed.field_path, value)


def _nest_field_path(field_path: str, value: object) -> dict[str, object]:
    parts = field_path.split(".")
    nested: object = value
    for part in reversed(parts):
        nested = {part: nested}
    return nested if isinstance(nested, dict) else {}


def _audit_record(
    *,
    input_name: str,
    from_ref: str,
    parsed: ParsedContextRef,
    status: ContextAuditStatus,
    severity: ContextAuditSeverity,
    value: object | None = None,
    reason: str | None = None,
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
        internal=False,
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
