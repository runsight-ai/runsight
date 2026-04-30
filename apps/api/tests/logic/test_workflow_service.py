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
    "runsight_core.identity",
    "runsight_core.yaml",
    "runsight_core.yaml.schema",
    "runsight_core.yaml.parser",
    "ruamel",
    "ruamel.yaml",
    "runsight_api.data.filesystem",
    "runsight_api.data.filesystem.workflow_repo",
    "runsight_api.data.repositories",
    "runsight_api.data.repositories.run_repo",
    "runsight_api.logic.services.workflow_service",
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
identity_pkg = types.ModuleType("runsight_core.identity")
yaml_pkg = types.ModuleType("runsight_core.yaml")
yaml_pkg.__path__ = []
schema_pkg = types.ModuleType("runsight_core.yaml.schema")
parser_pkg = types.ModuleType("runsight_core.yaml.parser")


class _EntityKind:
    SOUL = "soul"
    WORKFLOW = "workflow"
    TOOL = "tool"
    PROVIDER = "provider"
    ASSERTION = "assertion"


class _EntityRef:
    def __init__(self, kind, id):
        self.kind = kind
        self.id = id

    def __str__(self):
        return f"{self.kind}:{self.id}"


identity_pkg.EntityKind = _EntityKind
identity_pkg.EntityRef = _EntityRef
identity_pkg.validate_entity_id = lambda *_args, **_kwargs: None


class _RunsightWorkflowFile:
    @classmethod
    def model_validate(cls, data):
        return data


schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
parser_pkg.validate_tool_governance = lambda _: None
yaml_pkg.schema = schema_pkg
yaml_pkg.parser = parser_pkg
runsight_core.identity = identity_pkg
runsight_core.yaml = yaml_pkg
sys.modules["runsight_core"] = runsight_core
sys.modules["runsight_core.identity"] = identity_pkg
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
def run_read_model():
    mock = Mock()
    mock.get_workflow_health_metrics.return_value = {}
    return mock


@pytest.fixture
def workflow_service(workflow_repo, run_repo, run_read_model):
    return WorkflowService(workflow_repo, run_repo, run_read_model=run_read_model)


# --- list_workflows ---


def test_list_workflows_empty(workflow_service, workflow_repo):
    """list_workflows returns empty list when repo has no workflows."""
    workflow_repo.list_all.return_value = []

    result = workflow_service.list_workflows()

    assert result == []
    workflow_repo.list_all.assert_called_once()


def test_list_workflows_multiple(workflow_service, workflow_repo):
    """list_workflows returns all workflows from repo."""
    design_workflow = WorkflowEntity(kind="workflow", id="design-workflow", name="Design Flow")
    review_workflow = WorkflowEntity(kind="workflow", id="review-workflow", name="Review Flow")
    workflow_repo.list_all.return_value = [design_workflow, review_workflow]

    result = workflow_service.list_workflows()

    assert len(result) == 2
    assert result[0].id == "design-workflow"
    assert result[1].id == "review-workflow"


def test_list_workflows_with_query_filter(workflow_service, workflow_repo):
    """list_workflows filters by query (case-insensitive) in id or name."""
    customer_research = WorkflowEntity(
        kind="workflow", id="customer-research", name="Customer Research"
    )
    market_research = WorkflowEntity(kind="workflow", id="market-research", name="Market Study")
    incident_review = WorkflowEntity(kind="workflow", id="incident-review", name="Incident Review")
    workflow_repo.list_all.return_value = [customer_research, market_research, incident_review]

    result = workflow_service.list_workflows(query="research")

    assert len(result) == 2
    ids = [workflow.id for workflow in result]
    assert "customer-research" in ids
    assert "market-research" in ids
    assert "incident-review" not in ids


def test_list_workflows_query_matches_name(workflow_service, workflow_repo):
    """list_workflows matches query against name when present."""
    research_workflow = WorkflowEntity(
        kind="workflow", id="market-analysis", name="Customer Research"
    )
    review_workflow = WorkflowEntity(kind="workflow", id="support-triage", name="Support Triage")
    workflow_repo.list_all.return_value = [research_workflow, review_workflow]

    result = workflow_service.list_workflows(query="customer research")

    assert len(result) == 1
    assert result[0].id == "market-analysis"


