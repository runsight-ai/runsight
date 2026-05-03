"""Branch-aware execution behavior.

ExecutionService.launch_execution must:
1. Accept a ``branch`` parameter explicitly
2. When Git is configured, read YAML via GitService.read_file(path, branch)
3. ``branch="main"`` must load committed main content, not mutable working-tree YAML
4. Pass YAML *string* (not file path) to parse_workflow_yaml
5. Persist ``branch`` + ``commit_sha`` on the Run record
"""

import asyncio
import subprocess
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session

from runsight_api.domain.entities.run import Run
from runsight_api.logic.services.execution_service import ExecutionService
from tests.logic.branch_execution_fixtures import VALID_YAML
from tests.logic.branch_execution_fixtures import WORKFLOW_ID
from tests.logic.branch_execution_fixtures import WORKFLOW_PATH
from tests.logic.branch_execution_fixtures import branch_instruction
from tests.logic.branch_execution_fixtures import create_run_engine_with_branch_run
from tests.logic.branch_execution_fixtures import make_service


# ---------------------------------------------------------------------------
# launch_execution accepts branch parameter
# ---------------------------------------------------------------------------


class TestLaunchAcceptsBranch:
    """launch_execution accepts ``branch`` parameter."""

    @pytest.mark.asyncio
    async def test_accepts_branch_keyword_argument(self):
        """launch_execution can be called with branch='main' without TypeError."""
        svc, *_ = make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            # Must not raise TypeError for unexpected keyword argument 'branch'
            await svc.launch_execution(
                "main-branch-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch="main",
            )

    @pytest.mark.asyncio
    async def test_accepts_sim_branch(self):
        """launch_execution accepts a simulation branch name."""
        svc, *_ = make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "simulation-branch-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch="sim/branch-aware-workflow/20260329/abc12",
            )

    @pytest.mark.asyncio
    async def test_missing_branch_uses_working_tree_without_git_snapshot(self):
        """Omitting branch should use the working-tree workflow definition."""
        svc, _, _, _, git_service = make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "working-tree-run",
                WORKFLOW_ID,
                branch_instruction(),
            )
            await asyncio.sleep(0.05)

            git_service.read_file.assert_not_called()
            mock_parse.assert_called_once()
            assert mock_parse.call_args.args[0] == VALID_YAML


# ---------------------------------------------------------------------------
# Sim branch reads YAML via GitService.read_file
# ---------------------------------------------------------------------------


class TestSimBranchReadsViaGit:
    """Sim branch runs read YAML via git show (GitService.read_file)."""

    @pytest.mark.asyncio
    async def test_sim_branch_calls_git_read_file(self):
        """When branch is a sim branch, GitService.read_file is called."""
        svc, _, workflow_repo, _, git_service = make_service()

        sim_branch = "sim/branch-aware-workflow/20260329/abc12"
        git_service.read_file.return_value = VALID_YAML

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "sim-branch-read-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch=sim_branch,
            )
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
        """Sim branch YAML content comes from git, not from workflow_entity.yaml."""
        svc, _, workflow_repo, _, git_service = make_service()

        sim_branch = "sim/branch-aware-workflow/20260329/abc12"
        git_yaml = "workflow:\n  name: from-git-branch-aware\n  entry: planning_block\n  transitions: []\nblocks:\n  planning_block:\n    type: linear\n    soul_ref: branch_planner\nsouls: {}\nconfig: {}"
        git_service.read_file.return_value = git_yaml

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "sim-branch-yaml-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch=sim_branch,
            )
            await asyncio.sleep(0.05)

            # Parser must receive the git YAML, not the filesystem YAML
            mock_parse.assert_called_once()
            yaml_arg = mock_parse.call_args[0][0]
            assert yaml_arg == git_yaml

    @pytest.mark.asyncio
    async def test_sim_branch_gets_commit_sha_from_git_service(self):
        """Sim branch commit_sha comes from GitService.get_sha, not subprocess."""
        svc, _, _, _, git_service = make_service()

        sim_branch = "sim/branch-aware-workflow/20260329/abc12"
        git_service.get_sha.return_value = "deadbeef1234567890"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "sim-branch-sha-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch=sim_branch,
            )
            await asyncio.sleep(0.05)

            git_service.get_sha.assert_called_once()
            call_args = git_service.get_sha.call_args
            assert sim_branch in call_args[0] or call_args[1].get("branch") == sim_branch


# ---------------------------------------------------------------------------
# Main branch reads committed main via Git
# ---------------------------------------------------------------------------


class TestMainBranchReadsViaGit:
    """Main branch runs read committed main content via GitService."""

    @pytest.mark.asyncio
    async def test_main_branch_calls_git_read_file(self):
        """When branch is 'main', GitService.read_file is called for main."""
        svc, _, _, _, git_service = make_service()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "main-branch-read-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch="main",
            )
            await asyncio.sleep(0.05)

            git_service.read_file.assert_called_once_with(WORKFLOW_PATH, "main")

    @pytest.mark.asyncio
    async def test_main_branch_uses_git_yaml_not_workflow_entity_yaml(self):
        """Main branch parses committed main YAML, not mutable workflow entity YAML."""
        svc, _, workflow_repo, _, _ = make_service()
        workflow_repo.get_by_id.return_value.yaml = "workflow:\n  name: dirty-working-tree\n"
        svc.git_service.read_file.return_value = VALID_YAML

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "main-branch-yaml-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch="main",
            )
            await asyncio.sleep(0.05)

            mock_parse.assert_called_once()
            yaml_arg = mock_parse.call_args[0][0]
            assert yaml_arg == VALID_YAML
            assert yaml_arg != workflow_repo.get_by_id.return_value.yaml


