"""Red tests for RUN-956 run write/read-model ownership.

These tests stay on public service behavior while requiring a configurable
analytics/read-model seam:

- paginated run listing must be able to come from a read-model owner without
  moving soft-delete/get behavior off the write repository
- workflow health aggregation must be swappable independently from CRUD/write
  behavior while preserving the existing health payload
- baseline-backed eval deltas must be readable from a separate analytics owner
  without changing the public EvalService response
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from runsight_api.domain.entities.run import BaselineStats, NodeStatus, Run, RunNode, RunStatus
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.eval_service import EvalService
from runsight_api.logic.services.run_service import RunService
from runsight_api.logic.services.workflow_service import WorkflowService


def _make_run(
    run_id: str,
    *,
    workflow_id: str = "wf_956",
    workflow_name: str = "Workflow 956",
    created_at: float = 100.0,
    source: str = "manual",
    branch: str = "main",
    run_number: int | None = None,
    eval_pass_pct: float | None = None,
    deleted_at: float | None = None,
) -> Run:
    run = Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        status=RunStatus.completed,
        task_json="{}",
        created_at=created_at,
        updated_at=created_at,
        source=source,
        branch=branch,
        deleted_at=deleted_at,
    )
    if run_number is not None:
        run.__dict__["run_number"] = run_number
    run.__dict__["eval_pass_pct"] = eval_pass_pct
    return run


def _configure_read_model(service_cls, *, read_model, **kwargs):
    init = inspect.signature(service_cls.__init__)
    constructor_names = []

    token_groups = (
        "analytics",
        "query",
        "queries",
        "reader",
        "read_model",
        "readmodel",
        "report",
        "projection",
        "metrics",
    )
    for name in init.parameters:
        if name == "self" or name in kwargs:
            continue
        lowered = name.lower()
        if any(token in lowered for token in token_groups):
            kwargs[name] = read_model
            constructor_names.append(name)

    bundle_names = (
        "components",
        "collaborators",
        "dependencies",
        "deps",
        "ports",
        "repositories",
        "services",
    )
    if not constructor_names:
        for name in bundle_names:
            if name in init.parameters and name not in kwargs:
                kwargs[name] = SimpleNamespace(
                    analytics=read_model,
                    analytics_repo=read_model,
                    query_repo=read_model,
                    read_model=read_model,
                    run_queries=read_model,
                    reporting=read_model,
                    metrics=read_model,
                )
                constructor_names.append(name)
                break

    service = service_cls(**kwargs)
    if constructor_names:
        return service

    setter_names = (
        "set_read_model",
        "set_query_repo",
        "set_queries",
        "set_analytics_repo",
        "configure_read_model",
        "configure_query_repo",
        "configure_analytics_repo",
    )
    for name in setter_names:
        setter = getattr(service, name, None)
        if callable(setter):
            setter(read_model)
            return service

    attr_names = (
        "read_model",
        "_read_model",
        "query_repo",
        "_query_repo",
        "queries",
        "_queries",
        "analytics_repo",
        "_analytics_repo",
        "analytics",
        "_analytics",
        "reporting",
        "_reporting",
        "metrics",
        "_metrics",
    )
    for name in attr_names:
        if hasattr(service, name):
            setattr(service, name, read_model)
            return service

    for bundle_name in bundle_names:
        bundle = getattr(service, bundle_name, None)
        if bundle is None:
            continue
        for name in attr_names:
            if hasattr(bundle, name):
                setattr(bundle, name, read_model)
                return service

    raise AssertionError(
        f"{service_cls.__name__} must expose a configurable analytics/read-model seam"
    )


class _RunWriteRepositoryDouble:
    def __init__(self, runs: list[Run]):
        self._runs = {run.id: run for run in runs}

    def get_run(self, run_id: str) -> Run | None:
        run = self._runs.get(run_id)
        if run is None or run.deleted_at is not None:
            return None
        return run

    def delete_run(self, run_id: str) -> str | None:
        run = self._runs.get(run_id)
        if run is None or run.deleted_at is not None:
            return None
        run.deleted_at = 999.0
        return run_id


class _RunReadModelDouble:
    def __init__(
        self,
        *,
        paginated_result: tuple[list[Run], int] | None = None,
        workflow_health: dict[str, dict] | None = None,
        baselines: dict[tuple[str, str], BaselineStats | None] | None = None,
    ):
        self.paginated_result = paginated_result or ([], 0)
        self.workflow_health = workflow_health or {}
        self.baselines = baselines or {}
        self.paginated_calls: list[dict[str, object]] = []
        self.health_calls: list[list[str]] = []
        self.baseline_calls: list[tuple[str, str]] = []

    def list_runs_paginated(
        self,
        offset: int,
        limit: int,
        status: list[str] | None = None,
        workflow_id: str | None = None,
        source: list[str] | None = None,
        branch: str | None = None,
    ) -> tuple[list[Run], int]:
        self.paginated_calls.append(
            {
                "offset": offset,
                "limit": limit,
                "status": status,
                "workflow_id": workflow_id,
                "source": source,
                "branch": branch,
            }
        )
        return self.paginated_result

    def get_workflow_health_metrics(self, workflow_ids: list[str]) -> dict[str, dict]:
        self.health_calls.append(list(workflow_ids))
        return self.workflow_health

    def get_baseline(self, soul_id: str, soul_version: str) -> BaselineStats | None:
        self.baseline_calls.append((soul_id, soul_version))
        return self.baselines.get((soul_id, soul_version))


class _WorkflowRepositoryDouble:
    def __init__(self, workflows: list[WorkflowEntity]):
        self._workflows = workflows

    def list_all(self) -> list[WorkflowEntity]:
        return list(self._workflows)

    def get_block_count(self, workflow_id: str) -> int:
        return {"wf_alpha": 7, "wf_beta": 2}[workflow_id]

    def get_file_mtime(self, workflow_id: str) -> float:
        return {"wf_alpha": 1711900000.0, "wf_beta": 1711900500.0}[workflow_id]


def test_run_service_pages_through_read_model_while_delete_stays_on_write_repo() -> None:
    visible = _make_run(
        "run_visible",
        run_number=7,
        eval_pass_pct=66.67,
    )
    deleted = _make_run("run_deleted")
    write_repo = _RunWriteRepositoryDouble([visible, deleted])
    read_model = _RunReadModelDouble(paginated_result=([visible], 1))
    service = _configure_read_model(
        RunService,
        run_repo=write_repo,
        workflow_repo=Mock(),
        read_model=read_model,
    )

    items, total = service.list_runs_paginated(
        offset=10,
        limit=5,
        status=["completed"],
        workflow_id="wf_956",
        source=["manual"],
        branch="main",
    )

    assert total == 1
    assert [run.id for run in items] == ["run_visible"]
    assert items[0].run_number == 7
    assert items[0].eval_pass_pct == pytest.approx(66.67)
    assert read_model.paginated_calls == [
        {
            "offset": 10,
            "limit": 5,
            "status": ["completed"],
            "workflow_id": "wf_956",
            "source": ["manual"],
            "branch": "main",
        }
    ]

    assert service.delete_run("run_deleted") == "run_deleted"
    assert service.get_run("run_deleted") is None


def test_workflow_service_uses_read_model_health_metrics_without_changing_payload() -> None:
    workflows = [
        WorkflowEntity(kind="workflow", id="wf_alpha", name="Alpha", enabled=True),
        WorkflowEntity(kind="workflow", id="wf_beta", name="Beta", enabled=False),
    ]
    workflow_repo = _WorkflowRepositoryDouble(workflows)
    read_model = _RunReadModelDouble(
        workflow_health={
            "wf_alpha": {
                "run_count": 3,
                "eval_pass_pct": 50.0,
                "eval_health": "danger",
                "total_cost_usd": 2.75,
                "regression_count": 2,
            }
        }
    )
    git_service = Mock()
    git_service.current_branch.return_value = "main"
    git_service.get_sha.side_effect = lambda branch, path: {
        "custom/workflows/wf_alpha.yaml": "alpha_sha",
        "custom/workflows/wf_beta.yaml": "beta_sha",
    }[path]
    service = _configure_read_model(
        WorkflowService,
        workflow_repo=workflow_repo,
        run_repo=Mock(),
        git_service=git_service,
        read_model=read_model,
    )

    result = service.list_workflows()

    assert [workflow.id for workflow in result] == ["wf_alpha", "wf_beta"]
    assert read_model.health_calls == [["wf_alpha", "wf_beta"]]

    alpha = result[0]
    assert alpha.block_count == 7
    assert alpha.modified_at == pytest.approx(1711900000.0)
    assert alpha.commit_sha == "alpha_sha"
    assert alpha.health == {
        "run_count": 3,
        "eval_pass_pct": 50.0,
        "eval_health": "danger",
        "total_cost_usd": 2.75,
        "regression_count": 2,
    }

    beta = result[1]
    assert beta.block_count == 2
    assert beta.modified_at == pytest.approx(1711900500.0)
    assert beta.commit_sha == "beta_sha"
    assert beta.health == {
        "run_count": 0,
        "eval_pass_pct": None,
        "eval_health": None,
        "total_cost_usd": 0.0,
        "regression_count": 0,
    }


def test_eval_service_uses_separate_baseline_reader_without_changing_delta_behavior() -> None:
    run = _make_run("run_eval", workflow_id="wf_eval", workflow_name="Eval Flow")
    node = RunNode(
        id="run_eval:draft",
        run_id="run_eval",
        node_id="draft",
        block_type="llm",
        status=NodeStatus.completed,
        soul_id="writer",
        soul_version="sha:v1",
        eval_score=0.9,
        eval_passed=True,
        cost_usd=0.3,
        tokens={"prompt": 120, "completion": 180, "total": 300},
    )
    write_repo = SimpleNamespace(
        get_run=lambda run_id: run if run_id == "run_eval" else None,
        list_nodes_for_run=lambda run_id: [node] if run_id == "run_eval" else [],
    )
    read_model = _RunReadModelDouble(
        baselines={
            ("writer", "sha:v1"): BaselineStats(
                avg_cost=0.2,
                avg_tokens=200.0,
                avg_score=0.7,
                run_count=4,
            )
        }
    )
    service = _configure_read_model(EvalService, run_repo=write_repo, read_model=read_model)

    result = service.get_run_eval("run_eval")

    assert result is not None
    assert result.run_id == "run_eval"
    assert result.aggregate_score == pytest.approx(0.9)
    assert result.passed is True
    assert len(result.nodes) == 1
    assert read_model.baseline_calls == [("writer", "sha:v1")]

    delta = result.nodes[0].delta
    assert delta is not None
    assert delta.cost_pct == pytest.approx(50.0)
    assert delta.tokens_pct == pytest.approx(50.0)
    assert delta.score_delta == pytest.approx(0.2)
    assert delta.baseline_run_count == 4
