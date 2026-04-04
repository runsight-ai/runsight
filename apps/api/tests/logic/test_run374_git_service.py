"""Red tests for RUN-374: GitService abstraction.

Tests verify that a GitService class exists at
``runsight_api.logic.services.git_service`` and exposes the methods
specified in the ticket AC:

- create_branch(name)
- read_file(path, branch)
- commit_to_branch(branch, files, message)
- get_sha(branch, path)
- delete_branch(name)
- current_branch()
- is_clean()

Each test uses ``tmp_path`` + ``git init`` for full isolation — no
mocking of subprocess, no reliance on the host repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers — tiny git wrappers for *arranging* test state
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside *repo* and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    """Create a bare-bones git repo with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# hello")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")
    return repo


# ---------------------------------------------------------------------------
# 0. Import smoke test
# ---------------------------------------------------------------------------


class TestGitServiceImport:
    """GitService must be importable from the canonical location."""

    def test_import_git_service_class(self):
        from runsight_api.logic.services.git_service import GitService

        assert GitService is not None

    def test_git_service_is_a_class(self):
        from runsight_api.logic.services.git_service import GitService

        assert isinstance(GitService, type)

    def test_git_service_accepts_repo_path(self, tmp_path: Path):
        """GitService must accept a repo root path on construction."""
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        assert svc is not None


# ---------------------------------------------------------------------------
# 1. current_branch()
# ---------------------------------------------------------------------------


class TestCurrentBranch:
    def test_returns_current_branch_name(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        branch = svc.current_branch()
        # git init defaults to "master" or "main" depending on config
        assert branch in ("main", "master")

    def test_returns_branch_after_checkout(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        _git(repo, "checkout", "-b", "feature-x")
        svc = GitService(repo_path=str(repo))

        assert svc.current_branch() == "feature-x"


# ---------------------------------------------------------------------------
# 2. is_clean()
# ---------------------------------------------------------------------------


class TestIsClean:
    def test_clean_repo_returns_true(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        assert svc.is_clean() is True

    def test_dirty_repo_returns_false(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        (repo / "dirty.txt").write_text("uncommitted")
        svc = GitService(repo_path=str(repo))

        assert svc.is_clean() is False

    def test_staged_but_uncommitted_is_not_clean(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        (repo / "staged.txt").write_text("staged")
        _git(repo, "add", "staged.txt")
        svc = GitService(repo_path=str(repo))

        assert svc.is_clean() is False


# ---------------------------------------------------------------------------
# 3. create_branch(name)
# ---------------------------------------------------------------------------


class TestCreateBranch:
    def test_creates_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        svc.create_branch("new-branch")

        # Verify via raw git
        branches = _git(repo, "branch", "--list", "new-branch")
        assert "new-branch" in branches

    def test_does_not_switch_current_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        original = svc.current_branch()

        svc.create_branch("another-branch")

        assert svc.current_branch() == original

    def test_raises_on_duplicate_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        svc.create_branch("dup")

        with pytest.raises(Exception):
            svc.create_branch("dup")


# ---------------------------------------------------------------------------
# 4. delete_branch(name)
# ---------------------------------------------------------------------------


class TestDeleteBranch:
    def test_deletes_existing_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        svc.create_branch("to-delete")

        svc.delete_branch("to-delete")

        branches = _git(repo, "branch", "--list", "to-delete")
        assert "to-delete" not in branches

    def test_raises_on_nonexistent_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        with pytest.raises(Exception):
            svc.delete_branch("ghost-branch")

    def test_raises_when_deleting_current_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        current = svc.current_branch()

        with pytest.raises(Exception):
            svc.delete_branch(current)


# ---------------------------------------------------------------------------
# 5. read_file(path, branch)
# ---------------------------------------------------------------------------


class TestReadFile:
    def test_reads_file_from_current_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        content = svc.read_file("README.md", svc.current_branch())
        assert content == "# hello"

    def test_reads_file_from_other_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        main_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")

        # Create a branch with different file content
        _git(repo, "checkout", "-b", "other")
        (repo / "README.md").write_text("# other branch")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "change on other")
        _git(repo, "checkout", main_branch)

        svc = GitService(repo_path=str(repo))
        content = svc.read_file("README.md", "other")
        assert content == "# other branch"

    def test_raises_on_missing_file(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        with pytest.raises(Exception):
            svc.read_file("nonexistent.txt", svc.current_branch())


# ---------------------------------------------------------------------------
# 6. get_sha(branch, path)
# ---------------------------------------------------------------------------


class TestGetSha:
    def test_returns_sha_string(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        sha = svc.get_sha(svc.current_branch(), "README.md")
        # SHA is a 40-char hex string
        assert isinstance(sha, str)
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)

    def test_sha_matches_git_log(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        branch = svc.current_branch()

        expected = _git(repo, "log", "-1", "--format=%H", "--", "README.md")
        actual = svc.get_sha(branch, "README.md")
        assert actual == expected

    def test_returns_none_or_raises_for_missing_path(self, tmp_path: Path):
        """get_sha should either return None or raise for a file with no commits."""
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.get_sha(svc.current_branch(), "no-such-file.yaml")
        # Accept None as a valid "not found" return
        assert result is None


# ---------------------------------------------------------------------------
# 7. commit_to_branch(branch, files, message)
# ---------------------------------------------------------------------------


class TestCommitToBranch:
    def test_commits_file_to_named_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        svc.create_branch("feature")
        (repo / "new.txt").write_text("new content")

        svc.commit_to_branch("feature", ["new.txt"], "add new.txt")

        # Verify commit landed on feature branch
        log = _git(repo, "log", "feature", "--oneline", "-1")
        assert "add new.txt" in log

    def test_commit_returns_sha(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        svc.create_branch("feat-sha")

        (repo / "file.txt").write_text("content")
        result = svc.commit_to_branch("feat-sha", ["file.txt"], "test sha")

        # Should return a commit SHA (str, 40 hex chars)
        assert isinstance(result, str)
        assert len(result) == 40

    def test_does_not_change_current_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        original = svc.current_branch()

        svc.create_branch("side")
        (repo / "side.txt").write_text("side content")
        svc.commit_to_branch("side", ["side.txt"], "side commit")

        assert svc.current_branch() == original

    def test_raises_on_empty_message(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))
        svc.create_branch("empty-msg")

        (repo / "file.txt").write_text("x")
        with pytest.raises(Exception):
            svc.commit_to_branch("empty-msg", ["file.txt"], "")

    def test_raises_on_nonexistent_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        (repo / "orphan.txt").write_text("data")
        with pytest.raises(Exception):
            svc.commit_to_branch("no-such-branch", ["orphan.txt"], "fail")
