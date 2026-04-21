from typing import Any, List, Optional

from sqlmodel import Session, delete, select

from runsight_core.identity import EntityKind, EntityRef

from ...domain.entities.log import LogEntry
from ...domain.entities.run import BaselineStats, Run, RunNode, RunStatus
from ...domain.errors import RunHasActiveExecution, RunHasChildren, WorkflowHasActiveRuns
from .run_read_model import RunReadModel


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


class RunRepository:
    def __init__(self, session: Session):
        self.session = session
        self.read_model = RunReadModel(session)

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

    def delete_run(self, run_id: str) -> Optional[str]:
        run = self.session.get(Run, run_id)
        if run is None or run.deleted_at is not None:
            return None
        if run.status in [RunStatus.pending, RunStatus.running]:
            raise RunHasActiveExecution(f"Run {run_id} has active execution")
        children = self.list_children(run_id)
        if children:
            raise RunHasChildren(
                f"Run {run_id} has {len(children)} child run(s) and cannot be deleted"
            )
        import time as _time

        run.deleted_at = _time.time()
        self.session.add(run)
        self.session.commit()
        return run_id

    # Run
    def create_run(self, run: Run) -> Run:
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: str) -> Optional[Run]:
        # Expire the session cache so concurrent writes from other sessions are visible.
        self.session.expire_all()
        run = self.session.get(Run, run_id)
        if run is not None and run.deleted_at is not None:
            return None
        return run

    def refresh_run(self, run_id: str) -> Optional[Run]:
        run = self.session.get(Run, run_id)
        if run is not None:
            self.session.refresh(run)
        return run

    def list_runs(self, limit: int | None = None) -> List[Run]:
        statement = select(Run).where(Run.deleted_at.is_(None)).order_by(Run.created_at.desc())
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def list_children(self, parent_run_id: str) -> List[Run]:
        statement = (
            select(Run)
            .where(Run.parent_run_id == parent_run_id, Run.deleted_at.is_(None))
            .order_by(Run.created_at.desc())
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
        return self.read_model.list_runs_paginated(
            offset,
            limit,
            status=status,
            workflow_id=workflow_id,
            source=source,
            branch=branch,
        )

    @staticmethod
    def _eval_health(eval_pass_pct: float | None) -> str | None:
        return RunReadModel._eval_health(eval_pass_pct)

    def _count_regressions_for_workflow(self, workflow_id: str) -> int:
        return self.read_model._count_regressions_for_workflow(workflow_id)

    def get_workflow_health_metrics(self, workflow_ids: list[str]) -> dict[str, dict[str, Any]]:
        return self.read_model.get_workflow_health_metrics(workflow_ids)

    def _count_regressions_batch(self, workflow_ids: list[str]) -> dict[str, int]:
        return self.read_model._count_regressions_batch(workflow_ids)

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
        return self.read_model.get_baseline(soul_id, soul_version, limit=limit)
