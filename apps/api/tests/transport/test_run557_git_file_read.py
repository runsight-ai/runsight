"""Red-phase tests for RUN-557: Git file read endpoint.

Fork Recovery needs to read workflow YAML from a historical commit SHA.
``GitService.read_file`` already supports this, but there is no API
endpoint exposing it.

Tests verify:

1. ``GET /api/git/file?ref=X&path=Y`` returns file content from the
   specified git ref.
2. Works with both branch names and commit SHAs.
3. Path validation prevents directory traversal.
4. 404 if ref or path doesn't exist.
5. ``GitService.read_file`` param renamed from ``branch`` to ``ref``.

All tests are expected to FAIL against the current codebase because:
  - The git router has no ``/api/git/file`` endpoint.
  - ``GitService.read_file`` still uses the ``branch`` parameter name.
"""

import inspect
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runsight_api.core.config import settings
from runsight_api.logic.services.git_service import GitService
from runsight_api.main import app

# ---------------------------------------------------------------------------
# Helpers / Fixtures
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


def _get_head_sha(repo: Path) -> str:
    """Return the HEAD commit SHA of a repo."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


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
# 1. GET /api/git/file route exists
# ===================================================================


class TestGitFileRouteExists:
    """A GET /api/git/file endpoint must be registered."""

    def test_file_route_not_404(self, git_repo):
        """GET /api/git/file should not return 404 (route missing)."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "README.md"},
        )
        # 404 with a "Not Found" detail means the route doesn't exist —
        # that's the failure we expect in Red phase.
        # A 404 with "Git ref not found" or similar would be OK (route
        # exists, ref invalid).
        assert resp.status_code != 404 or "ref" in resp.json().get("error", "").lower(), (
            "Expected /api/git/file route to be registered, got 404"
        )

    def test_file_route_requires_ref_param(self, git_repo):
        """Omitting ref should return 422 (missing required query param)."""
        resp = client.get(
            "/api/git/file",
            params={"path": "README.md"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for missing 'ref' param, got {resp.status_code}"
        )

    def test_file_route_requires_path_param(self, git_repo):
        """Omitting path should return 422 (missing required query param)."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for missing 'path' param, got {resp.status_code}"
        )


# ===================================================================
# 2. Successful file reads (branch name and commit SHA)
# ===================================================================


class TestGitFileReadSuccess:
    """GET /api/git/file should return file content from a given git ref."""

    def test_read_file_by_branch_name(self, git_repo):
        """Reading a file by branch name returns its content."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "README.md"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body, f"Expected 'content' in response, got: {list(body.keys())}"
        assert body["content"] == "init"

    def test_read_file_by_commit_sha(self, git_repo):
        """Reading a file by commit SHA returns its content."""
        sha = _get_head_sha(git_repo)
        resp = client.get(
            "/api/git/file",
            params={"ref": sha, "path": "README.md"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert body["content"] == "init"

    def test_response_includes_ref_field(self, git_repo):
        """Response must echo back the ref that was used."""
        sha = _get_head_sha(git_repo)
        resp = client.get(
            "/api/git/file",
            params={"ref": sha, "path": "README.md"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "ref" in body, f"Expected 'ref' in response, got: {list(body.keys())}"
        assert body["ref"] == sha

    def test_read_file_from_historical_commit(self, git_repo):
        """Reading a file from a historical (non-HEAD) commit works."""
        first_sha = _get_head_sha(git_repo)

        # Modify the file and create a new commit
        (git_repo / "README.md").write_text("updated")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "update readme"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Reading the first commit should return the original content
        resp = client.get(
            "/api/git/file",
            params={"ref": first_sha, "path": "README.md"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "init", (
            f"Expected original content 'init' from historical SHA, got: {body['content']!r}"
        )

    def test_read_workflow_yaml(self, git_repo):
        """Reading a workflow YAML file works end-to-end."""
        wf_content = "name: my-workflow\nsteps: []\n"
        wf_path = git_repo / "custom" / "workflows" / "my-workflow.yaml"
        wf_path.write_text(wf_content)
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add workflow"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "custom/workflows/my-workflow.yaml"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == wf_content


# ===================================================================
# 3. 404 for missing ref or path
# ===================================================================


class TestGitFileNotFound:
    """GET /api/git/file must return 404 when ref or path doesn't exist.

    IMPORTANT: These tests must verify the endpoint's *own* 404, not
    FastAPI's generic "Not Found" (which would mean the route doesn't
    exist at all).  We check for the ``error`` key in the body — our
    error handler uses ``{"error": "..."}`` while FastAPI's default
    handler uses ``{"detail": "Not Found"}``.
    """

    def test_invalid_ref_returns_404_with_error_body(self, git_repo):
        """A garbage SHA should return 404 with an ``error`` field (not generic 'detail')."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef", "path": "README.md"},
        )
        assert resp.status_code == 404
        body = resp.json()
        # Must be our custom error response, not FastAPI's generic handler
        assert "error" in body, (
            f"Expected endpoint's own error response with 'error' key, "
            f"got generic FastAPI response: {body}"
        )
        assert "ref" in body["error"].lower() or "not found" in body["error"].lower()

    def test_nonexistent_path_returns_404_with_error_body(self, git_repo):
        """A path that doesn't exist should return 404 with an ``error`` field."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "does/not/exist.yaml"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body, (
            f"Expected endpoint's own error response with 'error' key, "
            f"got generic FastAPI response: {body}"
        )

    def test_invalid_branch_name_returns_404_with_error_body(self, git_repo):
        """A branch name that doesn't exist should return 404 with an ``error`` field."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "nonexistent-branch", "path": "README.md"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body, (
            f"Expected endpoint's own error response with 'error' key, "
            f"got generic FastAPI response: {body}"
        )


# ===================================================================
# 4. Path validation (directory traversal prevention)
# ===================================================================


class TestGitFilePathValidation:
    """Path param must be validated to prevent directory traversal."""

    def test_path_traversal_rejected(self, git_repo):
        """../../etc/passwd should be rejected with 400."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "../../etc/passwd"},
        )
        assert resp.status_code == 400
        body = resp.json()
        error = body.get("error", body.get("detail", "")).lower()
        assert "path" in error, f"Expected path validation error, got: {error!r}"

    def test_absolute_path_outside_project_rejected(self, git_repo):
        """/etc/passwd should be rejected with 400."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "/etc/passwd"},
        )
        assert resp.status_code == 400

    def test_flag_injection_in_path_rejected(self, git_repo):
        """Path starting with '-' should be rejected."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "--exec=whoami"},
        )
        assert resp.status_code == 400

    def test_empty_path_rejected(self, git_repo):
        """Empty path string should be rejected."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": ""},
        )
        # Either 400 (validation) or 422 (empty string fails query param)
        assert resp.status_code in (400, 422)

    def test_encoded_traversal_rejected(self, git_repo):
        """URL-encoded traversal sequences must be rejected."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "custom%2F..%2F..%2Fetc%2Fpasswd"},
        )
        assert resp.status_code == 400


# ===================================================================
# 5. Binary file returns raw content
# ===================================================================


class TestGitFileBinaryContent:
    """Binary files should return their raw content."""

    def test_binary_file_returns_content(self, git_repo):
        """A binary file at the path should still return content."""
        bin_path = git_repo / "data.bin"
        bin_path.write_bytes(b"\x00\x01\x02\x03")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add binary"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "data.bin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body


# ===================================================================
# 6. GitService.read_file param renamed from `branch` to `ref`
# ===================================================================


class TestGitServiceReadFileParamRenamed:
    """GitService.read_file should accept ``ref`` instead of ``branch``."""

    def test_read_file_has_ref_parameter(self):
        """The second positional parameter of read_file should be named 'ref'."""
        sig = inspect.signature(GitService.read_file)
        params = list(sig.parameters.keys())
        # params[0] is 'self', params[1] is 'path', params[2] should be 'ref'
        assert "ref" in params, f"Expected 'ref' parameter in GitService.read_file, got: {params}"

    def test_read_file_no_branch_parameter(self):
        """The old 'branch' parameter name should no longer exist."""
        sig = inspect.signature(GitService.read_file)
        params = list(sig.parameters.keys())
        assert "branch" not in params, (
            "GitService.read_file should no longer have a 'branch' parameter"
        )

    def test_read_file_works_with_ref_kwarg(self, git_repo):
        """Calling read_file(path, ref=...) should work."""
        svc = GitService(repo_path=git_repo)
        # This will raise TypeError if the param is still named 'branch'
        content = svc.read_file("README.md", ref="main")
        assert content == "init"


# ===================================================================
# 7. Response shape
# ===================================================================


class TestGitFileResponseShape:
    """Response must conform to the documented schema."""

    def test_response_has_content_and_ref(self, git_repo):
        """Response body must have exactly 'content' and 'ref' fields."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "README.md"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert "ref" in body

    def test_content_is_string(self, git_repo):
        """The 'content' field must be a string."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "README.md"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["content"], str)

    def test_ref_is_string(self, git_repo):
        """The 'ref' field must be a string."""
        resp = client.get(
            "/api/git/file",
            params={"ref": "main", "path": "README.md"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["ref"], str)
