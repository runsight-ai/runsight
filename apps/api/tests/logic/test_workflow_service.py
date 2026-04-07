"""Comprehensive unit tests for WorkflowService.

Tests document current behavior as guardrails — they break on any behavioral change.
"""

# ruff: noqa: E402

import sys
import types
from unittest.mock import Mock, call

import pytest

# ---------------------------------------------------------------------------
# Save ALL original modules, stub, import, then restore
# ---------------------------------------------------------------------------
_STUBBED_KEYS = [
    "structlog",
    "structlog.contextvars",
    "runsight_core",
    "runsight_core.yaml",
    "runsight_core.yaml.schema",
    "runsight_core.yaml.parser",
    "ruamel",
    "ruamel.yaml",
    "runsight_api.data.filesystem",
    "runsight_api.data.filesystem.workflow_repo",
    "runsight_api.data.repositories",
    "runsight_api.data.repositories.run_repo",
]
_originals = {k: sys.modules.get(k) for k in _STUBBED_KEYS}

structlog = types.ModuleType("structlog")
structlog.contextvars = types.SimpleNamespace(
    bind_contextvars=lambda **kwargs: None,
    unbind_contextvars=lambda *args, **kwargs: None,
)
sys.modules["structlog"] = structlog
sys.modules["structlog.contextvars"] = structlog.contextvars

runsight_core = types.ModuleType("runsight_core")
runsight_core.__path__ = []
yaml_pkg = types.ModuleType("runsight_core.yaml")
yaml_pkg.__path__ = []
schema_pkg = types.ModuleType("runsight_core.yaml.schema")
parser_pkg = types.ModuleType("runsight_core.yaml.parser")


class _RunsightWorkflowFile:
    @classmethod
    def model_validate(cls, data):
        return data


schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
parser_pkg.validate_tool_governance = lambda _: None
yaml_pkg.schema = schema_pkg
yaml_pkg.parser = parser_pkg
runsight_core.yaml = yaml_pkg
sys.modules["runsight_core"] = runsight_core
sys.modules["runsight_core.yaml"] = yaml_pkg
sys.modules["runsight_core.yaml.schema"] = schema_pkg
sys.modules["runsight_core.yaml.parser"] = parser_pkg

ruamel = types.ModuleType("ruamel")
ruamel.__path__ = []
ruamel_yaml = types.ModuleType("ruamel.yaml")


class _YAML:
    def __init__(self, *args, **kwargs):
        self.preserve_quotes = False

    def load(self, _content):
        return {}

    def dump(self, _data, _stream):
        return None


ruamel_yaml.YAML = _YAML
ruamel.yaml = ruamel_yaml
sys.modules["ruamel"] = ruamel
sys.modules["ruamel.yaml"] = ruamel_yaml

fake_filesystem_pkg = types.ModuleType("runsight_api.data.filesystem")
fake_filesystem_pkg.__path__ = []
fake_workflow_repo = types.ModuleType("runsight_api.data.filesystem.workflow_repo")


class _WorkflowRepository:
    pass


fake_workflow_repo.WorkflowRepository = _WorkflowRepository
fake_filesystem_pkg.workflow_repo = fake_workflow_repo
sys.modules["runsight_api.data.filesystem"] = fake_filesystem_pkg
sys.modules["runsight_api.data.filesystem.workflow_repo"] = fake_workflow_repo

fake_repositories_pkg = types.ModuleType("runsight_api.data.repositories")
fake_repositories_pkg.__path__ = []
fake_run_repo = types.ModuleType("runsight_api.data.repositories.run_repo")


class _RunRepository:
    pass


fake_run_repo.RunRepository = _RunRepository
fake_repositories_pkg.run_repo = fake_run_repo
sys.modules["runsight_api.data.repositories"] = fake_repositories_pkg
sys.modules["runsight_api.data.repositories.run_repo"] = fake_run_repo

from runsight_api.domain.errors import InputValidationError, WorkflowNotFound
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.workflow_service import WorkflowService

# Restore ALL original modules so other test files are not poisoned
for _key, _orig in _originals.items():
    if _orig is not None:
        sys.modules[_key] = _orig
    else:
        sys.modules.pop(_key, None)

