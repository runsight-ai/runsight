from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from tests.logic.snapshot_resolution_fixtures import SnapshotGitService
from tests.logic.snapshot_resolution_fixtures import (
    init_git_repo_with_embedded_id_child_on_feature_branch,
)
from tests.logic.snapshot_resolution_fixtures import (
    init_git_repo_with_invalid_child_contract_snapshot,
)
from tests.logic.snapshot_resolution_fixtures import init_git_repo_with_missing_child_ref
from tests.logic.snapshot_resolution_fixtures import (
    init_git_repo_with_reserved_child_contract_snapshot,
)
from tests.logic.snapshot_resolution_fixtures import prepared_inputs
from tests.logic.snapshot_resolution_fixtures import provider_repo_with_openai
from tests.logic.snapshot_resolution_fixtures import resolvable_child_snapshot_files
from tests.logic.snapshot_resolution_fixtures import run_repo_with_pending_record
from tests.logic.snapshot_resolution_fixtures import stub_runtime_execution


@pytest.mark.asyncio
async def test_launch_execution_resolves_child_workflow_from_snapshot_files_without_repo_path(
    tmp_path: Path,
) -> None:
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService

    git_service = SnapshotGitService(
        snapshot_root=tmp_path,
        snapshot_files=resolvable_child_snapshot_files(),
    )
    assert git_service.list_files("main", "custom/workflows/") == [
        "custom/workflows/child.yaml",
        "custom/workflows/parent.yaml",
    ]

    run_repo = run_repo_with_pending_record()
    provider_repo = provider_repo_with_openai()
    workflow_repo = WorkflowRepository(base_path=str(tmp_path))
    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )
    stub_runtime_execution(svc)

    def _assert_snapshot_registry(yaml_content, **kwargs):
        workflow_definition = yaml.safe_load(yaml_content)
        assert workflow_definition["workflow"]["name"] == "Parent Workflow"
        workflow_registry = kwargs.get("workflow_registry")
        assert workflow_registry is not None
        child_file = workflow_registry.get("child")
        assert child_file.workflow.name == "Child Workflow"
        assert child_file.inputs is not None
        assert list(child_file.inputs) == ["topic"]
        assert child_file.inputs["topic"].type == "string"
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
            prepared_inputs({"instruction": "execute nested workflow"}),
            branch="main",
        )
        await asyncio.sleep(0.05)

    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args.args[0]
    assert updated.error is None
    assert updated.branch == "main"
    assert updated.commit_sha is not None
    assert svc._run_workflow.await_count == 1


@pytest.mark.asyncio
async def test_launch_execution_rejects_invalid_child_public_input_contract_from_snapshot(
    tmp_path: Path,
) -> None:
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.git_service import GitService

    repo = init_git_repo_with_invalid_child_contract_snapshot(tmp_path)

    run_repo = run_repo_with_pending_record()
    provider_repo = provider_repo_with_openai()
    workflow_repo = WorkflowRepository(base_path=str(repo))
    git_service = GitService(repo_path=repo)
    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )
    stub_runtime_execution(svc)

    with patch.object(
        svc,
        "_prepare_runtime_workflow",
        side_effect=lambda *, yaml_content, api_keys: (yaml.safe_load(yaml_content), Mock()),
    ):
        await svc.launch_execution(
            "run_invalid_child_contract",
            "parent",
            prepared_inputs({"instruction": "execute nested workflow"}),
            branch="main",
        )
        await asyncio.sleep(0.05)

    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args.args[0]
    assert updated.error is not None
    assert "workflow contract name" in updated.error.lower()
    assert "userid" in updated.error.lower()
    assert svc._run_workflow.await_count == 0


