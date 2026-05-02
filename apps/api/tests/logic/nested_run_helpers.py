from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def create_run(
    session: Session,
    *,
    run_id: str,
    workflow_id: str = "nested_parent_workflow",
    workflow_name: str = "Nested parent workflow",
    status: RunStatus = RunStatus.running,
    parent_run_id: str | None = None,
    parent_node_id: str | None = None,
    root_run_id: str | None = None,
    depth: int = 0,
    warnings_json: list[dict[str, str | None]] | None = None,
    branch: str = "main",
    source: str = "manual",
    commit_sha: str | None = None,
) -> Run:
    run = Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        status=status,
        task_json="{}",
        parent_run_id=parent_run_id,
        parent_node_id=parent_node_id,
        root_run_id=root_run_id,
        depth=depth,
        warnings_json=warnings_json,
        branch=branch,
        source=source,
        commit_sha=commit_sha,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
