from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService, PreparedRunInputs
from runsight_core.redaction import RunRedactor

VALID_YAML = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "branch_aware_execution"
    / "branch-aware-workflow.yaml"
).read_text(encoding="utf-8")

WORKFLOW_ID = "branch-aware-workflow"
WORKFLOW_PATH = "/fake/workflows/branch-aware-workflow.yaml"


def prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=inputs,
        input_redactor=RunRedactor(),
    )


def branch_instruction() -> PreparedRunInputs:
    return prepared_inputs({"instruction": "run branch-aware workflow"})


def make_service(*, engine=None):
    """Return (service, run_repo, workflow_repo, provider_repo, git_service)."""
    run_repo = RunRepository(Session(engine)) if engine is not None else Mock()
    workflow_repo = Mock()
    provider_repo = Mock()
    git_service = Mock()

    workflow_entity = Mock()
    workflow_entity.yaml = VALID_YAML
    workflow_repo.get_by_id.return_value = workflow_entity
    workflow_repo._get_path.return_value = WORKFLOW_PATH

    provider_repo.list_all.return_value = []
    git_service.read_file.return_value = VALID_YAML
    git_service.get_sha.return_value = "abc123cafebabe"

    service = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=engine,
        git_service=git_service,
    )
    return service, run_repo, workflow_repo, provider_repo, git_service


def create_run_engine_with_branch_run(*, run_id: str, branch: str):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id=WORKFLOW_ID,
                workflow_name="Branch-aware workflow",
                status=RunStatus.pending,
                task_json="{}",
                branch=branch,
            )
        )
        session.commit()

    return engine
