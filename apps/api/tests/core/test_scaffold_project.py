"""Red tests for RUN-139: Auto-scaffold project directories on API boot.

Tests for scaffold_project(base_path) which should:
- Create .runsight-project marker, custom/workflows/, custom/souls/, .gitignore
- Be idempotent (skip existing projects)
- Fill gaps in partial structures
- Never overwrite an existing .gitignore
"""

from pathlib import Path

import yaml

from runsight_api.core.project import MARKER_FILE, scaffold_project


class TestScaffoldEmptyDirectory:
    """Empty directory -> scaffold creates all expected files/dirs."""

    def test_creates_marker_file(self, tmp_path: Path):
        scaffold_project(tmp_path)
        marker = tmp_path / MARKER_FILE
        assert marker.is_file(), ".runsight-project marker was not created"

    def test_marker_contains_valid_yaml_with_base_path(self, tmp_path: Path):
        scaffold_project(tmp_path)
        marker = tmp_path / MARKER_FILE
        data = yaml.safe_load(marker.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "base_path" in data
        assert data["base_path"] == "."

    def test_marker_contains_version(self, tmp_path: Path):
        scaffold_project(tmp_path)
        marker = tmp_path / MARKER_FILE
        data = yaml.safe_load(marker.read_text(encoding="utf-8"))
        assert "version" in data
        assert data["version"] == 1

    def test_creates_custom_workflows_dir(self, tmp_path: Path):
        scaffold_project(tmp_path)
        assert (tmp_path / "custom" / "workflows").is_dir()

    def test_creates_custom_souls_dir(self, tmp_path: Path):
        scaffold_project(tmp_path)
        assert (tmp_path / "custom" / "souls").is_dir()

    def test_creates_gitignore(self, tmp_path: Path):
        scaffold_project(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.is_file(), ".gitignore was not created"

    def test_gitignore_contains_canvas_pattern(self, tmp_path: Path):
        scaffold_project(tmp_path)
        gitignore = tmp_path / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        assert ".canvas/" in content

    def test_returns_without_error(self, tmp_path: Path):
        """scaffold_project should not raise on an empty directory."""
        scaffold_project(tmp_path)  # should not raise


class TestScaffoldIdempotent:
    """Existing project -> no modification (idempotent)."""

    def _setup_full_project(self, base: Path):
        """Create a complete project structure."""
        marker = base / MARKER_FILE
        marker.write_text(yaml.dump({"version": 1, "base_path": "."}), encoding="utf-8")
        (base / "custom" / "workflows").mkdir(parents=True)
        (base / "custom" / "souls").mkdir(parents=True)
        gitignore = base / ".gitignore"
        gitignore.write_text("# existing gitignore\n.canvas/\n.runsight/\n", encoding="utf-8")

    def test_marker_not_overwritten(self, tmp_path: Path):
        self._setup_full_project(tmp_path)
        marker = tmp_path / MARKER_FILE
        original_content = marker.read_text(encoding="utf-8")
        original_mtime = marker.stat().st_mtime

        scaffold_project(tmp_path)

        assert marker.read_text(encoding="utf-8") == original_content
        assert marker.stat().st_mtime == original_mtime

    def test_gitignore_not_overwritten(self, tmp_path: Path):
        self._setup_full_project(tmp_path)
        gitignore = tmp_path / ".gitignore"
        original_content = gitignore.read_text(encoding="utf-8")

        scaffold_project(tmp_path)

        assert gitignore.read_text(encoding="utf-8") == original_content

    def test_existing_dirs_preserved(self, tmp_path: Path):
        self._setup_full_project(tmp_path)
        # Add a file inside workflows to prove dir is not recreated/wiped
        sentinel = tmp_path / "custom" / "workflows" / "my_workflow.yaml"
        sentinel.write_text("name: test")

        scaffold_project(tmp_path)

        assert sentinel.is_file()
        assert sentinel.read_text() == "name: test"


class TestScaffoldPartialStructure:
    """Partial structure -> fills in missing pieces."""

    def test_missing_souls_dir_created(self, tmp_path: Path):
        """Has marker and workflows, but no souls dir."""
        (tmp_path / MARKER_FILE).write_text(
            yaml.dump({"version": 1, "base_path": "."}), encoding="utf-8"
        )
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        (tmp_path / ".gitignore").write_text(".canvas/\n")

        scaffold_project(tmp_path)

        assert (tmp_path / "custom" / "souls").is_dir()

    def test_missing_workflows_dir_created(self, tmp_path: Path):
        """Has marker and souls, but no workflows dir."""
        (tmp_path / MARKER_FILE).write_text(
            yaml.dump({"version": 1, "base_path": "."}), encoding="utf-8"
        )
        (tmp_path / "custom" / "souls").mkdir(parents=True)

        scaffold_project(tmp_path)

        assert (tmp_path / "custom" / "workflows").is_dir()

    def test_missing_gitignore_created(self, tmp_path: Path):
        """Has marker and dirs, but no .gitignore."""
        (tmp_path / MARKER_FILE).write_text(
            yaml.dump({"version": 1, "base_path": "."}), encoding="utf-8"
        )
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        (tmp_path / "custom" / "souls").mkdir(parents=True)

        scaffold_project(tmp_path)

        gitignore = tmp_path / ".gitignore"
        assert gitignore.is_file()
        assert ".canvas/" in gitignore.read_text(encoding="utf-8")

    def test_missing_marker_created(self, tmp_path: Path):
        """Has dirs and gitignore, but no marker."""
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        (tmp_path / "custom" / "souls").mkdir(parents=True)
        (tmp_path / ".gitignore").write_text(".canvas/\n")

        scaffold_project(tmp_path)

        marker = tmp_path / MARKER_FILE
        assert marker.is_file()

    def test_existing_gitignore_not_overwritten_in_partial(self, tmp_path: Path):
        """Has custom .gitignore with user content; scaffold must not touch it."""
        user_gitignore_content = "# My custom ignores\nnode_modules/\n.env\n.runsight/\n"
        (tmp_path / ".gitignore").write_text(user_gitignore_content, encoding="utf-8")

        scaffold_project(tmp_path)

        assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == user_gitignore_content


class TestScaffoldLogging:
    """Startup log message indicates whether project was created or found."""

    def test_logs_created_message_for_new_project(self, tmp_path: Path, caplog):
        with caplog.at_level("INFO"):
            scaffold_project(tmp_path)
        assert any("Created" in msg or "created" in msg.lower() for msg in caplog.messages), (
            "Expected a log message containing 'Created' for a new project"
        )

    def test_logs_found_message_for_existing_project(self, tmp_path: Path, caplog):
        # Set up a full project first
        (tmp_path / MARKER_FILE).write_text(
            yaml.dump({"version": 1, "base_path": "."}), encoding="utf-8"
        )
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        (tmp_path / "custom" / "souls").mkdir(parents=True)
        (tmp_path / ".gitignore").write_text(".canvas/\n")

        with caplog.at_level("INFO"):
            scaffold_project(tmp_path)
        assert any(
            "Found" in msg or "found" in msg.lower() or "existing" in msg.lower()
            for msg in caplog.messages
        ), "Expected a log message indicating existing project was found"