# --- Fixtures ---


@pytest.fixture
def workflow_repo():
    return Mock()


@pytest.fixture
def run_repo():
    return Mock()


@pytest.fixture
def workflow_service(workflow_repo, run_repo):
    return WorkflowService(workflow_repo, run_repo)


# --- list_workflows ---


def test_list_workflows_empty(workflow_service, workflow_repo):
    """list_workflows returns empty list when repo has no workflows."""
    workflow_repo.list_all.return_value = []

    result = workflow_service.list_workflows()

    assert result == []
    workflow_repo.list_all.assert_called_once()


def test_list_workflows_multiple(workflow_service, workflow_repo):
    """list_workflows returns all workflows from repo."""
    w1 = WorkflowEntity(id="wf_1", name="First")
    w2 = WorkflowEntity(id="wf_2", name="Second")
    workflow_repo.list_all.return_value = [w1, w2]

    result = workflow_service.list_workflows()

    assert len(result) == 2
    assert result[0].id == "wf_1"
    assert result[1].id == "wf_2"


def test_list_workflows_with_query_filter(workflow_service, workflow_repo):
    """list_workflows filters by query (case-insensitive) in id or name."""
    w1 = WorkflowEntity(id="alpha_beta", name="Alpha")
    w2 = WorkflowEntity(id="beta_gamma", name="Gamma")
    w3 = WorkflowEntity(id="other", name="Other")
    workflow_repo.list_all.return_value = [w1, w2, w3]

    result = workflow_service.list_workflows(query="beta")

    assert len(result) == 2
    ids = [w.id for w in result]
    assert "alpha_beta" in ids
    assert "beta_gamma" in ids
    assert "other" not in ids


def test_list_workflows_query_matches_name(workflow_service, workflow_repo):
    """list_workflows matches query against name when present."""
    w1 = WorkflowEntity(id="wf_1", name="MyWorkflow")
    w2 = WorkflowEntity(id="wf_2", name="OtherWorkflow")
    workflow_repo.list_all.return_value = [w1, w2]

    result = workflow_service.list_workflows(query="myworkflow")

    assert len(result) == 1
    assert result[0].id == "wf_1"


def test_list_workflows_query_empty_string_returns_all(workflow_service, workflow_repo):
    """list_workflows with query='' or None returns all (falsy query = no filter)."""
    w1 = WorkflowEntity(id="wf_1", name="One")
    workflow_repo.list_all.return_value = [w1]

    result_empty = workflow_service.list_workflows(query="")
    result_none = workflow_service.list_workflows(query=None)

    assert len(result_empty) == 1
    assert len(result_none) == 1


# --- get_workflow ---


def test_get_workflow_exists(workflow_service, workflow_repo):
    """get_workflow returns workflow when it exists."""
    w = WorkflowEntity(id="wf_1", name="Test")
    workflow_repo.get_by_id.return_value = w

    result = workflow_service.get_workflow("wf_1")

    assert result is w
    assert result.id == "wf_1"
    workflow_repo.get_by_id.assert_called_once_with("wf_1")


def test_get_workflow_not_found(workflow_service, workflow_repo):
    """get_workflow returns None when workflow does not exist."""
    workflow_repo.get_by_id.return_value = None

    result = workflow_service.get_workflow("non_existent")

    assert result is None


# --- get_workflow_detail ---


def test_get_workflow_detail_uses_main_branch_commit_sha(workflow_repo, run_repo):
    """get_workflow_detail enriches a workflow with commit_sha from main only."""
    git_service = Mock()
    git_service.current_branch.return_value = "feature-x"
    git_service.get_sha.return_value = "main-sha-123"
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        id="wf_1",
        name="Test Flow",
        filename="wf_1.yaml",
    )

    result = workflow_service.get_workflow_detail("wf_1")

    assert result.id == "wf_1"
    assert result.commit_sha == "main-sha-123"
    git_service.get_sha.assert_called_once_with("main", "custom/workflows/wf_1.yaml")
    workflow_repo.get_by_id.assert_called_once_with("wf_1")


