from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ...data.repositories.run_repo import RunRepository
from ...transport.schemas.eval import (
    EvalDelta,
    NodeEvalResult,
    RunEvalResponse,
    SoulEvalHistoryResponse,
    SoulVersionEntry,
)


class EvalService:
    def __init__(self, run_repo: RunRepository):
        self.run_repo = run_repo

    def get_run_eval(self, run_id: str) -> RunEvalResponse | None:
        run = self.run_repo.get_run(run_id)
        if run is None:
            return None

        all_nodes = self.run_repo.list_nodes_for_run(run_id)
        eval_nodes = [n for n in all_nodes if n.eval_score is not None]

        node_results: list[NodeEvalResult] = []
        for node in eval_nodes:
            delta = self._compute_delta(node)
            assertions = None
            if node.eval_results and isinstance(node.eval_results, dict):
                assertions = node.eval_results.get("assertions")

            node_results.append(
                NodeEvalResult(
                    node_id=node.node_id,
                    block_id=node.node_id,
                    soul_id=node.soul_id,
                    prompt_hash=node.prompt_hash,
                    soul_version=node.soul_version,
                    eval_score=node.eval_score,
                    passed=node.eval_passed,
                    assertions=assertions,
                    delta=delta,
                )
            )

        scores = [n.eval_score for n in eval_nodes if n.eval_score is not None]
        aggregate_score = mean(scores) if scores else None

        passed_values = [n.eval_passed for n in eval_nodes if n.eval_passed is not None]
        aggregate_passed = all(passed_values) if passed_values else None

        return RunEvalResponse(
            run_id=run.id,
            aggregate_score=aggregate_score,
            passed=aggregate_passed,
            nodes=node_results,
        )

    def get_soul_eval_history(self, soul_id: str) -> SoulEvalHistoryResponse:
        nodes = self.run_repo.list_nodes_for_soul(soul_id)
        eval_nodes = [n for n in nodes if n.eval_score is not None]

        groups: dict[str, list] = defaultdict(list)
        for node in eval_nodes:
            if node.soul_version is not None:
                groups[node.soul_version].append(node)

        versions: list[SoulVersionEntry] = []
        for soul_version, group_nodes in groups.items():
            scores = [n.eval_score for n in group_nodes if n.eval_score is not None]
            costs = [n.cost_usd for n in group_nodes]
            timestamps = [n.created_at for n in group_nodes]

            versions.append(
                SoulVersionEntry(
                    soul_version=soul_version,
                    avg_score=mean(scores) if scores else None,
                    avg_cost=mean(costs),
                    run_count=len(group_nodes),
                    first_seen=min(timestamps),
                    last_seen=max(timestamps),
                )
            )

        versions.sort(key=lambda v: v.first_seen)

        return SoulEvalHistoryResponse(soul_id=soul_id, versions=versions)

    def _compute_delta(self, node) -> EvalDelta | None:
        if node.soul_id is None or node.soul_version is None:
            return None

        baseline = self.run_repo.get_baseline(node.soul_id, node.soul_version)
        if baseline is None:
            return None

        cost_pct = 0.0
        if baseline.avg_cost != 0:
            cost_pct = (node.cost_usd - baseline.avg_cost) / baseline.avg_cost * 100

        tokens_total = (node.tokens or {}).get("total", 0)
        tokens_pct = 0.0
        if baseline.avg_tokens != 0:
            tokens_pct = (tokens_total - baseline.avg_tokens) / baseline.avg_tokens * 100

        score_delta = None
        if node.eval_score is not None and baseline.avg_score is not None:
            score_delta = node.eval_score - baseline.avg_score

        return EvalDelta(
            cost_pct=cost_pct,
            tokens_pct=tokens_pct,
            score_delta=score_delta,
            baseline_run_count=baseline.run_count,
        )
