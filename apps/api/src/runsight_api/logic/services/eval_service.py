from __future__ import annotations

from collections import defaultdict
from statistics import mean
import time

from ...data.repositories.run_repo import RunRepository
from ...transport.schemas.dashboard import AttentionItem
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

    def get_attention_items(self) -> list[AttentionItem]:
        """Scan recent production run nodes for attention-worthy conditions."""
        cutoff = time.time() - 24 * 3600
        items: list[tuple[float, AttentionItem]] = []
        previous_by_key: dict[tuple[str, str, str | None], object] = {}
        severity_rank = {"warning": 1, "info": 0}

        runs = [
            run
            for run in self.run_repo.list_runs()
            if (
                getattr(run, "branch", "main")
                if isinstance(getattr(run, "branch", "main"), str)
                else "main"
            )
            == "main"
            and (
                getattr(run, "source", "manual")
                if isinstance(getattr(run, "source", "manual"), str)
                else "manual"
            )
            in {"manual", "webhook", "schedule"}
        ]
        runs.sort(key=lambda run: run.created_at)

        for run in runs:
            nodes = sorted(
                self.run_repo.list_nodes_for_run(run.id), key=lambda node: node.created_at
            )
            for node in nodes:
                key = (run.workflow_id, node.node_id, node.soul_version)
                previous_node = previous_by_key.get(key)

                if run.created_at > cutoff:
                    title = f"{run.workflow_name} · {node.node_id}"

                    if node.soul_version is not None and previous_node is None:
                        items.append(
                            (
                                node.created_at,
                                AttentionItem(
                                    type="new_baseline",
                                    title=title,
                                    description="First production run for this version on main.",
                                    run_id=run.id,
                                    workflow_id=run.workflow_id,
                                    severity="info",
                                ),
                            )
                        )
                    elif previous_node is not None:
                        if node.eval_passed is False and previous_node.eval_passed is True:
                            items.append(
                                (
                                    node.created_at,
                                    AttentionItem(
                                        type="assertion_regression",
                                        title=title,
                                        description="Eval passed on the previous production run and failed on this one.",
                                        run_id=run.id,
                                        workflow_id=run.workflow_id,
                                        severity="warning",
                                    ),
                                )
                            )

                        if previous_node.cost_usd > 0:
                            cost_pct = (
                                (node.cost_usd - previous_node.cost_usd)
                                / previous_node.cost_usd
                                * 100
                            )
                            if cost_pct > 20:
                                items.append(
                                    (
                                        node.created_at,
                                        AttentionItem(
                                            type="cost_spike",
                                            title=title,
                                            description=f"Cost increased {cost_pct:.0f}% vs the previous production run.",
                                            run_id=run.id,
                                            workflow_id=run.workflow_id,
                                            severity="warning",
                                        ),
                                    )
                                )

                        if node.eval_score is not None and previous_node.eval_score is not None:
                            score_delta = node.eval_score - previous_node.eval_score
                            if score_delta < -0.1:
                                items.append(
                                    (
                                        node.created_at,
                                        AttentionItem(
                                            type="quality_drop",
                                            title=title,
                                            description=f"Eval score dropped {abs(score_delta):.2f} vs the previous production run.",
                                            run_id=run.id,
                                            workflow_id=run.workflow_id,
                                            severity="warning",
                                        ),
                                    )
                                )

                previous_by_key[key] = node

        items.sort(
            key=lambda item: (severity_rank.get(item[1].severity, 0), item[0]),
            reverse=True,
        )
        return [item for _, item in items]

    # ------------------------------------------------------------------
    # Regression detection (comparison-based)
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_node_regressions(
        current_node,
        previous_node,
    ) -> list[dict]:
        """Compare two matching nodes and return regression issue dicts."""
        issues: list[dict] = []

        # 1. assertion_regression: passed -> failed (same soul_version)
        if current_node.eval_passed is False and previous_node.eval_passed is True:
            issues.append(
                {
                    "node_id": current_node.node_id,
                    "node_name": getattr(current_node, "node_name", current_node.node_id),
                    "type": "assertion_regression",
                    "delta": {
                        "eval_passed": False,
                        "baseline_eval_passed": True,
                    },
                }
            )

        # 2. cost_spike: >20% cost increase
        if previous_node.cost_usd > 0:
            cost_pct = (
                (current_node.cost_usd - previous_node.cost_usd) / previous_node.cost_usd * 100
            )
            if cost_pct > 20:
                issues.append(
                    {
                        "node_id": current_node.node_id,
                        "node_name": getattr(current_node, "node_name", current_node.node_id),
                        "type": "cost_spike",
                        "delta": {
                            "cost_pct": cost_pct,
                            "baseline_cost": previous_node.cost_usd,
                        },
                    }
                )

        # 3. quality_drop: eval_score drop > 0.1
        if current_node.eval_score is not None and previous_node.eval_score is not None:
            score_delta = current_node.eval_score - previous_node.eval_score
            if score_delta < -0.1:
                issues.append(
                    {
                        "node_id": current_node.node_id,
                        "node_name": getattr(current_node, "node_name", current_node.node_id),
                        "type": "quality_drop",
                        "delta": {
                            "score_delta": score_delta,
                        },
                    }
                )

        return issues

    @staticmethod
    def _is_production_run(run) -> bool:
        """Filter to main-branch production runs, consistent with get_attention_items."""
        branch = getattr(run, "branch", "main")
        if not isinstance(branch, str):
            branch = "main"
        source = getattr(run, "source", "manual")
        if not isinstance(source, str):
            source = "manual"
        return branch == "main" and source in {"manual", "webhook", "schedule"}

    def get_run_regressions(self, run_id: str) -> dict | None:
        """Compute comparison-based regressions for a single run."""
        run = self.run_repo.get_run(run_id)
        if run is None:
            return None

        # Get production runs for the same workflow, ordered by created_at asc
        all_runs = self.run_repo.list_runs()
        workflow_runs = [
            r for r in all_runs if r.workflow_id == run.workflow_id and self._is_production_run(r)
        ]
        workflow_runs.sort(key=lambda r: r.created_at)

        # Find the previous production run before this one
        previous_run = None
        for r in workflow_runs:
            if r.id == run_id:
                break
            previous_run = r

        if previous_run is None:
            return {"count": 0, "issues": []}

        current_nodes = self.run_repo.list_nodes_for_run(run_id)
        previous_nodes = self.run_repo.list_nodes_for_run(previous_run.id)

        # Index previous nodes by (node_id, soul_version) — matching get_attention_items
        prev_node_map: dict[tuple[str, str | None], object] = {}
        for n in previous_nodes:
            sv = getattr(n, "soul_version", None)
            prev_node_map[(n.node_id, sv)] = n

        issues: list[dict] = []
        for node in current_nodes:
            sv = getattr(node, "soul_version", None)
            prev_node = prev_node_map.get((node.node_id, sv))
            if prev_node is None:
                continue
            issues.extend(self._detect_node_regressions(node, prev_node))

        return {"count": len(issues), "issues": issues}

    def get_workflow_regressions(self, workflow_id: str) -> dict:
        """Compute comparison-based regressions across all production runs of a workflow."""
        all_runs = self.run_repo.list_runs()
        workflow_runs = [
            r for r in all_runs if r.workflow_id == workflow_id and self._is_production_run(r)
        ]
        workflow_runs.sort(key=lambda r: r.created_at)

        if len(workflow_runs) < 2:
            return {"count": 0, "issues": []}

        all_issues: list[dict] = []

        for i in range(1, len(workflow_runs)):
            current_run = workflow_runs[i]
            previous_run = workflow_runs[i - 1]

            current_nodes = self.run_repo.list_nodes_for_run(current_run.id)
            previous_nodes = self.run_repo.list_nodes_for_run(previous_run.id)

            # Index by (node_id, soul_version)
            prev_node_map: dict[tuple[str, str | None], object] = {}
            for n in previous_nodes:
                sv = getattr(n, "soul_version", None)
                prev_node_map[(n.node_id, sv)] = n

            for node in current_nodes:
                sv = getattr(node, "soul_version", None)
                prev_node = prev_node_map.get((node.node_id, sv))
                if prev_node is None:
                    continue
                node_issues = self._detect_node_regressions(node, prev_node)
                for issue in node_issues:
                    issue["run_id"] = current_run.id
                    issue["run_number"] = getattr(current_run, "run_number", None)
                all_issues.extend(node_issues)

        return {"count": len(all_issues), "issues": all_issues}

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
