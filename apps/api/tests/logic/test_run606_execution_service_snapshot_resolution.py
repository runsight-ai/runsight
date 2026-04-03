from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml


def _init_git_repo_with_workflow_files(tmp_path: Path, *, workflow_files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    workflows_dir = repo / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    for filename, yaml_text in workflow_files.items():
        (workflows_dir / filename).write_text(dedent(yaml_text).strip() + "\n", encoding="utf-8")

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
        ["git", "commit", "-m", "initial workflow snapshot"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def _init_git_repo_with_nested_workflows(
    tmp_path: Path,
    *,
    parent_yaml: str,
    child_yaml: str,
) -> Path:
    return _init_git_repo_with_workflow_files(
        tmp_path,
        workflow_files={"parent.yaml": parent_yaml, "child.yaml": child_yaml},
    )


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

    with (
        patch.object(
            svc,
            "_prepare_runtime_workflow",
            side_effect=lambda *, yaml_content, api_keys: (yaml.safe_load(yaml_content), Mock()),
        ),
        patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse,
    ):
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


@pytest.mark.asyncio
async def test_launch_execution_rejects_invalid_child_interface_bindings_from_snapshot(
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
        inputs:
          question: shared_memory.topic
        outputs:
          results.summary: summary
    workflow:
      name: Parent Workflow
      entry: call_child
      transitions:
        - from: call_child
          to: null
    config: {}
    """
    committed_child_yaml = """
    version: "1.0"
    interface:
      inputs:
        - name: topic
          target: shared_memory.topic
          required: true
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
      inputs:
        - name: question
          target: shared_memory.topic
          required: true
      outputs:
        - name: summary
          source: results.writer
    workflow:
      name: Dirty Child Workflow
      entry: finish
      transitions: []
    """

    repo = _init_git_repo_with_nested_workflows(
        tmp_path,
        parent_yaml=parent_yaml,
        child_yaml=committed_child_yaml,
    )
    (repo / "custom" / "workflows" / "child.yaml").write_text(
        dedent(dirty_child_yaml).strip() + "\n",
        encoding="utf-8",
    )

    run_record = Mock()
    run_repo = Mock()
    run_repo.get_run.return_value = run_record
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

    with patch.object(
        svc,
        "_prepare_runtime_workflow",
        side_effect=lambda *, yaml_content, api_keys: (yaml.safe_load(yaml_content), Mock()),
    ):
        await svc.launch_execution(
            "run_invalid_interface",
            "parent",
            {"instruction": "execute nested workflow"},
            branch="main",
        )
        await asyncio.sleep(0.05)

    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args.args[0]
    assert updated.error is not None
    assert "question" in updated.error
    assert "interface" in updated.error.lower()
    assert svc._run_workflow.await_count == 0


@pytest.mark.asyncio
async def test_missing_child_ref_fails_at_save_and_launch_with_same_resolution_error(
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
        workflow_ref: custom/workflows/renamed-child.yaml
    workflow:
      name: Parent Workflow
      entry: call_child
      transitions:
        - from: call_child
          to: null
    config: {}
    """

    repo = _init_git_repo_with_workflow_files(
        tmp_path,
        workflow_files={"parent.yaml": parent_yaml},
    )
    workflow_repo = WorkflowRepository(base_path=str(repo))

    saved = workflow_repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    assert saved.valid is False
    assert saved.validation_error is not None
    assert "renamed-child" in saved.validation_error
    assert "resolve ref" in saved.validation_error.lower()

    run_record = Mock()
    run_repo = Mock()
    run_repo.get_run.return_value = run_record
    provider_repo = Mock()
    provider_repo.list_all.return_value = [
        Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"], api_key=None)
    ]
    git_service = GitService(repo_path=repo)
    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )
    svc._run_workflow = AsyncMock()

    with patch.object(
        svc,
        "_prepare_runtime_workflow",
        side_effect=lambda *, yaml_content, api_keys: (yaml.safe_load(yaml_content), Mock()),
    ):
        await svc.launch_execution(
            "run_missing_child",
            "parent",
            {"instruction": "execute nested workflow"},
            branch="main",
        )
        await asyncio.sleep(0.05)

    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args.args[0]
    assert updated.error is not None
    assert "renamed-child" in updated.error
    assert "resolve ref" in updated.error.lower()
    assert svc._run_workflow.await_count == 0
