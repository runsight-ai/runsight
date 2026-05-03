from __future__ import annotations

import copy
import time
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from runsight_core.identity import EntityKind, EntityRef

from ...data.repositories.run_repo import RunRepository
from ...domain.entities.log import LogEntry
from ...domain.entities.run import NodeStatus, Run, RunNode, RunStatus, validate_transition
from ...domain.errors import RunNotFound, WorkflowNotFound

if TYPE_CHECKING:
    from ...data.filesystem.workflow_repo import WorkflowRepository
    from ...data.repositories.run_read_model import RunReadModel


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


def _snapshot_dict(value: Any) -> Optional[Dict[str, Any]]:
    return copy.deepcopy(value) if isinstance(value, dict) else None


def _workflow_input_snapshots(
    workflow_id: str,
    workflow: Any,
    inputs: Mapping[str, Any],
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    from .execution_service import PreparedRunInputs

    if not isinstance(inputs, PreparedRunInputs):
        raise TypeError("RunService.create_run requires PreparedRunInputs")

    workflow_inputs = _snapshot_dict(getattr(inputs, "workflow_inputs", None))
    workflow_input_schema = _snapshot_dict(getattr(inputs, "workflow_input_schema", None))
    if workflow_inputs is not None and workflow_input_schema is not None:
        return workflow_inputs, workflow_input_schema
    raise TypeError("PreparedRunInputs must include workflow input snapshots")


class RunService:
    def __init__(
        self,
        run_repo: RunRepository,
        workflow_repo: WorkflowRepository,
        run_read_model: "RunReadModel | None" = None,
    ):
        self.run_repo = run_repo
        self.workflow_repo = workflow_repo
        self.run_read_model = run_read_model

    def get_run(self, run_id: str) -> Optional[Run]:
        return self.run_repo.get_run(run_id)

    def refresh_run(self, run_id: str) -> Optional[Run]:
        return self.run_repo.refresh_run(run_id)

    def list_runs(self) -> List[Run]:
        return self.run_repo.list_runs()

    def list_children(self, parent_run_id: str) -> List[Run]:
        return self.run_repo.list_children(parent_run_id)

    def list_runs_paginated(
        self,
        offset: int,
        limit: int,
        status: Optional[List[str]] = None,
        workflow_id: Optional[str] = None,
        source: Optional[List[str]] = None,
        branch: Optional[str] = None,
    ) -> Tuple[List[Run], int]:
        """Return a page of runs and total count via SQL pagination."""
        if self.run_read_model is None:
            raise RuntimeError("RunService requires a run read model for paginated run queries")
        return self.run_read_model.list_runs_paginated(
            offset, limit, status=status, workflow_id=workflow_id, source=source, branch=branch
        )

    def get_run_nodes(self, run_id: str) -> List[RunNode]:
        return self.run_repo.list_nodes_for_run(run_id)

    def get_run_logs(self, run_id: str) -> List[LogEntry]:
        return self.run_repo.list_logs_for_run(run_id)

    def create_run(
        self,
        workflow_id: str,
        inputs: Mapping[str, Any],
        *,
        branch: str,
        source: str = "manual",
        source_correlation_id: str | None = None,
        source_metadata: Mapping[str, Any] | None = None,
        workflow_snapshot: Any | None = None,
    ) -> Run:
        workflow = (
            workflow_snapshot
            if workflow_snapshot is not None
            else self.workflow_repo.get_by_id(workflow_id)
        )
        if not workflow:
            raise WorkflowNotFound(f"Workflow {_workflow_ref(workflow_id)} not found")

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        workflow_warnings = getattr(workflow, "warnings", None)
        warnings_json: Optional[List[Dict[str, Any]]] = None
        if isinstance(workflow_warnings, list) and workflow_warnings:
            warnings_json = copy.deepcopy(workflow_warnings)
        workflow_inputs, workflow_input_schema = _workflow_input_snapshots(
            workflow_id,
            workflow,
            inputs,
        )

        run = Run(
            id=run_id,
            workflow_id=workflow_id,
            workflow_name=workflow.name if isinstance(workflow.name, str) else workflow.id,
            status=RunStatus.pending,
            task_json="{}",
            branch=branch,
            source=source,
            source_correlation_id=source_correlation_id,
            source_metadata=copy.deepcopy(dict(source_metadata or {})),
            warnings_json=warnings_json,
            workflow_inputs=workflow_inputs,
            workflow_input_schema=workflow_input_schema,
        )
        self.run_repo.create_run(run)

        # We don't pre-populate nodes here since workflow execution is externalized or done via observers
        # In a real setup, we might parse the workflow YAML and create initial RunNode records
        return run

    def delete_run(self, run_id: str) -> Optional[str]:
        return self.run_repo.delete_run(run_id)

    def cancel_run(self, run_id: str) -> Run:
        run = self.get_run(run_id)
        if not run:
            raise RunNotFound(f"Run {run_id} not found")

        validate_transition(run.status, RunStatus.cancelled)

        run.status = RunStatus.cancelled
        run.cancelled_reason = "Cancelled by user"
        run.completed_at = time.time()
        if run.started_at:
            run.duration_s = run.completed_at - run.started_at

        return self.run_repo.update_run(run)

    def fail_run(self, run_id: str, error: str) -> Run:
        run = self.get_run(run_id)
        if not run:
            raise RunNotFound(f"Run {run_id} not found")

        validate_transition(run.status, RunStatus.failed)

        completed_at = time.time()
        run.status = RunStatus.failed
        run.error = error
        run.completed_at = completed_at
        run.updated_at = completed_at
        if run.started_at:
            run.duration_s = completed_at - run.started_at

        return self.run_repo.update_run(run)

    def get_node_summary(self, run_id: str) -> Dict[str, Any]:
        """Read-only summary of run nodes (replaces compute_summaries)."""
        nodes = self.get_run_nodes(run_id)

        total_cost = sum(n.cost_usd for n in nodes)
        total_tokens = sum((n.tokens or {}).get("total", 0) for n in nodes)
        eval_scores = [n.eval_score for n in nodes if n.eval_score is not None]

        completed = sum(1 for n in nodes if n.status == NodeStatus.completed)
        running = sum(1 for n in nodes if n.status == NodeStatus.running)
        pending = sum(1 for n in nodes if n.status == NodeStatus.pending)
        failed = sum(1 for n in nodes if n.status == NodeStatus.failed)

        return {
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "nodes_count": len(nodes),
            "total": len(nodes),
            "completed": completed,
            "running": running,
            "pending": pending,
            "failed": failed,
            "eval_score_avg": sum(eval_scores) / len(eval_scores) if eval_scores else None,
        }

    def get_node_summaries_batch(self, run_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch node summaries for multiple runs in a single batch."""
        result: Dict[str, Dict[str, Any]] = {}
        for run_id in run_ids:
            result[run_id] = self.get_node_summary(run_id)
        return result
