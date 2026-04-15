from typing import Any, List, Optional

from sqlalchemy import case
from sqlmodel import Session, delete, func, select

from runsight_core.identity import EntityKind, EntityRef

from ...domain.entities.log import LogEntry
from ...domain.entities.run import BaselineStats, Run, RunNode, RunStatus
from ...domain.errors import WorkflowHasActiveRuns


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


class RunRepository:
    def __init__(self, session: Session):
        self.session = session

    def delete_runs_for_workflow(self, workflow_id: str, force: bool = False) -> int:
        run_ids = list(
            self.session.exec(select(Run.id).where(Run.workflow_id == workflow_id)).all()
        )
        if not run_ids:
            return 0

        if not force:
            active_run = self.session.exec(
                select(Run.id)
                .where(
                    Run.workflow_id == workflow_id,
                    Run.status.in_([RunStatus.pending, RunStatus.running]),
                )
                .limit(1)
            ).first()
            if active_run is not None:
                raise WorkflowHasActiveRuns(
                    f"Workflow {_workflow_ref(workflow_id)} has active runs"
                )

        self.session.exec(delete(LogEntry).where(LogEntry.run_id.in_(run_ids)))
        self.session.exec(delete(RunNode).where(RunNode.run_id.in_(run_ids)))
        self.session.exec(delete(Run).where(Run.id.in_(run_ids)))
        self.session.commit()
        return len(run_ids)

    # Run
    def create_run(self, run: Run) -> Run:
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: str) -> Optional[Run]:
        # Expire the session cache so concurrent writes from other sessions are visible.
        self.session.expire_all()
        return self.session.get(Run, run_id)

    def refresh_run(self, run_id: str) -> Optional[Run]:
        run = self.session.get(Run, run_id)
        if run is not None:
            self.session.refresh(run)
        return run

    def list_runs(self) -> List[Run]:
        statement = select(Run).order_by(Run.created_at.desc())
        return list(self.session.exec(statement).all())

    def list_children(self, parent_run_id: str) -> List[Run]:
        statement = (
            select(Run).where(Run.parent_run_id == parent_run_id).order_by(Run.created_at.desc())
        )
        return list(self.session.exec(statement).all())

    def list_runs_paginated(
        self,
        offset: int,
        limit: int,
        status: list[str] | None = None,
        workflow_id: str | None = None,
        source: list[str] | None = None,
        branch: str | None = None,
    ) -> tuple:
        """Return a page of runs and the total count using SQL LIMIT/OFFSET."""
        filters = []
        count_statement = select(func.count()).select_from(Run)

        if status:
            filters.append(Run.status.in_(status))

        if workflow_id:
            filters.append(Run.workflow_id == workflow_id)

        if source:
            filters.append(Run.source.in_(source))

        if branch:
            filters.append(Run.branch == branch)

        if filters:
            count_statement = count_statement.where(*filters)

        eval_totals = (
            select(
                RunNode.run_id.label("run_id"),
                func.coalesce(
                    func.sum(case((RunNode.eval_passed.is_(True), 1), else_=0)),
                    0,
                ).label("eval_pass_count"),
                func.coalesce(
                    func.sum(case((RunNode.eval_passed.is_not(None), 1), else_=0)),
                    0,
                ).label("eval_total_count"),
            )
            .group_by(RunNode.run_id)
            .subquery()
        )
        statement = (
            select(
                Run,
                func.row_number()
                .over(partition_by=Run.workflow_id, order_by=Run.created_at.asc())
                .label("run_number"),
                func.coalesce(eval_totals.c.eval_pass_count, 0).label("eval_pass_count"),
                func.coalesce(eval_totals.c.eval_total_count, 0).label("eval_total_count"),
            )
            .select_from(Run)
            .outerjoin(eval_totals, eval_totals.c.run_id == Run.id)
            .order_by(Run.created_at.desc())
        )

        if filters:
            statement = statement.where(*filters)

        total = self.session.exec(count_statement).one()
        rows = self.session.exec(statement.offset(offset).limit(limit)).all()

        items = []
        for run, run_number, eval_pass_count, eval_total_count in rows:
            eval_total = int(eval_total_count or 0)
            eval_pass_pct = None
            if eval_total > 0:
                eval_pass_pct = float(eval_pass_count or 0) / eval_total * 100

            run.__dict__["run_number"] = int(run_number or 0)
            run.__dict__["eval_pass_pct"] = eval_pass_pct
            items.append(run)

        return items, total

    @staticmethod
    def _eval_health(eval_pass_pct: float | None) -> str | None:
        if eval_pass_pct is None:
            return None
        if eval_pass_pct >= 90:
            return "success"
        if eval_pass_pct >= 75:
            return "warning"
        return "danger"

    def _count_regressions_for_workflow(self, workflow_id: str) -> int:
        """Count comparison-based regressions for a workflow.

        A regression is a node whose eval_passed went from True to False between
        consecutive runs, for the same node_id and soul_version.
        """
        runs_stmt = (
            select(Run)
            .where(Run.workflow_id == workflow_id, Run.source != "simulation")
            .order_by(Run.created_at.asc())
        )
        runs = list(self.session.exec(runs_stmt).all())
        if len(runs) < 2:
            return 0

        regression_count = 0
        prev_nodes_map: dict[str, RunNode] = {}

        for run in runs:
            nodes = list(self.session.exec(select(RunNode).where(RunNode.run_id == run.id)).all())

            curr_nodes_map: dict[str, RunNode] = {}
            for node in nodes:
                if node.soul_version is not None:
                    key = node.node_id
                    curr_nodes_map[key] = node

                    prev_node = prev_nodes_map.get(key)
                    if (
                        prev_node is not None
                        and prev_node.soul_version == node.soul_version
                        and prev_node.eval_passed is True
                        and node.eval_passed is False
                    ):
                        regression_count += 1

            # Update previous node map: only track nodes with soul_version
            prev_nodes_map = curr_nodes_map

        return regression_count

    def get_workflow_health_metrics(self, workflow_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not workflow_ids:
            return {}

        run_totals = (
            select(
                Run.workflow_id.label("workflow_id"),
                func.count(Run.id).label("run_count"),
                func.coalesce(func.sum(Run.total_cost_usd), 0.0).label("total_cost_usd"),
            )
            .where(Run.workflow_id.in_(workflow_ids), Run.source != "simulation")
            .group_by(Run.workflow_id)
            .subquery()
        )
        eval_totals = (
            select(
                Run.workflow_id.label("workflow_id"),
                func.coalesce(
                    func.sum(case((RunNode.eval_passed.is_(True), 1), else_=0)),
                    0,
                ).label("eval_pass_count"),
                func.coalesce(
                    func.sum(case((RunNode.eval_passed.is_not(None), 1), else_=0)),
                    0,
                ).label("eval_total_count"),
            )
            .select_from(Run)
            .join(RunNode, RunNode.run_id == Run.id, isouter=True)
            .where(Run.workflow_id.in_(workflow_ids), Run.source != "simulation")
            .group_by(Run.workflow_id)
            .subquery()
        )
        statement = select(
            run_totals.c.workflow_id,
            run_totals.c.run_count,
            run_totals.c.total_cost_usd,
            func.coalesce(eval_totals.c.eval_pass_count, 0).label("eval_pass_count"),
            func.coalesce(eval_totals.c.eval_total_count, 0).label("eval_total_count"),
        ).select_from(
            run_totals.outerjoin(eval_totals, eval_totals.c.workflow_id == run_totals.c.workflow_id)
        )

        metrics: dict[str, dict[str, Any]] = {}
        for row in self.session.exec(statement):
            eval_total_count = int(row.eval_total_count or 0)
            eval_pass_pct = None
            if eval_total_count > 0:
                eval_pass_pct = float(row.eval_pass_count) / eval_total_count * 100

            metrics[row.workflow_id] = {
                "run_count": int(row.run_count or 0),
                "eval_pass_pct": eval_pass_pct,
                "eval_health": self._eval_health(eval_pass_pct),
                "total_cost_usd": float(row.total_cost_usd or 0.0),
                "regression_count": self._count_regressions_for_workflow(row.workflow_id),
            }

        return metrics

    def update_run(self, run: Run) -> Run:
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    # RunNode
    def create_node(self, node: RunNode) -> RunNode:
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        return node

    def get_node(self, node_id: str) -> Optional[RunNode]:  # composite id {run_id}:{node_id}
        return self.session.get(RunNode, node_id)

    def list_nodes_for_run(self, run_id: str) -> List[RunNode]:
        statement = select(RunNode).where(RunNode.run_id == run_id).order_by(RunNode.created_at)
        return list(self.session.exec(statement).all())

    def list_nodes_for_soul(self, soul_id: str) -> List[RunNode]:
        statement = select(RunNode).where(RunNode.soul_id == soul_id).order_by(RunNode.created_at)
        return list(self.session.exec(statement).all())

    def update_node(self, node: RunNode) -> RunNode:
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        return node

    # LogEntry
    def create_log(self, log_entry: LogEntry) -> LogEntry:
        self.session.add(log_entry)
        self.session.commit()
        self.session.refresh(log_entry)
        return log_entry

    def list_logs_for_run(self, run_id: str) -> List[LogEntry]:
        statement = select(LogEntry).where(LogEntry.run_id == run_id).order_by(LogEntry.timestamp)
        return list(self.session.exec(statement).all())

    # Baseline
    def get_baseline(
        self, soul_id: str, soul_version: str, limit: int = 100
    ) -> Optional[BaselineStats]:
        """Compute baseline statistics for a given soul_id + soul_version.

        Returns None when no matching RunNode records exist.
        """
        statement = (
            select(RunNode)
            .where(RunNode.soul_id == soul_id, RunNode.soul_version == soul_version)
            .order_by(RunNode.created_at.desc())
            .limit(limit)
        )
        nodes = list(self.session.exec(statement).all())
        if not nodes:
            return None

        total_cost = sum(n.cost_usd for n in nodes)
        total_tokens = sum((n.tokens or {}).get("total", 0) for n in nodes)
        scores = [n.eval_score for n in nodes if n.eval_score is not None]

        return BaselineStats(
            avg_cost=total_cost / len(nodes),
            avg_tokens=total_tokens / len(nodes),
            avg_score=sum(scores) / len(scores) if scores else None,
            run_count=len(nodes),
        )
