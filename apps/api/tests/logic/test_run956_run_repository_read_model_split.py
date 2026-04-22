"""Strict read-model ownership tests for run, workflow, and eval services."""

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
from runsight_api.transport import deps as transport_deps


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


class _RunReadModelDouble:
    def __init__(
        self,
        *,
        paginated_result: tuple[list[Run], int] | None = None,
        workflow_health: dict[str, dict] | None = None,
        baselines: dict[tuple[str, str], BaselineStats | None] | None = None,
    ) -> None:
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
    def __init__(self, workflows: list[WorkflowEntity]) -> None:
        self._workflows = workflows

    def list_all(self) -> list[WorkflowEntity]:
        return list(self._workflows)

    def get_block_count(self, workflow_id: str) -> int:
        return {"wf_alpha": 7, "wf_beta": 2}[workflow_id]

    def get_file_mtime(self, workflow_id: str) -> float:
        return {"wf_alpha": 1711900000.0, "wf_beta": 1711900500.0}[workflow_id]


@pytest.mark.parametrize(
    ("service_cls", "forbidden_fragments"),
    [
        (
            RunService,
            [
                "def _resolve_run_read_model(",
                'getattr(self.run_repo, "list_runs_paginated", None)',
                'session = getattr(self.run_repo, "session", None)',
                "RunReadModel(session)",
            ],
        ),
        (
            WorkflowService,
            [
                "def _resolve_run_read_model(",
                'getattr(self.run_repo, "get_workflow_health_metrics", None)',
                'session = getattr(self.run_repo, "session", None)',
                "RunReadModel(session)",
            ],
        ),
        (
            EvalService,
            [
                "def _resolve_run_read_model(",
                'baseline_getter = getattr(self.run_repo, "get_baseline", None)',
                'session = getattr(self.run_repo, "session", None)',
                "RunReadModel(session)",
            ],
        ),
    ],
)
def test_services_do_not_probe_run_repo_or_construct_read_models_implicitly(
    service_cls, forbidden_fragments
) -> None:
    source = inspect.getsource(service_cls)

    for fragment in forbidden_fragments:
        assert fragment not in source, (
            f"{service_cls.__name__} must use only the explicit run_read_model collaborator; "
            f"found forbidden fallback fragment: {fragment!r}"
        )


def test_run_service_uses_only_explicit_run_read_model_for_paginated_queries() -> None:
    visible = _make_run("run_visible", run_number=7, eval_pass_pct=66.67)
    read_model = _RunReadModelDouble(paginated_result=([visible], 1))

    def _unexpected_repo_pagination(*args, **kwargs):
        raise AssertionError("RunService must not read paginated runs from run_repo")

    run_repo = SimpleNamespace(
        get_run=lambda run_id: visible if run_id == visible.id else None,
        delete_run=lambda run_id: run_id,
        list_runs_paginated=_unexpected_repo_pagination,
        session=object(),
    )
    service = RunService(run_repo=run_repo, workflow_repo=Mock(), run_read_model=read_model)

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


def test_workflow_service_uses_only_explicit_run_read_model_for_health_queries() -> None:
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

    def _unexpected_health_query(*args, **kwargs):
        raise AssertionError("WorkflowService must not read workflow health from run_repo")

    run_repo = SimpleNamespace(
        get_workflow_health_metrics=_unexpected_health_query,
        session=object(),
    )
    git_service = Mock()
    git_service.current_branch.return_value = "main"
    git_service.get_sha.side_effect = lambda branch, path: {
        "custom/workflows/wf_alpha.yaml": "alpha_sha",
        "custom/workflows/wf_beta.yaml": "beta_sha",
    }[path]

    service = WorkflowService(
        workflow_repo=workflow_repo,
        run_repo=run_repo,
        git_service=git_service,
        run_read_model=read_model,
    )

    result = service.list_workflows()

    assert [workflow.id for workflow in result] == ["wf_alpha", "wf_beta"]
    assert read_model.health_calls == [["wf_alpha", "wf_beta"]]
    assert result[0].health["regression_count"] == 2
    assert result[1].health["regression_count"] == 0


def test_eval_service_uses_only_explicit_run_read_model_for_baselines() -> None:
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

    def _unexpected_baseline(*args, **kwargs):
        raise AssertionError("EvalService must not read baselines from run_repo")

    run_repo = SimpleNamespace(
        get_run=lambda run_id: run if run_id == "run_eval" else None,
        list_nodes_for_run=lambda run_id: [node] if run_id == "run_eval" else [],
        get_baseline=_unexpected_baseline,
        session=object(),
    )
    service = EvalService(run_repo=run_repo, run_read_model=read_model)

    result = service.get_run_eval("run_eval")

    assert result is not None
    assert result.run_id == "run_eval"
    assert read_model.baseline_calls == [("writer", "sha:v1")]
    assert result.nodes[0].delta is not None
    assert result.nodes[0].delta.baseline_run_count == 4


@pytest.mark.parametrize(
    ("factory", "expected_dependencies"),
    [
        (transport_deps.get_run_service, {"run_repo", "workflow_repo", "run_read_model"}),
        (
            transport_deps.get_workflow_service,
            {"workflow_repo", "run_repo", "run_read_model", "git_service"},
        ),
        (transport_deps.get_eval_service, {"run_repo", "run_read_model"}),
    ],
)
def test_dependency_factories_require_explicit_run_read_model(
    factory, expected_dependencies
) -> None:
    signature = inspect.signature(factory)

    assert expected_dependencies.issubset(signature.parameters), (
        f"{factory.__name__} must explicitly depend on run_read_model rather than hiding "
        "read-model construction inside the service"
    )
