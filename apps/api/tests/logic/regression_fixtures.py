"""Regression logic test fixtures."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode


def make_mock_run(
    run_id: str,
    *,
    workflow_id: str = "regression-workflow",
    workflow_name: str = "Research Flow",
    source: str = "manual",
    branch: str = "main",
    created_at: float = 100.0,
) -> Mock:
    run = Mock()
    run.id = run_id
    run.workflow_id = workflow_id
    run.workflow_name = workflow_name
    run.source = source
    run.branch = branch
    run.created_at = created_at
    return run


def make_mock_node(
    *,
    node_id: str = "analyze",
    run_id: str = "baseline-regression-run",
    soul_id: str | None = "researcher_v1",
    soul_version: str | None = "sha256:abc",
    eval_score: float | None = 0.95,
    eval_passed: bool | None = True,
    cost_usd: float = 0.005,
    tokens: dict | None = None,
    created_at: float = 100.0,
) -> Mock:
    node = Mock()
    node.node_id = node_id
    node.run_id = run_id
    node.soul_id = soul_id
    node.soul_version = soul_version
    node.eval_score = eval_score
    node.eval_passed = eval_passed
    node.cost_usd = cost_usd
    node.tokens = tokens or {"prompt": 100, "completion": 50, "total": 150}
    node.created_at = created_at
    return node


@pytest.fixture(name="db_session")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def seed_run(
    session: Session,
    run_id: str,
    *,
    workflow_id: str,
    branch: str,
    source: str = "manual",
    total_cost_usd: float = 0.0,
) -> None:
    run = Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=f"Workflow {workflow_id}",
        task_json="{}",
        branch=branch,
        source=source,
        total_cost_usd=total_cost_usd,
    )
    session.add(run)


def seed_node(
    session: Session,
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool | None,
    soul_version: str | None = None,
    eval_score: float | None = None,
    cost_usd: float = 0.0,
) -> None:
    node = RunNode(
        id=f"{run_id}:{node_id}",
        run_id=run_id,
        node_id=node_id,
        block_type="llm",
        status="completed",
        eval_passed=eval_passed,
        soul_version=soul_version,
        eval_score=eval_score,
        cost_usd=cost_usd,
    )
    session.add(node)
