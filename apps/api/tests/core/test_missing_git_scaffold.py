"""Tests for workspace scaffolding when git is unavailable."""

from pathlib import Path

import pytest

from runsight_api.core.project import scaffold_project


class TestScaffoldProjectMissingGit:
    def test_creates_workspace_dirs_without_git_or_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PATH", "")
        legacy_marker = tmp_path / ".runsight-project"
        legacy_marker.write_text("version: 1\nbase_path: .\n", encoding="utf-8")

        scaffold_project(tmp_path)

        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert (tmp_path / ".gitignore").is_file()
        assert ".runsight/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert not (tmp_path / ".git").exists()
        assert not legacy_marker.exists()

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
