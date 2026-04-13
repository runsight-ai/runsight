"""Red tests for RUN-767: git router must return SERVICE_UNAVAILABLE when git is missing."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runsight_api.core.config import settings
from runsight_api.main import app


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


client = TestClient(app)


class TestGitStatusMissingBinary:
    def test_status_returns_service_unavailable_envelope_when_git_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        repo = _init_repo(tmp_path)
        original = settings.base_path
        settings.base_path = str(repo)
        monkeypatch.setenv("PATH", "")

        try:
            resp = client.get("/api/git/status")
        finally:
            settings.base_path = original

        assert resp.status_code == 503
        body = resp.json()
        assert body["error_code"] == "SERVICE_UNAVAILABLE"
        assert body["status_code"] == 503
