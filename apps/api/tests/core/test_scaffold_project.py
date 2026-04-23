"""Tests for workspace scaffolding under the RUN-963 contract."""

from pathlib import Path

from runsight_api.core.config import Settings, ensure_project_dirs
from runsight_api.core.project import scaffold_project


class TestScaffoldProject:
    def test_creates_custom_dirs_and_gitignore_without_marker(self, tmp_path: Path):
        scaffold_project(tmp_path)

        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert (tmp_path / ".gitignore").is_file()
        assert not (tmp_path / ".runsight-project").exists()

    def test_removes_legacy_marker_file_when_present(self, tmp_path: Path):
        legacy_marker = tmp_path / ".runsight-project"
        legacy_marker.write_text("version: 1\nbase_path: .\n", encoding="utf-8")

        scaffold_project(tmp_path)

        assert not legacy_marker.exists()

    def test_existing_gitignore_keeps_user_content_and_gains_runsight_entry(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n.env\n", encoding="utf-8")

        scaffold_project(tmp_path)

        content = gitignore.read_text(encoding="utf-8")
        assert "node_modules/" in content
        assert ".env" in content
        assert ".runsight/" in content

    def test_scaffold_is_idempotent_for_existing_workspace(self, tmp_path: Path):
        sentinel = tmp_path / "custom" / "workflows" / "sentinel.yaml"
        scaffold_project(tmp_path)
        sentinel.write_text("name: sentinel\n", encoding="utf-8")

        scaffold_project(tmp_path)

        assert sentinel.is_file()
        assert sentinel.read_text(encoding="utf-8") == "name: sentinel\n"


class TestEnsureProjectDirsUsesScaffold:
    def test_startup_creates_runsight_and_canvas_without_marker(self, tmp_path: Path):
        settings = Settings(base_path=str(tmp_path))

        ensure_project_dirs(settings)

        assert (tmp_path / ".runsight").is_dir()
        assert (tmp_path / "custom" / "workflows" / ".canvas").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert not (tmp_path / ".runsight-project").exists()

    def test_startup_removes_legacy_marker_file(self, tmp_path: Path):
        legacy_marker = tmp_path / ".runsight-project"
        legacy_marker.write_text("version: 1\nbase_path: .\n", encoding="utf-8")
        settings = Settings(base_path=str(tmp_path))

        ensure_project_dirs(settings)

        assert not legacy_marker.exists()
