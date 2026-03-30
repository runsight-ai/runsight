"""Red-phase tests for RUN-423: sim-branch endpoint + RunCreate branch field.

ADR-001 requires: dirty state → create sim branch, commit YAML there, then run
from the sim branch.  These tests verify:

1. RunCreate schema accepts an optional `branch` field
2. POST /api/git/sim-branch route exists in the git router
3. The sim-branch endpoint accepts workflow_id + yaml_content and returns
   branch + commit_sha

All tests are expected to FAIL against the current codebase because:
  - RunCreate has no `branch` field
  - The git router has no /sim-branch endpoint
"""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runsight_api.core.config import settings
from runsight_api.main import app
from runsight_api.transport.schemas.runs import RunCreate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(tmp: Path) -> Path:
    """Initialise a throwaway git repo with custom/workflows/ directory."""
    (tmp / "custom" / "workflows").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    (tmp / "README.md").write_text("init")
    subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    return tmp


@pytest.fixture()
def git_repo(tmp_path):
    """Yield a temporary git repo path and override settings.base_path."""
    repo = _init_git_repo(tmp_path)
    original = settings.base_path
    settings.base_path = str(repo)
    yield repo
    settings.base_path = original


client = TestClient(app)


# ===================================================================
# 1. RunCreate schema accepts a `branch` field
# ===================================================================


class TestRunCreateBranchField:
    """RunCreate should accept an optional branch field defaulting to 'main'."""

    def test_branch_field_accepted(self):
        """RunCreate should accept branch without raising ValidationError."""
        payload = RunCreate(
            workflow_id="wf_test",
            branch="sim/my-workflow/20260330/abc12",
            source="manual",
        )
        assert payload.branch == "sim/my-workflow/20260330/abc12"

    def test_branch_defaults_to_main(self):
        """When branch is omitted, it should default to 'main'."""
        payload = RunCreate(workflow_id="wf_test")
        assert payload.branch == "main"

    def test_branch_in_model_fields(self):
        """The branch field must be declared in the schema's model_fields."""
        assert "branch" in RunCreate.model_fields

    def test_branch_serializes_to_dict(self):
        """branch should appear in .model_dump() output."""
        payload = RunCreate(
            workflow_id="wf_test",
            branch="sim/slug/20260330/x1y2z",
        )
        data = payload.model_dump()
        assert "branch" in data
        assert data["branch"] == "sim/slug/20260330/x1y2z"


# ===================================================================
# 2. POST /api/git/sim-branch route exists
# ===================================================================


class TestSimBranchRouteExists:
    """A POST /api/git/sim-branch endpoint must be registered."""

    def test_sim_branch_route_not_404(self, git_repo):
        """POST /api/git/sim-branch should not return 404 (route missing)."""
        resp = client.post(
            "/api/git/sim-branch",
            json={
                "workflow_id": "wf_hello",
                "yaml_content": "name: hello\nsteps: []\n",
            },
        )
        # 404 means the route doesn't exist at all — that's the failure we expect
        assert resp.status_code != 404, (
            "Expected /api/git/sim-branch route to be registered, got 404"
        )

    def test_sim_branch_returns_200_or_201(self, git_repo):
        """POST /api/git/sim-branch must return a successful status code."""
        resp = client.post(
            "/api/git/sim-branch",
            json={
                "workflow_id": "wf_test",
                "yaml_content": "name: test\n",
            },
        )
        assert resp.status_code in (200, 201), (
            f"Expected 200 or 201 from /api/git/sim-branch, got {resp.status_code}"
        )


# ===================================================================
# 3. Sim-branch endpoint request/response schema
# ===================================================================


class TestSimBranchEndpointSchema:
    """POST /api/git/sim-branch should accept workflow_id + yaml_content
    and return branch + commit_sha."""

    def test_returns_branch_field(self, git_repo):
        """Response must include a 'branch' field."""
        resp = client.post(
            "/api/git/sim-branch",
            json={
                "workflow_id": "wf_schema_test",
                "yaml_content": "name: schema_test\nsteps: []\n",
            },
        )
        body = resp.json()
        assert "branch" in body, f"Expected 'branch' in response, got keys: {list(body.keys())}"

    def test_returns_commit_sha_field(self, git_repo):
        """Response must include a 'commit_sha' field."""
        resp = client.post(
            "/api/git/sim-branch",
            json={
                "workflow_id": "wf_sha_test",
                "yaml_content": "name: sha_test\nsteps: []\n",
            },
        )
        body = resp.json()
        assert "commit_sha" in body, (
            f"Expected 'commit_sha' in response, got keys: {list(body.keys())}"
        )

    def test_branch_follows_sim_convention(self, git_repo):
        """Branch name must follow sim/{slug}/{date}/{id} convention."""
        resp = client.post(
            "/api/git/sim-branch",
            json={
                "workflow_id": "wf_convention",
                "yaml_content": "name: convention\nsteps: []\n",
            },
        )
        body = resp.json()
        branch = body.get("branch", "")
        assert branch.startswith("sim/"), f"Branch should start with 'sim/', got: {branch}"
        parts = branch.split("/")
        assert len(parts) == 4, (
            f"Branch should have 4 parts (sim/slug/date/id), got {len(parts)}: {branch}"
        )

    def test_commit_sha_is_hex_string(self, git_repo):
        """commit_sha must be a 40-char hex string (full SHA)."""
        resp = client.post(
            "/api/git/sim-branch",
            json={
                "workflow_id": "wf_hex_test",
                "yaml_content": "name: hex_test\nsteps: []\n",
            },
        )
        body = resp.json()
        sha = body.get("commit_sha", "")
        assert len(sha) == 40, f"Expected 40-char SHA, got length {len(sha)}: {sha}"
        assert all(c in "0123456789abcdef" for c in sha), f"SHA should be hex, got: {sha}"

    def test_rejects_missing_workflow_id(self, git_repo):
        """Omitting workflow_id should return 422."""
        resp = client.post(
            "/api/git/sim-branch",
            json={"yaml_content": "name: missing_id\n"},
        )
        assert resp.status_code == 422

    def test_rejects_missing_yaml_content(self, git_repo):
        """Omitting yaml_content should return 422."""
        resp = client.post(
            "/api/git/sim-branch",
            json={"workflow_id": "wf_missing_yaml"},
        )
        assert resp.status_code == 422

    def test_success_status_code(self, git_repo):
        """Successful sim-branch creation should return 200 or 201."""
        resp = client.post(
            "/api/git/sim-branch",
            json={
                "workflow_id": "wf_status_test",
                "yaml_content": "name: status_test\nsteps: []\n",
            },
        )
        assert resp.status_code in (200, 201), (
            f"Expected 200 or 201, got {resp.status_code}: {resp.text}"
        )
