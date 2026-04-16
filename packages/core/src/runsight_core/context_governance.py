"""Context governance contracts for workflow input resolution."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

_REDACTED_PREVIEW = "[redacted]"
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
