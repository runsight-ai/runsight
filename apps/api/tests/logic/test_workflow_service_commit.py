"""WorkflowService commit behavior and rollback coverage."""

from unittest.mock import Mock, call

import pytest

from workflow_service_helpers import InputValidationError, WorkflowEntity, WorkflowService
from workflow_service_helpers import make_workflow_repo


@pytest.fixture
def workflow_repo():
    return make_workflow_repo()


def test_commit_workflow_writes_current_state_and_returns_commit_metadata(workflow_repo):
    """commit_workflow writes the draft payload, commits it to main, and returns metadata."""
    git_service = Mock()
    git_service.commit_to_branch.return_value = "abc123def456"
    saved = WorkflowEntity(
        kind="workflow",
        id="saveable-workflow",
        name="Updated Flow",
        yaml="workflow:\n  name: Updated Flow\n",
        canvas_state={
            "nodes": [{"id": "workflow-canvas-node"}],
            "edges": [],
            "viewport": {"x": 1, "y": 2, "zoom": 0.75},
            "selected_node_id": "workflow-canvas-node",
            "canvas_mode": "dag",
        },
    )
    workflow_repo.update.return_value = saved

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    draft = {
        "yaml": "workflow:\n  name: Updated Flow\n",
        "canvas_state": {
            "nodes": [{"id": "workflow-canvas-node"}],
            "edges": [],
            "viewport": {"x": 1, "y": 2, "zoom": 0.75},
            "selected_node_id": "workflow-canvas-node",
            "canvas_mode": "dag",
        },
    }

    result = workflow_service.commit_workflow("saveable-workflow", draft, "Save workflow to main")

    assert result == {"hash": "abc123def456", "message": "Save workflow to main"}
    workflow_repo.update.assert_called_once_with("saveable-workflow", draft)
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        [
            "custom/workflows/saveable-workflow.yaml",
            "custom/workflows/.canvas/saveable-workflow.canvas.json",
        ],
        "Save workflow to main",
    )


def test_commit_workflow_stages_only_workflow_owned_files(workflow_repo):
    """commit_workflow must not stage unrelated worktree changes during an explicit save."""
    git_service = Mock()
    git_service.commit_to_branch.return_value = "abc123def456"
    workflow_repo.update.return_value = WorkflowEntity(
        kind="workflow", id="saveable-workflow", name="Updated Flow"
    )

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    workflow_service.commit_workflow(
        "saveable-workflow",
        {"yaml": "workflow:\n  name: Updated Flow\n"},
        "Save workflow to main",
    )

    _, files, _ = git_service.commit_to_branch.call_args.args
    assert files == ["custom/workflows/saveable-workflow.yaml"]
    assert "README.md" not in files
    assert ".env" not in files


def test_commit_workflow_does_not_attempt_git_commit_when_persisting_the_draft_fails(
    workflow_repo,
):
    """Atomic save contract: if the workflow write fails, the main-branch commit must never start."""
    git_service = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="saveable-workflow",
        name="Original Flow",
        yaml="workflow:\n  name: Original Flow\n",
    )
    workflow_repo.update.side_effect = OSError("disk full")

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    with pytest.raises(OSError, match="disk full"):
        workflow_service.commit_workflow(
            "saveable-workflow",
            {"yaml": "workflow:\n  name: Updated Flow\n"},
            "Save workflow to main",
        )

    git_service.commit_to_branch.assert_not_called()


def test_commit_workflow_requires_yaml_before_touching_git(workflow_repo):
    """Explicit saves must fail fast when the draft omits canonical YAML."""
    git_service = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="saveable-workflow",
        name="Original Flow",
        yaml="workflow:\n  name: Original Flow\n",
    )
    workflow_repo.update.side_effect = InputValidationError("yaml is required")

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    with pytest.raises(InputValidationError, match="yaml is required"):
        workflow_service.commit_workflow(
            "saveable-workflow",
            {"name": "Updated Flow"},
            "Save workflow to main",
        )

    git_service.commit_to_branch.assert_not_called()


