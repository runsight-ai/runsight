import uuid
import time
import json
from typing import List, Optional, Dict, Any

from ...domain.entities.run import Run, RunNode, RunStatus
from ...domain.entities.log import LogEntry
from ...data.repositories.run_repo import RunRepository
from ...data.filesystem.workflow_repo import WorkflowRepository
from ...domain.errors import WorkflowNotFound, RunNotFound


class RunService:
    def __init__(self, run_repo: RunRepository, workflow_repo: WorkflowRepository):
        self.run_repo = run_repo
        self.workflow_repo = workflow_repo

    def get_run(self, run_id: str) -> Optional[Run]:
        return self.run_repo.get_run(run_id)

    def list_runs(self) -> List[Run]:
        return self.run_repo.list_runs()

    def get_run_nodes(self, run_id: str) -> List[RunNode]:
        return self.run_repo.list_nodes_for_run(run_id)

    def get_run_logs(self, run_id: str) -> List[LogEntry]:
        return self.run_repo.list_logs_for_run(run_id)

    def create_run(self, workflow_id: str, task_data: Dict[str, Any]) -> Run:
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise WorkflowNotFound(f"Workflow {workflow_id} not found")

        run_id = f"run_{uuid.uuid4().hex[:12]}"

        run = Run(
            id=run_id,
            workflow_id=workflow_id,
            workflow_name=workflow.name if isinstance(workflow.name, str) else workflow.id,
            status=RunStatus.pending,
            task_json=json.dumps(task_data),
        )
        self.run_repo.create_run(run)

        # We don't pre-populate nodes here since workflow execution is externalized or done via observers
        # In a real setup, we might parse the workflow YAML and create initial RunNode records
        return run

    def cancel_run(self, run_id: str) -> Run:
        run = self.get_run(run_id)
        if not run:
            raise RunNotFound(f"Run {run_id} not found")

        run.status = RunStatus.cancelled
        run.cancelled_reason = "Cancelled by user"
        run.completed_at = time.time()
        if run.started_at:
            run.duration_s = run.completed_at - run.started_at

        return self.run_repo.update_run(run)

    def get_node_summary(self, run_id: str) -> Dict[str, Any]:
        """Read-only summary of run nodes (replaces compute_summaries)."""
        nodes = self.get_run_nodes(run_id)

        total_cost = sum(n.cost_usd for n in nodes)
        total_tokens = sum((n.tokens or {}).get("total", 0) for n in nodes)

        completed = sum(1 for n in nodes if n.status == "completed")
        running = sum(1 for n in nodes if n.status == "running")
        pending = sum(1 for n in nodes if n.status == "pending")
        failed = sum(1 for n in nodes if n.status == "failed")

        return {
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "nodes_count": len(nodes),
            "total": len(nodes),
            "completed": completed,
            "running": running,
            "pending": pending,
            "failed": failed,
        }