@pytest.mark.asyncio
async def test_missing_child_ref_fails_at_save_and_launch_with_same_resolution_error(
    tmp_path: Path,
) -> None:
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.git_service import GitService

    repo, parent_yaml = init_git_repo_with_missing_child_ref(tmp_path)
    workflow_repo = WorkflowRepository(base_path=str(repo))

    saved = workflow_repo.update("parent", {"yaml": parent_yaml})

    assert saved.valid is False
    assert saved.validation_error is not None
    assert "renamed-child" in saved.validation_error
    assert "resolve ref" in saved.validation_error.lower()

    run_repo = run_repo_with_pending_record()
    provider_repo = provider_repo_with_openai()
    git_service = GitService(repo_path=repo)
    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )
    stub_runtime_execution(svc)

    with patch.object(
        svc,
        "_prepare_runtime_workflow",
        side_effect=lambda *, yaml_content, api_keys: (yaml.safe_load(yaml_content), Mock()),
    ):
        await svc.launch_execution(
            "run_missing_child",
            "parent",
            prepared_inputs({"instruction": "execute nested workflow"}),
            branch="main",
        )
        await asyncio.sleep(0.05)

    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args.args[0]
    assert updated.error is not None
    assert "renamed-child" in updated.error
    assert "resolve ref" in updated.error.lower()
    assert svc._run_workflow.await_count == 0


@pytest.mark.asyncio
async def test_launch_execution_rejects_reserved_child_public_input_contract_from_snapshot(
    tmp_path: Path,
) -> None:
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.git_service import GitService

    repo = init_git_repo_with_reserved_child_contract_snapshot(tmp_path)

    run_repo = run_repo_with_pending_record()
    provider_repo = provider_repo_with_openai()
    workflow_repo = WorkflowRepository(base_path=str(repo))
    git_service = GitService(repo_path=repo)
    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )
    stub_runtime_execution(svc)

    with patch.object(
        svc,
        "_prepare_runtime_workflow",
        side_effect=lambda *, yaml_content, api_keys: (yaml.safe_load(yaml_content), Mock()),
    ):
        await svc.launch_execution(
            "run_reserved_child_contract",
            "parent",
            prepared_inputs({"instruction": "execute nested workflow"}),
            branch="main",
        )
        await asyncio.sleep(0.05)

    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args.args[0]
    assert updated.error is not None
    assert "reserved" in updated.error.lower()
    assert "workflow" in updated.error.lower()
    assert "child" in updated.error.lower()
    assert svc._run_workflow.await_count == 0


# ---------------------------------------------------------------------------
# Item 3b: Branch-scoped snapshot resolution — embedded-id child refs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_launch_execution_resolves_embedded_id_child_from_branch_snapshot(
    tmp_path: Path,
) -> None:
    """Branch snapshot resolution discovers children by embedded workflow id."""
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.git_service import GitService

    repo = init_git_repo_with_embedded_id_child_on_feature_branch(tmp_path)

    run_repo = run_repo_with_pending_record()
    provider_repo = provider_repo_with_openai()
    workflow_repo = WorkflowRepository(base_path=str(repo))
    git_service = GitService(repo_path=repo)

    svc = ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
    )
    stub_runtime_execution(svc)

    with (
        patch.object(
            svc,
            "_prepare_runtime_workflow",
            side_effect=lambda *, yaml_content, api_keys: (yaml.safe_load(yaml_content), Mock()),
        ),
        patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse,
    ):
        mock_parse.return_value = Mock(name="parsed_workflow")

        await svc.launch_execution(
            "run_embedded_id_branch",
            "parent",
            prepared_inputs({"instruction": "execute with embedded-id child"}),
            branch="feature-a",
        )
        await asyncio.sleep(0.05)

    # Embedded-id resolution from branch snapshot should succeed.
    error_calls = [
        c
        for c in run_repo.update_run.call_args_list
        if hasattr(c.args[0], "error") and c.args[0].error is not None
    ]
    assert len(error_calls) == 0, (
        f"Expected no error when resolving child by embedded id from branch snapshot. "
        f"Got: {error_calls[0].args[0].error if error_calls else 'N/A'}"
    )
    assert svc._run_workflow.await_count == 1
