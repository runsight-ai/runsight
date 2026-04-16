"""Transport helpers for persisted context audit log rows."""

from __future__ import annotations

import base64
import json
from typing import Any

from runsight_core.context_governance import ContextAuditEventV1


def parse_context_audit_message(message: str) -> ContextAuditEventV1 | None:
    """Return a context audit event when a log message matches the v1 contract."""

    try:
        return ContextAuditEventV1.model_validate_json(message)
    except ValueError:
        return None


def context_audit_sort_key(log: Any, event: ContextAuditEventV1) -> tuple[int, float | int, int]:
    """Stable ordering key: audit sequence first, then persisted log order."""

    log_id = _log_id(log)
    if event.sequence is not None:
        return (0, event.sequence, log_id)
    created_at = getattr(log, "created_at", getattr(log, "timestamp", 0.0))
    return (1, float(created_at) if isinstance(created_at, int | float) else 0.0, log_id)


def encode_context_audit_cursor(key: tuple[int, float | int, int]) -> str:
    raw = json.dumps({"key": list(key)}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_context_audit_cursor(cursor: str) -> tuple[int, float, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        key = payload["key"]
        if not isinstance(key, list) or len(key) != 3:
            raise ValueError("cursor key must have three parts")
        bucket, value, log_id = key
        if not isinstance(bucket, int) or bucket not in {0, 1}:
            raise ValueError("cursor bucket invalid")
        if not isinstance(value, int | float) or not isinstance(log_id, int):
            raise ValueError("cursor value invalid")
        return (bucket, float(value), log_id)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid context audit cursor") from exc


def _log_id(log: Any) -> int:
    log_id = getattr(log, "id", 0)
    return log_id if isinstance(log_id, int) else 0
