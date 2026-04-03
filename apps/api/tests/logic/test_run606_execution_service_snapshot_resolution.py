from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _init_git_repo_with_nested_workflows(
    tmp_path: Path,
    *,
    parent_yaml: str,
    child_yaml: str,
) -> Path:
    repo = tmp_path / "repo"
    workflows_dir = repo / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "parent.yaml").write_text(dedent(parent_yaml).strip() + "\n", encoding="utf-8")
    (workflows_dir / "child.yaml").write_text(dedent(child_yaml).strip() + "\n", encoding="utf-8")

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
        ["git", "commit", "-m", "initial nested workflows"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


@pytest.mark.asyncio
async def test_launch_execution_resolves_child_workflow_from_requested_branch_snapshot(
    tmp_path: Path,
) -> None:
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.git_service import GitService

    parent_yaml = """
    version: "1.0"
    blocks:
      call_child:
        type: workflow
        workflow_ref: custom/workflows/child.yaml
    workflow:
      name: Parent Workflow
      entry: call_child
      transitions:
        - from: call_child
          to: null
    souls:
      controller:
        id: controller_1
        role: Controller
        system_prompt: Route child workflows.
        provider: openai
        model_name: gpt-4o
    config: {}
    """
    child_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs:
        - name: summary
          source: results.writer
    workflow:
      name: Child Workflow
      entry: finish
      transitions: []
    """
    dirty_child_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs:
        - name: detail
          source: results.writer
    workflow:
      name: Dirty Child Workflow
      entry: finish
      transitions: []
    """

    repo = _init_git_repo_with_nested_workflows(
        tmp_path,
        parent_yaml=parent_yaml,
        child_yaml=child_yaml,
    )
    (repo / "custom" / "workflows" / "child.yaml").write_text(
        dedent(dirty_child_yaml).strip() + "\n",
        encoding="utf-8",
    )

    run_repo = Mock()
    provider_repo = Mock()
    provider_repo.list_all.return_value = [
        Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"], api_key=None)
    ]
    workflow_repo = WorkflowRepository(base_path=str(repo))
    git_service = GitService(repo_path=repo)
    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )
    svc._run_workflow = AsyncMock()

    def _assert_snapshot_registry(workflow_definition, **kwargs):
        assert workflow_definition["workflow"]["name"] == "Parent Workflow"
        workflow_registry = kwargs.get("workflow_registry")
        assert workflow_registry is not None
        child_file = workflow_registry.get("custom/workflows/child.yaml")
        assert child_file.interface is not None
        assert [item.name for item in child_file.interface.outputs] == ["summary"]
        return Mock(name="parsed_parent_workflow")

    with patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse:
        mock_parse.side_effect = _assert_snapshot_registry

        await svc.launch_execution(
            "run_snapshot_child",
            "parent",
            {"instruction": "execute nested workflow"},
            branch="main",
        )
        await asyncio.sleep(0.05)

    run_repo.update_run.assert_not_called()
    assert svc._run_workflow.await_count == 1
