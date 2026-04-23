"""Tests for workspace scaffolding under the RUN-963 contract."""

import subprocess
from pathlib import Path

from runsight_api.core.config import Settings, ensure_project_dirs
from runsight_api.core.project import scaffold_project


def _git(workspace_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=workspace_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_existing_repo(
    workspace_root: Path,
    *,
    marker_text: str = "version: 1\nbase_path: .\n",
    gitignore_text: str | None = None,
) -> Path:
    legacy_marker = workspace_root / ".runsight-project"
    legacy_marker.write_text(marker_text, encoding="utf-8")
    if gitignore_text is not None:
        (workspace_root / ".gitignore").write_text(gitignore_text, encoding="utf-8")

    _git(workspace_root, "init")
    _git(workspace_root, "config", "user.email", "runsight-tests@example.com")
    _git(workspace_root, "config", "user.name", "Runsight Tests")
    _git(workspace_root, "add", ".")
    _git(workspace_root, "commit", "-m", "Initial workspace state")
    return legacy_marker


class TestScaffoldProject:
    def test_creates_custom_dirs_and_gitignore_without_marker(self, tmp_path: Path):
        scaffold_project(tmp_path)

        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert (tmp_path / ".gitignore").is_file()
        assert not (tmp_path / ".runsight-project").exists()

    def test_existing_git_repo_keeps_tracked_legacy_marker_and_no_gitignore(self, tmp_path: Path):
        legacy_marker = _init_existing_repo(tmp_path)

        scaffold_project(tmp_path)

        assert legacy_marker.exists()
        assert legacy_marker.read_text(encoding="utf-8") == "version: 1\nbase_path: .\n"
        assert not (tmp_path / ".gitignore").exists()
        assert _git(tmp_path, "status", "--short").stdout.strip() == ""

    def test_existing_git_repo_keeps_gitignore_contents_unchanged(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        _init_existing_repo(
            tmp_path,
            gitignore_text="node_modules/\n.env\n",
        )

        scaffold_project(tmp_path)

        assert gitignore.read_text(encoding="utf-8") == "node_modules/\n.env\n"
        assert _git(tmp_path, "status", "--short").stdout.strip() == ""

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

    def test_startup_keeps_existing_git_repo_clean_when_tracking_legacy_marker(
        self, tmp_path: Path
    ):
        legacy_marker = _init_existing_repo(
            tmp_path,
            gitignore_text="node_modules/\n",
        )
        settings = Settings(base_path=str(tmp_path))

        ensure_project_dirs(settings)

        assert legacy_marker.exists()
        assert legacy_marker.read_text(encoding="utf-8") == "version: 1\nbase_path: .\n"
        assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n"
        assert _git(tmp_path, "status", "--short").stdout.strip() == ""
