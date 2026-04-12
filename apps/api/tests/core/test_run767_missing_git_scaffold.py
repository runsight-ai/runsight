"""Red tests for RUN-767: scaffold_project must degrade when git is missing."""

from pathlib import Path

import pytest
import yaml

from runsight_api.core.project import MARKER_FILE, scaffold_project


class TestScaffoldProjectMissingGit:
    """`scaffold_project` should still build the local project skeleton."""

    def test_creates_project_files_even_when_git_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PATH", "")

        scaffold_project(tmp_path)

        marker = tmp_path / MARKER_FILE
        assert marker.is_file(), ".runsight-project marker was not created"
        data = yaml.safe_load(marker.read_text(encoding="utf-8"))
        assert data["base_path"] == "."
        assert data["version"] == 1
        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        gitignore = tmp_path / ".gitignore"
        assert gitignore.is_file()
        assert ".canvas/" in gitignore.read_text(encoding="utf-8")
        assert not (tmp_path / ".git").exists()

    def test_logs_warning_when_git_is_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog
    ):
        monkeypatch.setenv("PATH", "")

        with caplog.at_level("WARNING"):
            scaffold_project(tmp_path)

        assert any(
            "git" in message.lower()
            and ("unavailable" in message.lower() or "disabled" in message.lower())
            for message in caplog.messages
        ), "Expected a warning that Git/GitOps is unavailable"
