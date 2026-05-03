import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.redaction import RunRedactor
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.logic.services.execution_service import PreparedRunInputs


def _prepared_inputs(inputs):
    return PreparedRunInputs(
        normalized_inputs=inputs,
        input_redactor=RunRedactor(),
    )


def test_execution_service_returns_sha_for_tracked_workflow_file():
    from runsight_api.logic.services.execution_service import ExecutionService

    fake_sha = "abc123def456789012345678901234567890abcd"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout=f"{fake_sha}\n")
        result = ExecutionService._get_workflow_commit_sha("/some/path/workflow.yaml")

    assert result == fake_sha
    mock_run.assert_called_once()


@pytest.mark.parametrize(
    "run_result, side_effect",
    [
        (Mock(returncode=128, stdout=""), None),
        (Mock(returncode=0, stdout=""), None),
        (None, FileNotFoundError("git not found")),
        (None, OSError("unexpected")),
    ],
)
def test_execution_service_returns_none_when_workflow_sha_cannot_be_resolved(
    run_result,
    side_effect,
):
    from runsight_api.logic.services.execution_service import ExecutionService

    with patch("subprocess.run", return_value=run_result, side_effect=side_effect):
        assert ExecutionService._get_workflow_commit_sha("/some/path/wf.yaml") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fake_sha, run_id",
    [
        ("aabbccddee1234567890aabbccddee1234567890", "run_sha_store"),
        (None, "run_sha_none"),
    ],
)
async def test_launch_execution_persists_resolved_commit_sha(fake_sha, run_id):
    from runsight_api.domain.entities.run import Run, RunStatus
    from runsight_api.logic.services.execution_service import ExecutionService

    db_engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(db_engine)
    with Session(db_engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="workflow_commit_sha",
                workflow_name="Commit SHA workflow",
                status=RunStatus.pending,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()

    workflow_repo = Mock()
    mock_entity = Mock()
    mock_entity.yaml = (
        "workflow:\n  name: test\n  entry: b1\n  transitions: []\n"
        "blocks:\n  b1:\n    type: linear\n    soul_ref: test\nsouls: {}\nconfig: {}"
    )
    mock_entity.filename = "workflow_commit_sha.yaml"
    workflow_repo.get_by_id.return_value = mock_entity
    workflow_repo._get_path.return_value = Mock(
        __str__=lambda self: "/isolated-test-workspace/workflows/workflow_commit_sha.yaml"
    )

    provider_repo = Mock()
    provider_repo.list_all.return_value = []
    service = ExecutionService(
        run_repo=RunRepository(Session(db_engine)),
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
    )

    with (
        patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse,
        patch.object(ExecutionService, "_get_workflow_commit_sha", return_value=fake_sha),
    ):
        from runsight_core.state import WorkflowState

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())
        mock_parse.return_value = mock_wf

        await service.launch_execution(
            run_id,
            "workflow_commit_sha",
            _prepared_inputs({"instruction": "summarize research notes"}),
            branch=None,
        )
        await asyncio.sleep(0.15)

    with Session(db_engine) as session:
        updated = session.get(Run, run_id)
        assert updated is not None
        assert updated.commit_sha == fake_sha
        assert not hasattr(updated, "workflow_commit_sha")
        assert not hasattr(updated, "effective_commit_sha")
