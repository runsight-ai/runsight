"""Base models for the assertion plugin interface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


def token_usage_from_data(raw: Any) -> TokenUsage | None:
    """Deserialize TokenUsage from a dict payload."""
    if raw is None:
        return None
    if isinstance(raw, TokenUsage):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("tokens_used must be an object when provided")
    return TokenUsage(
        prompt=int(raw.get("prompt", 0) or 0),
        completion=int(raw.get("completion", 0) or 0),
        total=int(raw.get("total", 0) or 0),
    )


def grading_result_from_data(raw: Any) -> GradingResult:
    """Deserialize a GradingResult from a dict payload, including nested fields."""
    if isinstance(raw, GradingResult):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("grading result payload must be an object")

    named_scores_raw = raw.get("named_scores", {})
    if not isinstance(named_scores_raw, dict):
        named_scores_raw = {}

    metadata_raw = raw.get("metadata", {})
    if not isinstance(metadata_raw, dict):
        metadata_raw = {}

    component_results_raw = raw.get("component_results", [])
    if not isinstance(component_results_raw, list):
        component_results_raw = []

    return GradingResult(
        passed=bool(raw.get("passed", False)),
        score=float(raw.get("score", 0.0)),
        reason=str(raw.get("reason", "")),
        named_scores={str(k): float(v) for k, v in named_scores_raw.items()},
        tokens_used=token_usage_from_data(raw.get("tokens_used")),
        component_results=[grading_result_from_data(item) for item in component_results_raw],
        assertion_type=str(raw["assertion_type"])
        if raw.get("assertion_type") is not None
        else None,
        metadata={str(k): v for k, v in metadata_raw.items()},
    )


def grading_result_to_data(result: GradingResult) -> dict[str, Any]:
    """Serialize a GradingResult into JSON-compatible data."""
    return asdict(result)
