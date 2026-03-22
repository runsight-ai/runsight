from sqlmodel import Session, select, func
from typing import List, Optional
from ...domain.entities.run import Run, RunNode
from ...domain.entities.log import LogEntry


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

    def list_runs_paginated(self, offset: int, limit: int) -> tuple:
        """Return a page of runs and the total count using SQL LIMIT/OFFSET."""
        count_statement = select(func.count()).select_from(Run)
        total = self.session.exec(count_statement).one()

        statement = select(Run).order_by(Run.created_at.desc()).offset(offset).limit(limit)
        items = list(self.session.exec(statement).all())
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
