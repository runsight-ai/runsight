from __future__ import annotations

from pydantic import BaseModel


class EvalDelta(BaseModel):
    cost_pct: float
    tokens_pct: float
    score_delta: float | None
    baseline_run_count: int


class NodeEvalResult(BaseModel):
    node_id: str
    block_id: str
    soul_id: str | None
    prompt_hash: str | None
    soul_version: str | None
    eval_score: float | None
    passed: bool | None
    assertions: list[dict] | None
    delta: EvalDelta | None


class RunEvalResponse(BaseModel):
    run_id: str
    aggregate_score: float | None
    passed: bool | None
    nodes: list[NodeEvalResult]


class SoulVersionEntry(BaseModel):
    soul_version: str
    avg_score: float | None
    avg_cost: float
    run_count: int
    first_seen: float | str
    last_seen: float | str


class SoulEvalHistoryResponse(BaseModel):
    soul_id: str
    versions: list[SoulVersionEntry]
