"""Red tests for RUN-380: Branch-aware execution — ExecutionService reads YAML from branch.

ExecutionService.launch_execution must:
1. Accept a ``branch`` parameter (default "main")
2. When branch != "main", read YAML via GitService.read_file(path, branch)
3. When branch == "main", read from filesystem (unchanged behavior)
4. Pass YAML *string* (not file path) to parse_workflow_yaml
5. Persist ``branch`` + ``commit_sha`` on the Run record

All tests should FAIL until the implementation is wired.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_YAML = """\
workflow:
  name: test
  entry: b1
  transitions:
    - from: b1
      to: null
blocks:
  b1:
    type: linear
    soul_ref: test
souls: {}
config: {}
"""


def _make_service(*, engine=None):
    """Return (service, run_repo, workflow_repo, provider_repo, git_service) with mocks."""
    run_repo = Mock()
    workflow_repo = Mock()
    provider_repo = Mock()
    git_service = Mock()

    # workflow_repo returns a valid entity
    wf_entity = Mock()
    wf_entity.yaml = VALID_YAML
    workflow_repo.get_by_id.return_value = wf_entity
    workflow_repo._get_path.return_value = "/fake/workflows/test.yaml"

    # provider_repo — no providers
    provider_repo.list_all.return_value = []

    # git_service defaults
    git_service.read_file.return_value = VALID_YAML
    git_service.get_sha.return_value = "abc123cafebabe"

    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=engine,
        git_service=git_service,
    )
    return svc, run_repo, workflow_repo, provider_repo, git_service


# ---------------------------------------------------------------------------
# 1. launch_execution accepts branch parameter
# ---------------------------------------------------------------------------


class TestLaunchAcceptsBranch:
    """AC: launch_execution accepts ``branch`` parameter."""

    @pytest.mark.asyncio
    async def test_accepts_branch_keyword_argument(self):
        """launch_execution can be called with branch='main' without TypeError."""
        svc, *_ = _make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            # Must not raise TypeError for unexpected keyword argument 'branch'
            await svc.launch_execution("run_1", "wf_1", {"instruction": "go"}, branch="main")

    @pytest.mark.asyncio
    async def test_accepts_sim_branch(self):
        """launch_execution accepts a simulation branch name."""
        svc, *_ = _make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "run_2",
                "wf_1",
                {"instruction": "go"},
                branch="sim/my-workflow/20260329/abc12",
            )

    @pytest.mark.asyncio
    async def test_branch_defaults_to_main(self):
        """When branch is omitted, it defaults to 'main'."""
        svc, _, _, _, git_service = _make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            # Call without branch — should NOT use git_service.read_file
            await svc.launch_execution("run_3", "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.05)

            # Default is main -> filesystem read, not git read
            git_service.read_file.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Sim branch reads YAML via GitService.read_file
# ---------------------------------------------------------------------------


class TestSimBranchReadsViaGit:
    """AC: Sim branch runs read YAML via git show (GitService.read_file)."""

    @pytest.mark.asyncio
    async def test_sim_branch_calls_git_read_file(self):
        """When branch is a sim branch, GitService.read_file is called."""
        svc, _, workflow_repo, _, git_service = _make_service()

        sim_branch = "sim/my-workflow/20260329/abc12"
        git_service.read_file.return_value = VALID_YAML

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_sim1", "wf_1", {"instruction": "go"}, branch=sim_branch)
            await asyncio.sleep(0.05)

            git_service.read_file.assert_called_once()
            call_args = git_service.read_file.call_args
            # Should pass the workflow path and the branch
            assert (
                call_args[1].get("branch", call_args[0][1] if len(call_args[0]) > 1 else None)
                == sim_branch
            )

    @pytest.mark.asyncio
    async def test_sim_branch_uses_git_yaml_not_filesystem(self):
        """Sim branch YAML content comes from git, not from wf_entity.yaml."""
        svc, _, workflow_repo, _, git_service = _make_service()

        sim_branch = "sim/my-workflow/20260329/abc12"
        git_yaml = "workflow:\n  name: from-git\n  entry: b1\n  transitions: []\nblocks:\n  b1:\n    type: linear\n    soul_ref: test\nsouls: {}\nconfig: {}"
        git_service.read_file.return_value = git_yaml

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_sim2", "wf_1", {"instruction": "go"}, branch=sim_branch)
            await asyncio.sleep(0.05)

            # Parser must receive the git YAML, not the filesystem YAML
            mock_parse.assert_called_once()
            yaml_arg = mock_parse.call_args[0][0]
            assert yaml_arg == git_yaml

    @pytest.mark.asyncio
    async def test_sim_branch_gets_commit_sha_from_git_service(self):
        """Sim branch commit_sha comes from GitService.get_sha, not subprocess."""
        svc, _, _, _, git_service = _make_service()

        sim_branch = "sim/my-workflow/20260329/abc12"
        git_service.get_sha.return_value = "deadbeef1234567890"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_sim3", "wf_1", {"instruction": "go"}, branch=sim_branch)
            await asyncio.sleep(0.05)

            git_service.get_sha.assert_called_once()
            call_args = git_service.get_sha.call_args
            assert sim_branch in call_args[0] or call_args[1].get("branch") == sim_branch


# ---------------------------------------------------------------------------
# 3. Main branch reads from filesystem (unchanged behavior)
# ---------------------------------------------------------------------------


class TestMainBranchFilesystem:
    """AC: Main branch runs read from filesystem (unchanged behavior)."""

    @pytest.mark.asyncio
    async def test_main_branch_does_not_call_git_read_file(self):
        """When branch is 'main', GitService.read_file is NOT called."""
        svc, _, _, _, git_service = _make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_main1", "wf_1", {"instruction": "go"}, branch="main")
            await asyncio.sleep(0.05)

            git_service.read_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_main_branch_uses_workflow_entity_yaml(self):
        """Main branch uses wf_entity.yaml (filesystem) as YAML source."""
        svc, _, workflow_repo, _, _ = _make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_main2", "wf_1", {"instruction": "go"}, branch="main")
            await asyncio.sleep(0.05)

            mock_parse.assert_called_once()
            yaml_arg = mock_parse.call_args[0][0]
            assert yaml_arg == VALID_YAML


# ---------------------------------------------------------------------------
# 4. Parser receives YAML string content
# ---------------------------------------------------------------------------


class TestParserReceivesString:
    """AC: Parser receives YAML string, not file path."""

    @pytest.mark.asyncio
    async def test_parser_gets_string_for_sim_branch(self):
        """parse_workflow_yaml receives a YAML string (not a Path) for sim branches."""
        svc, _, _, _, git_service = _make_service()

        sim_branch = "sim/test/20260329/zzz"
        git_service.read_file.return_value = VALID_YAML

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_str1", "wf_1", {"instruction": "go"}, branch=sim_branch)
            await asyncio.sleep(0.05)

            mock_parse.assert_called_once()
            yaml_arg = mock_parse.call_args[0][0]
            assert isinstance(yaml_arg, str)
            # Must be actual YAML content, not a file path
            assert "workflow:" in yaml_arg


# ---------------------------------------------------------------------------
# 5. Branch + commit_sha stored on Run record
# ---------------------------------------------------------------------------


class TestBranchStoredOnRun:
    """AC: branch + commit_sha stored on Run record."""

    @pytest.mark.asyncio
    async def test_sim_branch_stored_on_run(self):
        """Run record has branch field set to the sim branch name."""
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_store1"
        sim_branch = "sim/my-wf/20260329/abc12"

        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        svc, _, _, _, git_service = _make_service(engine=db_engine)
        git_service.get_sha.return_value = "cafebabe12345678"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"}, branch=sim_branch)
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.branch == sim_branch

    @pytest.mark.asyncio
    async def test_commit_sha_stored_on_run(self):
        """Run record has commit_sha populated from GitService."""
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_store2"
        sim_branch = "sim/my-wf/20260329/def45"

        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        svc, _, _, _, git_service = _make_service(engine=db_engine)
        git_service.get_sha.return_value = "deadbeef90abcdef"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"}, branch=sim_branch)
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.commit_sha == "deadbeef90abcdef"

    @pytest.mark.asyncio
    async def test_main_branch_stored_on_run(self):
        """When branch is 'main', Run.branch is set to 'main'."""
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_store3"

        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        svc, _, _, _, git_service = _make_service(engine=db_engine)

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"}, branch="main")
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.branch == "main"

    @pytest.mark.asyncio
    async def test_main_branch_commit_sha_from_git_service(self):
        """Even for main branch, commit_sha is populated via GitService.get_sha."""
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_store4"

        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        svc, _, _, _, git_service = _make_service(engine=db_engine)
        git_service.get_sha.return_value = "mainsha0000"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"}, branch="main")
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.commit_sha == "mainsha0000"


# ---------------------------------------------------------------------------
# 6. ExecutionService accepts git_service dependency
# ---------------------------------------------------------------------------


class TestGitServiceDependency:
    """ExecutionService.__init__ must accept a git_service parameter."""

    def test_init_accepts_git_service(self):
        """ExecutionService can be constructed with a git_service kwarg."""
        git_service = Mock()
        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            git_service=git_service,
        )
        assert svc.git_service is git_service

    def test_git_service_defaults_to_none(self):
        """git_service defaults to None when not provided."""
        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
        )
        assert svc.git_service is None