def test_list_workflows_query_empty_string_returns_all(workflow_service, workflow_repo):
    """list_workflows with query='' or None returns all (falsy query = no filter)."""
    single_workflow = WorkflowEntity(kind="workflow", id="single-workflow", name="Single Flow")
    workflow_repo.list_all.return_value = [single_workflow]

    result_empty = workflow_service.list_workflows(query="")
    result_none = workflow_service.list_workflows(query=None)

    assert len(result_empty) == 1
    assert len(result_none) == 1


def test_list_workflows_returns_none_commit_sha_without_git_service(
    workflow_repo, run_repo, run_read_model
):
    """Workflow list metadata should keep commit_sha nullable when no git service is wired."""
    workflow_service = WorkflowService(workflow_repo, run_repo, run_read_model=run_read_model)
    workflow_repo.list_all.return_value = [
        WorkflowEntity(kind="workflow", id="workflow-without-git", name="No Git Flow")
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].id == "workflow-without-git"
    assert result[0].commit_sha is None
    run_read_model.get_workflow_health_metrics.assert_called_once_with(["workflow-without-git"])


def test_list_workflows_returns_none_commit_sha_when_current_branch_lookup_fails(
    workflow_repo,
    run_repo,
    run_read_model,
):
    """Workflow list metadata should not fall back to main when branch lookup fails."""
    git_service = Mock()
    git_service.current_branch.side_effect = RuntimeError("branch lookup failed")
    git_service.get_sha.side_effect = lambda branch, _path: (
        "main-sha-123" if branch == "main" else None
    )
    workflow_service = WorkflowService(
        workflow_repo,
        run_repo,
        git_service=git_service,
        run_read_model=run_read_model,
    )
    workflow_repo.list_all.return_value = [
        WorkflowEntity(kind="workflow", id="branch-lookup-workflow", name="Branch Failure Flow")
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].id == "branch-lookup-workflow"
    assert result[0].commit_sha is None
    run_read_model.get_workflow_health_metrics.assert_called_once_with(["branch-lookup-workflow"])


def test_list_workflows_returns_none_commit_sha_when_current_branch_has_no_commit(
    workflow_repo,
    run_repo,
    run_read_model,
):
    """Workflow list metadata should stay nullable when the current branch has no commit for a file."""
    git_service = Mock()
    git_service.current_branch.return_value = "feature-x"
    git_service.get_sha.return_value = None
    workflow_service = WorkflowService(
        workflow_repo,
        run_repo,
        git_service=git_service,
        run_read_model=run_read_model,
    )
    workflow_repo.list_all.return_value = [
        WorkflowEntity(kind="workflow", id="feature-only-workflow", name="Feature Branch Flow")
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].id == "feature-only-workflow"
    assert result[0].commit_sha is None
    git_service.get_sha.assert_called_once_with(
        "feature-x", "custom/workflows/feature-only-workflow.yaml"
    )


@pytest.mark.parametrize(
    ("branch_value", "case_id"),
    [
        ("", "empty"),
        ("HEAD", "detached_head"),
        (None, "non_string"),
    ],
)
def test_list_workflows_returns_none_commit_sha_for_invalid_current_branch_values(
    workflow_repo,
    run_repo,
    run_read_model,
    branch_value,
    case_id,
):
    """Workflow list metadata should treat invalid current branch values as missing SHAs."""
    git_service = Mock()
    git_service.current_branch.return_value = branch_value
    git_service.get_sha.return_value = f"unexpected-sha-for-{case_id}"
    workflow_service = WorkflowService(
        workflow_repo,
        run_repo,
        git_service=git_service,
        run_read_model=run_read_model,
    )
    workflow_repo.list_all.return_value = [
        WorkflowEntity(
            kind="workflow",
            id=f"invalid-branch-{case_id}-workflow",
            name="Invalid Branch Flow",
        )
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].commit_sha is None


# --- get_workflow ---


def test_get_workflow_exists(workflow_service, workflow_repo):
    """get_workflow returns workflow when it exists."""
    existing_workflow = WorkflowEntity(
        kind="workflow", id="existing-workflow", name="Existing Workflow"
    )
    workflow_repo.get_by_id.return_value = existing_workflow

    result = workflow_service.get_workflow("existing-workflow")

    assert result is existing_workflow
    assert result.id == "existing-workflow"
    workflow_repo.get_by_id.assert_called_once_with("existing-workflow")


