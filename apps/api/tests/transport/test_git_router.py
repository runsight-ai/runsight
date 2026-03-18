"""Red-phase tests for RUN-130: Git status, commit, diff, and log endpoints.

These tests exercise the git router at /api/git/*.  Each test creates an
isolated temporary git repo so we never touch the real runsight repo.
"""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.core.config import settings


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
    # Create an initial commit so HEAD exists
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


@pytest.fixture()
def non_git_dir(tmp_path):
    """Yield a plain directory (no .git) and override settings.base_path."""
    original = settings.base_path
    settings.base_path = str(tmp_path)
    yield tmp_path
    settings.base_path = original


client = TestClient(app)


# ===================================================================
# GET /api/git/status
# ===================================================================


class TestGitStatus:
    def test_status_clean_repo(self, git_repo):
        """A freshly-committed repo should report is_clean=true."""
        resp = client.get("/api/git/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "branch" in body
        assert body["is_clean"] is True
        assert body["uncommitted_files"] == []

    def test_status_dirty_repo(self, git_repo):
        """Adding an uncommitted workflow file should appear in the response."""
        wf = git_repo / "custom" / "workflows" / "hello.yaml"
        wf.write_text("name: hello\n")

        resp = client.get("/api/git/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_clean"] is False
        assert len(body["uncommitted_files"]) >= 1
        paths = [f["path"] for f in body["uncommitted_files"]]
        assert any("hello.yaml" in p for p in paths)

    def test_status_returns_branch_name(self, git_repo):
        """Branch name should be a non-empty string."""
        resp = client.get("/api/git/status")
        assert resp.status_code == 200
        branch = resp.json()["branch"]
        assert isinstance(branch, str)
        assert len(branch) > 0

    def test_status_uncommitted_file_has_status_field(self, git_repo):
        """Each uncommitted file entry must include a 'status' field."""
        wf = git_repo / "custom" / "workflows" / "wf.yaml"
        wf.write_text("name: wf\n")

        resp = client.get("/api/git/status")
        body = resp.json()
        for f in body["uncommitted_files"]:
            assert "path" in f
            assert "status" in f

    def test_status_non_git_dir(self, non_git_dir):
        """Requesting status on a non-git directory should return an error."""
        resp = client.get("/api/git/status")
        assert resp.status_code in (400, 500)
        body = resp.json()
        assert "error" in body or "detail" in body


# ===================================================================
# POST /api/git/commit
# ===================================================================


class TestGitCommit:
    def test_commit_stages_and_commits(self, git_repo):
        """A simple commit with a message should succeed."""
        wf = git_repo / "custom" / "workflows" / "new.yaml"
        wf.write_text("name: new\n")

        resp = client.post("/api/git/commit", json={"message": "add new workflow"})
        assert resp.status_code == 200
        body = resp.json()
        assert "hash" in body or "commit" in body

        # Verify the repo is now clean
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == ""

    def test_commit_with_custom_files(self, git_repo):
        """When a file list is provided, only those files should be staged."""
        wf1 = git_repo / "custom" / "workflows" / "a.yaml"
        wf2 = git_repo / "custom" / "workflows" / "b.yaml"
        wf1.write_text("name: a\n")
        wf2.write_text("name: b\n")

        resp = client.post(
            "/api/git/commit",
            json={
                "message": "commit only a",
                "files": ["custom/workflows/a.yaml"],
            },
        )
        assert resp.status_code == 200

        # b.yaml should still be uncommitted
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "b.yaml" in result.stdout

    def test_commit_empty_message_returns_error(self, git_repo):
        """An empty commit message should be rejected."""
        wf = git_repo / "custom" / "workflows" / "x.yaml"
        wf.write_text("name: x\n")

        resp = client.post("/api/git/commit", json={"message": ""})
        assert resp.status_code in (400, 422)

    def test_commit_no_message_field_returns_422(self, git_repo):
        """Omitting the message field entirely should return 422."""
        resp = client.post("/api/git/commit", json={})
        assert resp.status_code == 422

    def test_commit_non_git_dir(self, non_git_dir):
        """Committing in a non-git directory should return an error."""
        resp = client.post("/api/git/commit", json={"message": "nope"})
        assert resp.status_code in (400, 500)


# ===================================================================
# GET /api/git/diff
# ===================================================================


class TestGitDiff:
    def test_diff_shows_uncommitted_changes(self, git_repo):
        """Diff should return unified diff text for uncommitted changes."""
        wf = git_repo / "custom" / "workflows" / "diff_test.yaml"
        wf.write_text("name: diff_test\n")
        # Stage so diff HEAD shows it
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)

        resp = client.get("/api/git/diff")
        assert resp.status_code == 200
        body = resp.json()
        assert "diff" in body
        assert "diff_test.yaml" in body["diff"]

    def test_diff_clean_repo_returns_empty(self, git_repo):
        """A clean repo should return an empty diff."""
        resp = client.get("/api/git/diff")
        assert resp.status_code == 200
        body = resp.json()
        assert "diff" in body
        assert body["diff"] == "" or body["diff"].strip() == ""

    def test_diff_non_git_dir(self, non_git_dir):
        """Diff on a non-git directory should return an error."""
        resp = client.get("/api/git/diff")
        assert resp.status_code in (400, 500)


# ===================================================================
# GET /api/git/log
# ===================================================================


class TestGitLog:
    def test_log_returns_recent_commits(self, git_repo):
        """Log should return at least the initial commit."""
        resp = client.get("/api/git/log")
        assert resp.status_code == 200
        body = resp.json()
        assert "commits" in body
        assert len(body["commits"]) >= 1

    def test_log_commit_shape(self, git_repo):
        """Each commit entry must contain hash, message, date, author."""
        resp = client.get("/api/git/log")
        body = resp.json()
        commit = body["commits"][0]
        assert "hash" in commit
        assert "message" in commit
        assert "date" in commit
        assert "author" in commit

    def test_log_includes_new_commit(self, git_repo):
        """After a new commit, it should appear in the log."""
        readme = git_repo / "test_log.txt"
        readme.write_text("log test")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "log test commit"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        resp = client.get("/api/git/log")
        body = resp.json()
        messages = [c["message"] for c in body["commits"]]
        assert any("log test commit" in m for m in messages)

    def test_log_non_git_dir(self, non_git_dir):
        """Log on a non-git directory should return an error."""
        resp = client.get("/api/git/log")
        assert resp.status_code in (400, 500)
