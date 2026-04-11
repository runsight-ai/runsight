"""Envelope data models for process-isolated block execution (ISO-001)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SoulEnvelope(BaseModel):
    """Identity envelope passed to an isolated block subprocess."""

    id: str
    role: str
    system_prompt: str
    model_name: str
    provider: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    required_tool_calls: list[str] = Field(default_factory=list)
    max_tool_iterations: int = 5


class ToolDefEnvelope(BaseModel):
    """Tool definition envelope for isolated execution."""

    source: str
    config: dict[str, Any]
    exits: list[str]
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    tool_type: str = ""


class TaskEnvelope(BaseModel):
    """Task envelope carrying the instruction for a block."""

    id: str
    instruction: str
    context: dict[str, Any]


class DelegateArtifact(BaseModel):
    """Artifact produced by a delegate tool call."""

    task: str


class ContextEnvelope(BaseModel):
    """Full context shipped to an isolated block subprocess via stdin JSON."""

    block_id: str
    block_type: str
    block_config: dict[str, Any]
    soul: SoulEnvelope
    tools: list[ToolDefEnvelope]
    task: TaskEnvelope
    scoped_results: dict[str, Any]
    scoped_shared_memory: dict[str, Any]
    conversation_history: list[dict[str, Any]]
    timeout_seconds: int
    max_output_bytes: int


class ResultEnvelope(BaseModel):
    """Result returned by an isolated block subprocess via stdout JSON."""

    block_id: str
    output: str | None
    exit_handle: str
    cost_usd: float
    total_tokens: int
    tool_calls_made: int
    delegate_artifacts: dict[str, DelegateArtifact]
    conversation_history: list[dict[str, Any]]
    error: str | None
    error_type: str | None


class HeartbeatMessage(BaseModel):
    """Progress heartbeat sent on stderr as a single JSON line."""

    heartbeat: int
    phase: str
    detail: str
    timestamp: datetime