def test_get_workflow_detail_returns_none_commit_sha_when_not_committed_on_main(
    workflow_repo,
    run_repo,
):
    """get_workflow_detail returns null commit_sha when main has no commit for the file."""
    git_service = Mock()
    git_service.current_branch.return_value = "feature-x"
    git_service.get_sha.return_value = None
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        id="wf_2",
        name="Draft Flow",
        filename="wf_2.yaml",
    )

    result = workflow_service.get_workflow_detail("wf_2")

    assert result.id == "wf_2"
    assert result.commit_sha is None
    git_service.get_sha.assert_called_once_with("main", "custom/workflows/wf_2.yaml")


# --- create_workflow ---


def test_create_workflow_happy_path(workflow_service, workflow_repo):
    """create_workflow creates and returns workflow when data has id."""
    data = {"id": "wf_new", "name": "New Workflow"}
    created = WorkflowEntity(**data)
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "wf_new"
    assert result.name == "New Workflow"
    workflow_repo.create.assert_called_once_with(data)


def test_create_workflow_without_id(workflow_service, workflow_repo):
    """create_workflow works without id — repo generates it from filename."""
    data = {"name": "No ID Needed"}
    created = WorkflowEntity(id="no-id-needed-abc12", name="No ID Needed")
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "no-id-needed-abc12"
    workflow_repo.create.assert_called_once_with(data)


def test_create_workflow_commit_true_uses_repo_relative_yaml_path(workflow_repo, run_repo):
    """create_workflow should auto-commit the YAML file using the repo-relative path."""
    git_service = Mock()
    git_service.is_clean.return_value = False
    git_service.commit_to_branch.return_value = "abc123def456"
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.create.return_value = WorkflowEntity(
        id="wf_new",
        name="New Workflow",
    )

    result = workflow_service.create_workflow({"name": "New Workflow"})

    assert result.id == "wf_new"
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/workflows/wf_new.yaml"],
        "Create workflow: New Workflow",
    )


def test_create_workflow_commit_false_skips_auto_commit(workflow_repo, run_repo):
    """create_workflow(commit=False) must not auto-commit the new workflow."""
    git_service = Mock()
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.create.return_value = WorkflowEntity(
        id="wf_no_commit",
        name="No Commit Workflow",
    )

    result = workflow_service.create_workflow({"name": "No Commit Workflow"}, commit=False)

    assert result.id == "wf_no_commit"
    workflow_repo.create.assert_called_once_with({"name": "No Commit Workflow"})
    git_service.commit_to_branch.assert_not_called()


def test_create_workflow_requires_yaml(workflow_service, workflow_repo):
    """create_workflow should surface the canonical YAML-only contract."""
    workflow_repo.create.side_effect = InputValidationError("yaml is required")

    with pytest.raises(InputValidationError, match="yaml is required"):
        workflow_service.create_workflow({"name": "No YAML"})


def test_create_workflow_does_not_fail_when_auto_commit_errors(workflow_repo):
    """Workflow creation should succeed even if the convenience git auto-commit cannot run."""
    git_service = Mock()
    git_service.is_clean.return_value = False
    git_service.commit_to_branch.side_effect = RuntimeError("checkout main failed")
    created = WorkflowEntity(id="wf_new", name="New Workflow")
    workflow_repo.create.return_value = created
    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    result = workflow_service.create_workflow({"name": "New Workflow"})

    assert result == created
    workflow_repo.create.assert_called_once_with({"name": "New Workflow"})
    git_service.commit_to_branch.assert_called_once()


# --- update_workflow ---


def test_update_workflow_happy_path(workflow_service, workflow_repo):
    """update_workflow updates and returns workflow when it exists."""
    data = {"name": "Updated Name"}
    updated = WorkflowEntity(id="wf_1", name="Updated Name")
    workflow_repo.update.return_value = updated

    result = workflow_service.update_workflow("wf_1", data)

    assert result.id == "wf_1"
    assert result.name == "Updated Name"
    workflow_repo.update.assert_called_once_with("wf_1", data)


