"""Red tests for RUN-767: GitService must surface ServiceUnavailable when git is missing."""

from pathlib import Path

import pytest

from runsight_api.domain.errors import ServiceUnavailable
from runsight_api.logic.services.git_service import GitService


def _git(repo: Path, *args: str) -> None:
    import subprocess

    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# hello", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


class TestGitServiceMissingBinary:
    def test_current_branch_raises_service_unavailable_when_git_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        repo = _init_repo(tmp_path)
        monkeypatch.setenv("PATH", "")
        svc = GitService(repo_path=str(repo))

        with pytest.raises(ServiceUnavailable):
            svc.current_branch()