def test_get_workflow_not_found(workflow_service, workflow_repo):
    """get_workflow returns None when workflow does not exist."""
    workflow_repo.get_by_id.return_value = None

    result = workflow_service.get_workflow("missing-workflow")

    assert result is None


# --- get_workflow_detail ---


def test_get_workflow_detail_uses_main_branch_commit_sha(workflow_repo, run_repo):
    """get_workflow_detail enriches a workflow with commit_sha from main only."""
    git_service = Mock()
    git_service.current_branch.return_value = "feature-x"
    git_service.get_sha.return_value = "main-sha-123"
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="published-workflow",
        name="Published Flow",
        filename="published-workflow.yaml",
    )

    result = workflow_service.get_workflow_detail("published-workflow")

    assert result.id == "published-workflow"
    assert result.commit_sha == "main-sha-123"
    git_service.get_sha.assert_called_once_with("main", "custom/workflows/published-workflow.yaml")
    workflow_repo.get_by_id.assert_called_once_with("published-workflow")


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
        kind="workflow",
        id="unpublished-draft-workflow",
        name="Draft Flow",
        filename="unpublished-draft-workflow.yaml",
    )

    result = workflow_service.get_workflow_detail("unpublished-draft-workflow")

    assert result.id == "unpublished-draft-workflow"
    assert result.commit_sha is None
    git_service.get_sha.assert_called_once_with(
        "main", "custom/workflows/unpublished-draft-workflow.yaml"
    )


# --- create_workflow ---


def test_create_workflow_returns_created_entity(workflow_service, workflow_repo):
    """create_workflow creates and returns workflow when data has id."""
    data = {"id": "created-workflow", "name": "Created Workflow"}
    created = WorkflowEntity(kind="workflow", **data)
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "created-workflow"
    assert result.name == "Created Workflow"
    workflow_repo.create.assert_called_once_with(data)


def test_create_workflow_without_id(workflow_service, workflow_repo):
    """create_workflow works without id — repo generates it from filename."""
    data = {"name": "No ID Needed"}
    created = WorkflowEntity(kind="workflow", id="generated-workflow-abc12", name="No ID Needed")
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "generated-workflow-abc12"
    workflow_repo.create.assert_called_once_with(data)


def test_create_workflow_commit_true_uses_repo_relative_yaml_path(workflow_repo, run_repo):
    """create_workflow should auto-commit the YAML file using the repo-relative path."""
    git_service = Mock()
    git_service.is_clean.return_value = False
    git_service.commit_to_branch.return_value = "abc123def456"
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.create.return_value = WorkflowEntity(
        kind="workflow",
        id="created-workflow",
        name="Created Workflow",
    )

    result = workflow_service.create_workflow({"name": "Created Workflow"})

    assert result.id == "created-workflow"
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/workflows/created-workflow.yaml"],
        "Create workflow: Created Workflow",
    )


def test_create_workflow_commit_false_skips_auto_commit(workflow_repo, run_repo):
    """create_workflow(commit=False) must not auto-commit the new workflow."""
    git_service = Mock()
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.create.return_value = WorkflowEntity(
        kind="workflow",
        id="draft-only-workflow",
        name="No Commit Workflow",
    )

    result = workflow_service.create_workflow({"name": "No Commit Workflow"}, commit=False)

    assert result.id == "draft-only-workflow"
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
    created = WorkflowEntity(kind="workflow", id="created-workflow", name="New Workflow")
    workflow_repo.create.return_value = created
    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    result = workflow_service.create_workflow({"name": "New Workflow"})

    assert result == created
    workflow_repo.create.assert_called_once_with({"name": "New Workflow"})
    git_service.commit_to_branch.assert_called_once()


# --- update_workflow ---


def test_update_workflow_returns_updated_entity(workflow_service, workflow_repo):
    """update_workflow updates and returns workflow when it exists."""
    data = {"name": "Updated Name"}
    updated = WorkflowEntity(kind="workflow", id="editable-workflow", name="Updated Name")
    workflow_repo.update.return_value = updated

    result = workflow_service.update_workflow("editable-workflow", data)

    assert result.id == "editable-workflow"
    assert result.name == "Updated Name"
    workflow_repo.update.assert_called_once_with("editable-workflow", data)