def test_update_workflow_not_found(workflow_service, workflow_repo):
    """update_workflow raises WorkflowNotFound when workflow does not exist."""
    workflow_repo.update.side_effect = WorkflowNotFound("Workflow wf_missing not found")

    with pytest.raises(WorkflowNotFound) as exc_info:
        workflow_service.update_workflow("wf_missing", {"name": "New"})

    assert "wf_missing" in str(exc_info.value)


def test_update_workflow_requires_yaml(workflow_service, workflow_repo):
    """update_workflow should reject name-only updates that bypass raw YAML."""
    workflow_repo.update.side_effect = InputValidationError("yaml is required")

    with pytest.raises(InputValidationError, match="yaml is required"):
        workflow_service.update_workflow("wf_1", {"name": "Renamed"})


# --- commit_workflow ---


def test_commit_workflow_writes_current_state_and_returns_commit_metadata(workflow_repo):
    """commit_workflow writes the draft payload, commits it to main, and returns commit metadata."""
    git_service = Mock()
    git_service.commit_to_branch.return_value = "abc123def456"
    saved = WorkflowEntity(
        id="wf_1",
        name="Updated Flow",
        yaml="workflow:\n  name: Updated Flow\n",
        canvas_state={
            "nodes": [{"id": "node-1"}],
            "edges": [],
            "viewport": {"x": 1, "y": 2, "zoom": 0.75},
            "selected_node_id": "node-1",
            "canvas_mode": "dag",
        },
    )
    workflow_repo.update.return_value = saved

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    draft = {
        "yaml": "workflow:\n  name: Updated Flow\n",
        "canvas_state": {
            "nodes": [{"id": "node-1"}],
            "edges": [],
            "viewport": {"x": 1, "y": 2, "zoom": 0.75},
            "selected_node_id": "node-1",
            "canvas_mode": "dag",
        },
    }

    result = workflow_service.commit_workflow("wf_1", draft, "Save workflow to main")

    assert result == {"hash": "abc123def456", "message": "Save workflow to main"}
    workflow_repo.update.assert_called_once_with("wf_1", draft)
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        [
            "custom/workflows/wf_1.yaml",
            "custom/workflows/.canvas/wf_1.canvas.json",
        ],
        "Save workflow to main",
    )


def test_commit_workflow_stages_only_workflow_owned_files(workflow_repo):
    """commit_workflow must not stage unrelated worktree changes during an explicit save."""
    git_service = Mock()
    git_service.commit_to_branch.return_value = "abc123def456"
    workflow_repo.update.return_value = WorkflowEntity(id="wf_1", name="Updated Flow")

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    workflow_service.commit_workflow(
        "wf_1",
        {"yaml": "workflow:\n  name: Updated Flow\n"},
        "Save workflow to main",
    )

    _, files, _ = git_service.commit_to_branch.call_args.args
    assert files == ["custom/workflows/wf_1.yaml"]
    assert "README.md" not in files
    assert ".env" not in files


def test_commit_workflow_does_not_attempt_git_commit_when_persisting_the_draft_fails(workflow_repo):
    """Atomic save contract: if the workflow write fails, the main-branch commit must never start."""
    git_service = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        id="wf_1",
        name="Original Flow",
        yaml="workflow:\n  name: Original Flow\n",
    )
    workflow_repo.update.side_effect = OSError("disk full")

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    with pytest.raises(OSError, match="disk full"):
        workflow_service.commit_workflow(
            "wf_1",
            {"yaml": "workflow:\n  name: Updated Flow\n"},
            "Save workflow to main",
        )

    git_service.commit_to_branch.assert_not_called()


