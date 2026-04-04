"""Base models for the assertion plugin interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class TokenUsage:
    """Token usage breakdown for an assertion evaluation."""

    prompt: int = 0
    completion: int = 0
    total: int = 0


@dataclass
class GradingResult:
    """Result of a single assertion evaluation."""

    passed: bool
    score: float
    reason: str
    named_scores: dict[str, float] = field(default_factory=dict)
    tokens_used: TokenUsage | None = None
    component_results: list[GradingResult] = field(default_factory=list)
    assertion_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssertionContext:
    """Context provided to assertion evaluators."""

    output: str
    prompt: str
    prompt_hash: str
    soul_id: str
    soul_version: str
    block_id: str
    block_type: str
    cost_usd: float
    total_tokens: int
    latency_ms: float
    variables: dict[str, Any]
    run_id: str
    workflow_id: str


@runtime_checkable
class Assertion(Protocol):
    """Protocol that assertion plugins must satisfy."""

    type: str

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult: ...