def test_commit_workflow_restores_the_previous_workflow_if_git_commit_to_main_fails(workflow_repo):
    """Atomic save contract: a failed main-branch commit must roll the persisted workflow back."""
    git_service = Mock()
    git_service.commit_to_branch.side_effect = RuntimeError("git failed")
    previous_canvas_state = {
        "nodes": [{"id": "node-original"}],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1.0},
        "selected_node_id": "node-original",
        "canvas_mode": "dag",
    }
    previous = WorkflowEntity(
        kind="workflow",
        id="rollback-workflow",
        name="Original Flow",
        yaml="workflow:\n  name: Original Flow\n",
        canvas_state=previous_canvas_state,
    )
    workflow_repo.get_by_id.return_value = previous
    workflow_repo.update.side_effect = [
        WorkflowEntity(
            kind="workflow",
            id="rollback-workflow",
            name="Updated Flow",
            yaml="workflow:\n  name: Updated Flow\n",
        ),
        previous,
    ]

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)
    draft = {
        "yaml": "workflow:\n  name: Updated Flow\n",
        "canvas_state": {
            "nodes": [{"id": "node-updated"}],
            "edges": [],
            "viewport": {"x": 2, "y": 3, "zoom": 0.75},
            "selected_node_id": "node-updated",
            "canvas_mode": "dag",
        },
    }

    with pytest.raises(RuntimeError, match="git failed"):
        workflow_service.commit_workflow("rollback-workflow", draft, "Save workflow to main")

    assert workflow_repo.update.call_args_list == [
        call("rollback-workflow", draft),
        call(
            "rollback-workflow",
            {
                "yaml": "workflow:\n  name: Original Flow\n",
                "canvas_state": previous_canvas_state,
            },
        ),
    ]
    git_service.commit_to_branch.assert_called_once()


def test_commit_workflow_restores_exact_corrupt_canvas_sidecar_bytes_when_git_commit_fails(
    tmp_path,
):
    """Rollback must preserve the pre-save sidecar bytes even when JSON parsing failed."""
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

    workflow_id = "corrupt-canvas-workflow"
    original_yaml = (
        f"id: {workflow_id}\n"
        "kind: workflow\n"
        "version: '1.0'\n"
        "blocks: {}\n"
        "workflow:\n"
        "  name: Original Flow\n"
        "  entry: start\n"
        "  transitions: []\n"
    )
    updated_yaml = (
        f"id: {workflow_id}\n"
        "kind: workflow\n"
        "version: '1.0'\n"
        "blocks: {}\n"
        "workflow:\n"
        "  name: Updated Flow\n"
        "  entry: start\n"
        "  transitions: []\n"
    )
    original_canvas = {
        "nodes": [{"id": "node-original", "position": {"x": 10, "y": 20}}],
        "edges": [],
        "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.0},
        "selected_node_id": "node-original",
        "canvas_mode": "dag",
    }
    updated_canvas = {
        "nodes": [{"id": "node-updated", "position": {"x": 30, "y": 40}}],
        "edges": [],
        "viewport": {"x": 3.0, "y": 4.0, "zoom": 0.8},
        "selected_node_id": "node-updated",
        "canvas_mode": "dag",
    }
    corrupt_canvas_bytes = b'{"nodes":[{"id":"node-original"}],\n'

    workflow_repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_repo.create({"yaml": original_yaml, "canvas_state": original_canvas})
    canvas_path = workflow_repo._canvas_path(workflow_id)
    canvas_path.write_bytes(corrupt_canvas_bytes)

    git_service = Mock()
    git_service.commit_to_branch.side_effect = RuntimeError("git failed")
    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    with pytest.raises(RuntimeError, match="git failed"):
        workflow_service.commit_workflow(
            workflow_id,
            {"yaml": updated_yaml, "canvas_state": updated_canvas},
            "Save workflow to main",
        )

    assert workflow_repo._get_path(workflow_id).read_text() == original_yaml
    assert canvas_path.exists()
    assert canvas_path.read_bytes() == corrupt_canvas_bytes