def test_commit_workflow_requires_yaml_before_touching_git(workflow_repo):
    """Explicit saves must fail fast when the draft omits canonical YAML."""
    git_service = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        id="wf_1",
        name="Original Flow",
        yaml="workflow:\n  name: Original Flow\n",
    )
    workflow_repo.update.side_effect = InputValidationError("yaml is required")

    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    with pytest.raises(InputValidationError, match="yaml is required"):
        workflow_service.commit_workflow(
            "wf_1",
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
        id="wf_1",
        name="Original Flow",
        yaml="workflow:\n  name: Original Flow\n",
        canvas_state=previous_canvas_state,
    )
    workflow_repo.get_by_id.return_value = previous
    workflow_repo.update.side_effect = [
        WorkflowEntity(
            id="wf_1",
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
        workflow_service.commit_workflow("wf_1", draft, "Save workflow to main")

    assert workflow_repo.update.call_args_list == [
        call("wf_1", draft),
        call(
            "wf_1",
            {
                "yaml": "workflow:\n  name: Original Flow\n",
                "canvas_state": previous_canvas_state,
            },
        ),
    ]
    git_service.commit_to_branch.assert_called_once()


# --- delete_workflow ---


def test_delete_workflow_cascades_runs_before_deleting_yaml_and_returns_runs_deleted(
    workflow_repo,
    run_repo,
):
    """delete_workflow should remove DB runs before YAML and report the cascade count."""
    tracker = Mock()
    git_service = Mock()
    git_service.is_clean.return_value = False
    workflow_repo.get_by_id.return_value = WorkflowEntity(id="wf_1", name="Research Flow")
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 3
    tracker.attach_mock(run_repo, "run_repo")
    tracker.attach_mock(workflow_repo, "workflow_repo")
    tracker.attach_mock(git_service, "git_service")

    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)

    result = workflow_service.delete_workflow("wf_1")

    assert result == {"id": "wf_1", "deleted": True, "runs_deleted": 3}
    assert tracker.mock_calls[:4] == [
        call.workflow_repo.get_by_id("wf_1"),
        call.run_repo.delete_runs_for_workflow("wf_1", force=False),
        call.workflow_repo.delete("wf_1"),
        call.git_service.is_clean(),
    ]
    git_service.commit_to_branch.assert_called_once()


def test_delete_workflow_force_true_deletes_even_with_active_runs(
    workflow_repo,
    run_repo,
):
    """force=True should cascade runs and still delete the workflow shell."""
    git_service = Mock()
    git_service.is_clean.return_value = False
    workflow_repo.get_by_id.return_value = WorkflowEntity(id="wf_1", name="Research Flow")
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 2

    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)

    result = workflow_service.delete_workflow("wf_1", force=True)

    assert result == {"id": "wf_1", "deleted": True, "runs_deleted": 2}
    run_repo.delete_runs_for_workflow.assert_called_once_with("wf_1", force=True)
    workflow_repo.delete.assert_called_once_with("wf_1")
    git_service.commit_to_branch.assert_called_once()


def test_delete_workflow_zero_runs_still_deletes_workflow_cleanly(workflow_repo, run_repo):
    """Deleting a workflow with no historical runs should still remove the workflow."""
    workflow_repo.get_by_id.return_value = WorkflowEntity(id="wf_1", name="Research Flow")
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 0

    workflow_service = WorkflowService(workflow_repo, run_repo)

    result = workflow_service.delete_workflow("wf_1")

    assert result == {"id": "wf_1", "deleted": True, "runs_deleted": 0}
    run_repo.delete_runs_for_workflow.assert_called_once_with("wf_1", force=False)
    workflow_repo.delete.assert_called_once_with("wf_1")


def test_delete_workflow_raises_workflow_has_active_runs_without_deleting_yaml(
    workflow_repo,
    run_repo,
):
    """Active runs should block workflow deletion until force=True is used."""
    from runsight_api.domain.errors import WorkflowHasActiveRuns

    run_repo.delete_runs_for_workflow.side_effect = WorkflowHasActiveRuns(
        "Workflow wf_1 has active runs"
    )

    workflow_service = WorkflowService(workflow_repo, run_repo)

    with pytest.raises(WorkflowHasActiveRuns):
        workflow_service.delete_workflow("wf_1", force=False)

    workflow_repo.delete.assert_not_called()


def test_delete_workflow_not_found(workflow_service, workflow_repo, run_repo):
    """delete_workflow raises WorkflowNotFound when workflow does not exist."""
    run_repo.delete_runs_for_workflow.return_value = 0
    workflow_repo.delete.return_value = False

    with pytest.raises(WorkflowNotFound) as exc_info:
        workflow_service.delete_workflow("non_existent")

    assert "non_existent" in str(exc_info.value)