def test_update_workflow_not_found(workflow_service, workflow_repo):
    """update_workflow raises WorkflowNotFound when workflow does not exist."""
    workflow_repo.update.side_effect = WorkflowNotFound("Workflow missing-workflow not found")

    with pytest.raises(WorkflowNotFound) as exc_info:
        workflow_service.update_workflow("missing-workflow", {"name": "New"})

    assert "missing-workflow" in str(exc_info.value)


def test_update_workflow_requires_yaml(workflow_service, workflow_repo):
    """update_workflow should reject name-only updates that bypass raw YAML."""
    workflow_repo.update.side_effect = InputValidationError("yaml is required")

    with pytest.raises(InputValidationError, match="yaml is required"):
        workflow_service.update_workflow("editable-workflow", {"name": "Renamed"})


# --- commit_workflow ---


def test_commit_workflow_writes_current_state_and_returns_commit_metadata(workflow_repo):
    """commit_workflow writes the draft payload, commits it to main, and returns commit metadata."""
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


def test_commit_workflow_does_not_attempt_git_commit_when_persisting_the_draft_fails(workflow_repo):
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


# --- delete_workflow ---


def test_delete_workflow_cascades_runs_before_deleting_yaml_and_returns_runs_deleted(
    workflow_repo,
    run_repo,
):
    """delete_workflow should remove DB runs before YAML and report the cascade count."""
    tracker = Mock()
    git_service = Mock()
    git_service.is_clean.return_value = False
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow", id="research-workflow", name="Research Flow"
    )
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 3
    tracker.attach_mock(run_repo, "run_repo")
    tracker.attach_mock(workflow_repo, "workflow_repo")
    tracker.attach_mock(git_service, "git_service")

    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)

    result = workflow_service.delete_workflow("research-workflow")

    assert result == {"id": "research-workflow", "deleted": True, "runs_deleted": 3}
    assert tracker.mock_calls[:4] == [
        call.workflow_repo.get_by_id("research-workflow"),
        call.run_repo.delete_runs_for_workflow("research-workflow", force=False),
        call.workflow_repo.delete("research-workflow"),
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
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow", id="research-workflow", name="Research Flow"
    )
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 2

    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)

    result = workflow_service.delete_workflow("research-workflow", force=True)

    assert result == {"id": "research-workflow", "deleted": True, "runs_deleted": 2}
    run_repo.delete_runs_for_workflow.assert_called_once_with("research-workflow", force=True)
    workflow_repo.delete.assert_called_once_with("research-workflow")
    git_service.commit_to_branch.assert_called_once()


def test_delete_workflow_zero_runs_still_deletes_workflow_cleanly(workflow_repo, run_repo):
    """Deleting a workflow with no historical runs should still remove the workflow."""
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow", id="research-workflow", name="Research Flow"
    )
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 0

    workflow_service = WorkflowService(workflow_repo, run_repo)

    result = workflow_service.delete_workflow("research-workflow")

    assert result == {"id": "research-workflow", "deleted": True, "runs_deleted": 0}
    run_repo.delete_runs_for_workflow.assert_called_once_with("research-workflow", force=False)
    workflow_repo.delete.assert_called_once_with("research-workflow")


def test_delete_workflow_raises_workflow_has_active_runs_without_deleting_yaml(
    workflow_repo,
    run_repo,
):
    """Active runs should block workflow deletion until force=True is used."""
    from runsight_api.domain.errors import WorkflowHasActiveRuns

    run_repo.delete_runs_for_workflow.side_effect = WorkflowHasActiveRuns(
        "Workflow research-workflow has active runs"
    )

    workflow_service = WorkflowService(workflow_repo, run_repo)

    with pytest.raises(WorkflowHasActiveRuns):
        workflow_service.delete_workflow("research-workflow", force=False)

    workflow_repo.delete.assert_not_called()


def test_delete_workflow_not_found(workflow_service, workflow_repo, run_repo):
    """delete_workflow raises WorkflowNotFound when workflow does not exist."""
    run_repo.delete_runs_for_workflow.return_value = 0
    workflow_repo.delete.return_value = False

    with pytest.raises(WorkflowNotFound, match=r"workflow:missing-workflow"):
        workflow_service.delete_workflow("missing-workflow")