class TestGitUnavailableStrictness:
    """Fail-closed behavior when explicit git snapshots are unavailable."""

    @pytest.mark.asyncio
    async def test_non_git_repo_fails_closed_for_explicit_main_branch(self):
        """Explicit main branch must not fall back to working-tree YAML."""
        svc, _, workflow_repo, _, git_service = make_service()
        working_tree_yaml = "workflow:\n  name: local-working-tree\n  entry: planning_block\n  transitions: []\nblocks:\n  planning_block:\n    type: linear\n    soul_ref: branch_planner\nsouls: {}\nconfig: {}"
        workflow_repo.get_by_id.return_value.yaml = working_tree_yaml
        git_service.read_file.side_effect = subprocess.CalledProcessError(
            128,
            ["git", "show"],
            stderr="fatal: not a git repository (or any of the parent directories): .git",
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "git-unavailable-main-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch="main",
            )
            await asyncio.sleep(0.05)

            git_service.read_file.assert_called_once_with(WORKFLOW_PATH, "main")
            mock_parse.assert_not_called()


# ---------------------------------------------------------------------------
# Parser receives YAML string content
# ---------------------------------------------------------------------------


class TestParserReceivesString:
    """Parser receives YAML string, not file path."""

    @pytest.mark.asyncio
    async def test_parser_gets_string_for_sim_branch(self):
        """parse_workflow_yaml receives a YAML string (not a Path) for sim branches."""
        svc, _, _, _, git_service = make_service()

        sim_branch = "sim/parser-workflow/20260329/zzz"
        git_service.read_file.return_value = VALID_YAML

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "parser-yaml-string-run",
                WORKFLOW_ID,
                branch_instruction(),
                branch=sim_branch,
            )
            await asyncio.sleep(0.05)

            mock_parse.assert_called_once()
            yaml_arg = mock_parse.call_args[0][0]
            assert isinstance(yaml_arg, str)
            # Must be actual YAML content, not a file path
            assert "workflow:" in yaml_arg


# ---------------------------------------------------------------------------
# Branch + commit_sha stored on Run record
# ---------------------------------------------------------------------------


class TestBranchStoredOnRun:
    """branch + commit_sha stored on Run record."""

    @pytest.mark.asyncio
    async def test_sim_branch_stored_on_run(self):
        """Run record has branch field set to the sim branch name."""
        run_id = "stored-sim-branch-run"
        sim_branch = "sim/branch-aware-workflow/20260329/abc12"
        db_engine = create_run_engine_with_branch_run(run_id=run_id, branch=sim_branch)

        svc, _, _, _, git_service = make_service(engine=db_engine)
        git_service.get_sha.return_value = "cafebabe12345678"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                run_id,
                WORKFLOW_ID,
                branch_instruction(),
                branch=sim_branch,
            )
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.branch == sim_branch

    @pytest.mark.asyncio
    async def test_commit_sha_stored_on_run(self):
        """Run record has commit_sha populated from GitService and no legacy sha field."""
        run_id = "stored-sim-sha-run"
        sim_branch = "sim/branch-aware-workflow/20260329/def45"
        db_engine = create_run_engine_with_branch_run(run_id=run_id, branch=sim_branch)

        svc, _, _, _, git_service = make_service(engine=db_engine)
        git_service.get_sha.return_value = "deadbeef90abcdef"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                run_id,
                WORKFLOW_ID,
                branch_instruction(),
                branch=sim_branch,
            )
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.commit_sha == "deadbeef90abcdef"
            assert not hasattr(updated, "workflow_commit_sha")
            assert not hasattr(updated, "effective_commit_sha")

    @pytest.mark.asyncio
    async def test_main_branch_stored_on_run(self):
        """When branch is 'main', Run.branch is set to 'main'."""
        run_id = "stored-main-branch-run"
        db_engine = create_run_engine_with_branch_run(run_id=run_id, branch="main")

        svc, _, _, _, git_service = make_service(engine=db_engine)

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                run_id,
                WORKFLOW_ID,
                branch_instruction(),
                branch="main",
            )
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.branch == "main"

    @pytest.mark.asyncio
    async def test_main_branch_commit_sha_from_git_service(self):
        """Even for main branch, commit_sha is populated via GitService.get_sha without legacy fields."""
        run_id = "stored-main-sha-run"
        db_engine = create_run_engine_with_branch_run(run_id=run_id, branch="main")

        svc, _, _, _, git_service = make_service(engine=db_engine)
        git_service.get_sha.return_value = "mainsha0000"

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                run_id,
                WORKFLOW_ID,
                branch_instruction(),
                branch="main",
            )
            await asyncio.sleep(0.05)

        with Session(db_engine) as session:
            updated = session.get(Run, run_id)
            assert updated.commit_sha == "mainsha0000"
            assert not hasattr(updated, "workflow_commit_sha")
            assert not hasattr(updated, "effective_commit_sha")


# ---------------------------------------------------------------------------
# ExecutionService accepts git_service dependency
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
