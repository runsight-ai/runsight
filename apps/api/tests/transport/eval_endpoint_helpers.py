"""Eval endpoint transport test builders."""

from __future__ import annotations

from unittest.mock import Mock

from runsight_api.domain.entities.run import BaselineStats
from runsight_api.logic.services.eval_service import EvalService
from runsight_api.transport.schemas.eval import (
    EvalDelta,
    NodeEvalResult,
    RunEvalResponse,
    SoulVersionEntry,
)

_DEFAULT_EVAL_RESULTS = object()


def make_node_eval_result(*, node_id: str = "analyze", with_delta: bool = True) -> NodeEvalResult:
    delta = None
    if with_delta:
        delta = EvalDelta(
            cost_pct=-12.3,
            tokens_pct=-8.1,
            score_delta=0.02,
            baseline_run_count=487,
        )
    return NodeEvalResult(
        node_id=node_id,
        block_id=node_id,
        soul_id="researcher_v1",
        prompt_hash="sha256:abc123",
        soul_version="sha256:def456",
        eval_score=0.95,
        passed=True,
        assertions=[
            {"type": "contains", "passed": True, "score": 1.0, "reason": "ok"},
        ],
        delta=delta,
    )


def make_run_eval_response(*, nodes=None) -> RunEvalResponse:
    if nodes is None:
        nodes = [make_node_eval_result()]
    return RunEvalResponse(
        run_id="run_abc123",
        aggregate_score=0.92,
        passed=True,
        nodes=nodes,
    )


def make_version_entry(**overrides) -> SoulVersionEntry:
    defaults = dict(
        soul_version="sha256:abc123",
        avg_score=0.94,
        avg_cost=0.003,
        run_count=487,
        first_seen="2026-03-20T00:00:00",
        last_seen="2026-03-25T00:00:00",
    )
    defaults.update(overrides)
    return SoulVersionEntry(**defaults)


def eval_service_with_baseline(repo: Mock, *, baseline=None) -> EvalService:
    run_read_model = Mock()
    run_read_model.get_baseline.return_value = baseline
    return EvalService(repo, run_read_model=run_read_model)


def eval_node(
    *,
    node_id: str = "analyze",
    block_type: str = "llm",
    soul_id: str | None = "researcher_v1",
    prompt_hash: str | None = "sha256:abc",
    soul_version: str | None = "sha256:def",
    eval_score: float | None = 0.95,
    eval_passed: bool | None = True,
    eval_results: dict | None | object = _DEFAULT_EVAL_RESULTS,
    cost_usd: float = 0.005,
    tokens: dict | None = None,
    created_at: float | None = None,
) -> Mock:
    attrs = dict(
        node_id=node_id,
        block_type=block_type,
        soul_id=soul_id,
        prompt_hash=prompt_hash,
        soul_version=soul_version,
        eval_score=eval_score,
        eval_passed=eval_passed,
        eval_results=(
            {"assertions": [{"type": "contains", "passed": True, "score": 1.0, "reason": "ok"}]}
            if eval_results is _DEFAULT_EVAL_RESULTS
            else eval_results
        ),
        cost_usd=cost_usd,
        tokens=tokens or {"prompt": 100, "completion": 50, "total": 150},
    )
    if created_at is not None:
        attrs["created_at"] = created_at
    return Mock(**attrs)


def baseline_stats() -> BaselineStats:
    return BaselineStats(
        avg_cost=0.005,
        avg_tokens=150.0,
        avg_score=0.93,
        run_count=487,
    )
