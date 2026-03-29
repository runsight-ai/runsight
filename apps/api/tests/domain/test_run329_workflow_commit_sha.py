"""Red tests for RUN-329: Capture workflow commit SHA on Run at execution time.

Tests cover:
1. Run model has workflow_commit_sha field (defaults to None)
2. SHA captured at execution time via git command
3. Graceful None when not in a git repo or git not available
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

# ---------------------------------------------------------------------------
# 1. Run model — workflow_commit_sha field
# ---------------------------------------------------------------------------


class TestRunWorkflowCommitShaField:
    def test_run_has_workflow_commit_sha_field(self):
        """Run model has a workflow_commit_sha field."""
        from runsight_api.domain.entities.run import Run

        run = Run(
            id="run-sha-1",
            workflow_id="wf-1",
            workflow_name="WF 1",
            task_json='{"instruction": "test"}',
        )
        assert hasattr(run, "workflow_commit_sha")

    def test_workflow_commit_sha_defaults_to_none(self):
        """workflow_commit_sha defaults to None when not provided."""
        from runsight_api.domain.entities.run import Run

        run = Run(
            id="run-sha-2",
            workflow_id="wf-1",
            workflow_name="WF 1",
            task_json='{"instruction": "test"}',
        )
        assert run.workflow_commit_sha is None

    def test_workflow_commit_sha_accepts_string(self):
        """workflow_commit_sha can be set to a string (SHA hash)."""
        from runsight_api.domain.entities.run import Run

        sha = "abc123def456789012345678901234567890abcd"
        run = Run(
            id="run-sha-3",
            workflow_id="wf-1",
            workflow_name="WF 1",
            task_json='{"instruction": "test"}',
            workflow_commit_sha=sha,
        )
        assert run.workflow_commit_sha == sha

    def test_workflow_commit_sha_persists_in_db(self):
        """workflow_commit_sha is stored and retrieved from the database."""
        from runsight_api.domain.entities.run import Run

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        sha = "abc123def456789012345678901234567890abcd"
        with Session(engine) as session:
            run = Run(
                id="run-sha-db",
                workflow_id="wf-1",
                workflow_name="WF 1",
                task_json='{"instruction": "test"}',
                workflow_commit_sha=sha,
            )
            session.add(run)
            session.commit()

        with Session(engine) as session:
            loaded = session.get(Run, "run-sha-db")
            assert loaded.workflow_commit_sha == sha

    def test_workflow_commit_sha_none_persists_in_db(self):
        """workflow_commit_sha=None round-trips through the database."""
        from runsight_api.domain.entities.run import Run

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            run = Run(
                id="run-sha-none",
                workflow_id="wf-1",
                workflow_name="WF 1",
                task_json='{"instruction": "test"}',
            )
            session.add(run)
            session.commit()

        with Session(engine) as session:
            loaded = session.get(Run, "run-sha-none")
            assert loaded.workflow_commit_sha is None


# ---------------------------------------------------------------------------
# 2. ExecutionService — SHA capture helper
# ---------------------------------------------------------------------------


class TestGetWorkflowCommitSha:
    def test_get_workflow_commit_sha_method_exists(self):
        """ExecutionService has a _get_workflow_commit_sha static/class method."""
        from runsight_api.logic.services.execution_service import ExecutionService

        assert hasattr(ExecutionService, "_get_workflow_commit_sha")

    def test_returns_sha_string_for_tracked_file(self):
        """Returns a 40-char hex SHA when the file is tracked by git."""
        from runsight_api.logic.services.execution_service import ExecutionService

        fake_sha = "abc123def456789012345678901234567890abcd"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=f"{fake_sha}\n",
            )
            result = ExecutionService._get_workflow_commit_sha("/some/path/workflow.yaml")

        assert result == fake_sha
        mock_run.assert_called_once()

    def test_returns_none_when_not_git_repo(self):
        """Returns None when file is not in a git repo (git command fails)."""
        from runsight_api.logic.services.execution_service import ExecutionService

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=128,
                stdout="",
            )
            result = ExecutionService._get_workflow_commit_sha("/not/a/repo/wf.yaml")

        assert result is None

    def test_returns_none_when_git_not_installed(self):
        """Returns None when git is not installed (FileNotFoundError)."""
        from runsight_api.logic.services.execution_service import ExecutionService

        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = ExecutionService._get_workflow_commit_sha("/some/path/wf.yaml")

        assert result is None

    def test_returns_none_when_file_untracked(self):
        """Returns None when the file exists but has no commits (stdout is empty)."""
        from runsight_api.logic.services.execution_service import ExecutionService

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="",
            )
            result = ExecutionService._get_workflow_commit_sha("/some/path/new.yaml")

        assert result is None

    def test_returns_none_on_unexpected_exception(self):
        """Returns None on any unexpected exception (never crashes)."""
        from runsight_api.logic.services.execution_service import ExecutionService

        with patch("subprocess.run", side_effect=OSError("unexpected")):
            result = ExecutionService._get_workflow_commit_sha("/some/path/wf.yaml")

        assert result is None


# ---------------------------------------------------------------------------
# 3. ExecutionService — SHA stored on Run during launch_execution
# ---------------------------------------------------------------------------


class TestLaunchExecutionStoresSha:
    @pytest.mark.asyncio
    async def test_launch_execution_stores_sha_on_run(self):
        """launch_execution captures workflow commit SHA and stores it on the Run record."""
        from runsight_api.domain.entities.run import Run, RunStatus
        from runsight_api.logic.services.execution_service import ExecutionService

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_sha_store"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        workflow_repo = Mock()
        mock_entity = Mock()
        mock_entity.yaml = (
            "workflow:\n  name: test\n  entry: b1\n  transitions: []\n"
            "blocks:\n  b1:\n    type: linear\n    soul_ref: test\nsouls: {}\nconfig: {}"
        )
        mock_entity.filename = "wf_1.yaml"
        workflow_repo.get_by_id.return_value = mock_entity
        workflow_repo._get_path.return_value = Mock(
            __str__=lambda self: "/project/custom/workflows/wf_1.yaml"
        )

        provider_repo = Mock()
        provider_repo.list_all.return_value = []

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        fake_sha = "aabbccddee1234567890aabbccddee1234567890"

        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml"
            ) as mock_parse,
            patch.object(
                ExecutionService,
                "_get_workflow_commit_sha",
                return_value=fake_sha,
            ),
        ):
            from runsight_core.state import WorkflowState

            mock_wf = Mock()
            mock_wf.run = AsyncMock(return_value=WorkflowState())
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.workflow_commit_sha == fake_sha

    @pytest.mark.asyncio
    async def test_launch_execution_stores_none_when_no_git(self):
        """launch_execution stores None for workflow_commit_sha when git is unavailable."""
        from runsight_api.domain.entities.run import Run, RunStatus
        from runsight_api.logic.services.execution_service import ExecutionService

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_sha_none"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        workflow_repo = Mock()
        mock_entity = Mock()
        mock_entity.yaml = (
            "workflow:\n  name: test\n  entry: b1\n  transitions: []\n"
            "blocks:\n  b1:\n    type: linear\n    soul_ref: test\nsouls: {}\nconfig: {}"
        )
        mock_entity.filename = "wf_1.yaml"
        workflow_repo.get_by_id.return_value = mock_entity
        workflow_repo._get_path.return_value = Mock(
            __str__=lambda self: "/project/custom/workflows/wf_1.yaml"
        )

        provider_repo = Mock()
        provider_repo.list_all.return_value = []

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml"
            ) as mock_parse,
            patch.object(
                ExecutionService,
                "_get_workflow_commit_sha",
                return_value=None,
            ),
        ):
            from runsight_core.state import WorkflowState

            mock_wf = Mock()
            mock_wf.run = AsyncMock(return_value=WorkflowState())
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.workflow_commit_sha is None
