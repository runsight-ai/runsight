from typing import List, Optional

from sqlmodel import Session, func, select

from ...domain.entities.log import LogEntry
from ...domain.entities.run import BaselineStats, Run, RunNode


class RunRepository:
    def __init__(self, session: Session):
        self.session = session

    # Run
    def create_run(self, run: Run) -> Run:
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: str) -> Optional[Run]:
        return self.session.get(Run, run_id)

    def list_runs(self) -> List[Run]:
        statement = select(Run).order_by(Run.created_at.desc())
        return list(self.session.exec(statement).all())

    def list_runs_paginated(
        self,
        offset: int,
        limit: int,
        status: list[str] | None = None,
        workflow_id: str | None = None,
    ) -> tuple:
        """Return a page of runs and the total count using SQL LIMIT/OFFSET."""
        count_statement = select(func.count()).select_from(Run)
        statement = select(Run).order_by(Run.created_at.desc())

        if status:
            count_statement = count_statement.where(Run.status.in_(status))
            statement = statement.where(Run.status.in_(status))

        if workflow_id:
            count_statement = count_statement.where(Run.workflow_id == workflow_id)
            statement = statement.where(Run.workflow_id == workflow_id)

        total = self.session.exec(count_statement).one()
        items = list(self.session.exec(statement.offset(offset).limit(limit)).all())
        return items, total

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
