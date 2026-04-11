"""IPC data models and type aliases for the isolation protocol (RUN-817).

Extracted from ipc.py to give model definitions a dedicated home, separate
from the IPCServer / IPCClient implementation.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterable, Awaitable
from contextvars import ContextVar
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

HandlerResult = Awaitable[dict[str, Any]] | AsyncIterable[dict[str, Any]]
Handler = Callable[[dict[str, Any]], HandlerResult]

_current_ipc_request_id: ContextVar[str | None] = ContextVar(
    "_current_ipc_request_id",
    default=None,
)

RPC_ALLOWLIST = frozenset(
    {
        "capability_negotiation",
        "delegate",
        "file_io",
        "http",
        "llm_call",
        "simple",
        "stream",
        "tool_call",
        "write_artifact",
    }
)


class GrantToken(BaseModel):
    """Single-use grant token for subprocess->engine IPC authentication."""

    block_id: str
    token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = Field(default_factory=time.monotonic)
    ttl_seconds: float = 120.0
    consumed: bool = False

    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_seconds

    def consume(self) -> bool:
        if self.consumed:
            return False
        if self.is_expired():
            return False
        self.consumed = True
        return True


class IPCRequest(BaseModel):
    """Request envelope sent from engine process to worker process."""

    model_config = ConfigDict(extra="forbid")

    id: str
    action: str
    payload: dict[str, Any]


class CapabilityRequest(BaseModel):
    """Dedicated startup capability negotiation request."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["capability_negotiation"] = "capability_negotiation"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    grant_token: str
    supported_actions: list[str]
    worker_version: str


class CapabilityResponse(BaseModel):
    """Dedicated startup capability negotiation response."""

    id: str
    done: bool = True
    accepted: bool
    active_actions: list[str]
    engine_context: dict[str, Any]
    error: str | None


class IPCResponseFrame(BaseModel):
    """Streamed response frame sent from worker process to engine process."""

    id: str
    done: bool
    payload: Any | None
    engine_context: dict[str, Any] | None
    error: str | None
