"""Focused regression coverage for RUN-423 main-branch workflow loading."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _init_git_repo_with_workflow(
    tmp_path: Path,
    *,
    workflow_id: str,
    main_yaml: str,
) -> Path:
    repo = tmp_path / "repo"
    workflow_path = repo / "custom" / "workflows" / f"{workflow_id}.yaml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(main_yaml)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Runsight Tests"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial workflow"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


@pytest.mark.asyncio
async def test_launch_execution_reads_main_yaml_from_git_not_working_tree(tmp_path: Path):
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.git_service import GitService

    main_yaml = """id: wf_1
kind: workflow
version: '1.0'
workflow:
  name: Main Workflow
  entry: b1
  transitions: []
blocks:
  b1:
    type: linear
    soul_ref: main-soul
souls: {}
config: {}
"""
    dirty_yaml = """id: wf_1
kind: workflow
version: '1.0'
workflow:
  name: Dirty Workflow
  entry: b1
  transitions: []
blocks:
  b1:
    type: linear
    soul_ref: dirty-soul
souls: {}
config: {}
"""

    repo = _init_git_repo_with_workflow(tmp_path, workflow_id="wf_1", main_yaml=main_yaml)
    workflow_path = repo / "custom" / "workflows" / "wf_1.yaml"
    workflow_path.write_text(dirty_yaml)

    run_repo = Mock()
    provider_repo = Mock()
    provider_repo.list_all.return_value = []
    workflow_repo = WorkflowRepository(base_path=str(repo))
    git_service = GitService(repo_path=repo)
    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )

    with patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse:
        mock_wf = Mock()
        mock_wf.run = AsyncMock()
        mock_parse.return_value = mock_wf

        await svc.launch_execution(
            "run_main_branch_yaml",
            "wf_1",
            {"instruction": "execute main"},
            branch="main",
        )

        mock_parse.assert_called_once()
        assert mock_parse.call_args.args[0] == main_yaml
        assert mock_parse.call_args.args[0] != dirty_yaml
