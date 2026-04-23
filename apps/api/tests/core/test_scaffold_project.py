"""Tests for workspace scaffolding under the RUN-963 contract."""

import logging
import subprocess
from pathlib import Path

from sqlmodel import create_engine
from starlette.testclient import TestClient

from runsight_api.core.config import Settings, ensure_project_dirs
from runsight_api.core.project import scaffold_project
from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo


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


def _init_gitfile_worktree(
    tmp_path: Path,
    *,
    marker_text: str = "version: 1\nbase_path: .\n",
    gitignore_text: str | None = None,
) -> Path:
    primary_repo = tmp_path / "primary-repo"
    worktree_root = tmp_path / "linked-worktree"
    primary_repo.mkdir()

    _git(primary_repo, "init")
    _git(primary_repo, "config", "user.email", "runsight-tests@example.com")
    _git(primary_repo, "config", "user.name", "Runsight Tests")
    (primary_repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(primary_repo, "add", "README.md")
    _git(primary_repo, "commit", "-m", "Initial repository state")
    _git(primary_repo, "branch", "-M", "main")
    _git(primary_repo, "worktree", "add", "-b", "linked-worktree", str(worktree_root), "HEAD")

    legacy_marker = worktree_root / ".runsight-project"
    legacy_marker.write_text(marker_text, encoding="utf-8")
    if gitignore_text is not None:
        (worktree_root / ".gitignore").write_text(gitignore_text, encoding="utf-8")
    _git(worktree_root, "add", ".")
    _git(worktree_root, "commit", "-m", "Track workspace files")

    assert (worktree_root / ".git").is_file()
    return worktree_root


def _start_api(workspace_root: Path, monkeypatch) -> None:
    from runsight_api import main as main_module

    db_url = f"sqlite:///{workspace_root / '.runsight' / 'runsight.db'}"
    monkeypatch.setattr(main_module.app_settings, "base_path", str(workspace_root))
    monkeypatch.setattr(main_module.app_settings, "db_url", db_url)

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(main_module, "engine", engine)

    app = main_module.create_app()
    try:
        with TestClient(app):
            pass
    finally:
        engine.dispose()


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

    def test_existing_gitignore_without_repo_gets_canvas_and_runsight_patterns(
        self, tmp_path: Path
    ):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n.env\n", encoding="utf-8")

        scaffold_project(tmp_path)

        assert gitignore.read_text(encoding="utf-8") == (
            "node_modules/\n.env\n.canvas/\n.runsight/\n"
        )

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

    def test_gitfile_repo_keeps_tracked_marker_and_does_not_create_gitignore_or_commit(
        self, tmp_path: Path
    ):
        worktree_root = _init_gitfile_worktree(tmp_path)
        legacy_marker = worktree_root / ".runsight-project"
        head_before = _git(worktree_root, "rev-parse", "HEAD").stdout.strip()

        scaffold_project(worktree_root)

        assert (worktree_root / ".git").is_file()
        assert legacy_marker.exists()
        assert legacy_marker.read_text(encoding="utf-8") == "version: 1\nbase_path: .\n"
        assert not (worktree_root / ".gitignore").exists()
        assert _git(worktree_root, "rev-parse", "HEAD").stdout.strip() == head_before
        assert _git(worktree_root, "status", "--short").stdout.strip() == ""


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

    def test_startup_keeps_gitfile_repo_clean_when_tracking_marker_and_gitignore(
        self, tmp_path: Path
    ):
        worktree_root = _init_gitfile_worktree(
            tmp_path,
            gitignore_text="node_modules/\n.env\n",
        )
        legacy_marker = worktree_root / ".runsight-project"
        head_before = _git(worktree_root, "rev-parse", "HEAD").stdout.strip()
        settings = Settings(base_path=str(worktree_root))

        ensure_project_dirs(settings)

        assert (worktree_root / ".git").is_file()
        assert legacy_marker.exists()
        assert legacy_marker.read_text(encoding="utf-8") == "version: 1\nbase_path: .\n"
        assert (worktree_root / ".gitignore").read_text(encoding="utf-8") == (
            "node_modules/\n.env\n"
        )
        assert _git(worktree_root, "rev-parse", "HEAD").stdout.strip() == head_before
        assert _git(worktree_root, "status", "--short").stdout.strip() == ""


class TestFullApiStartupPreservesGitWorkspaceCleanliness:
    def test_full_api_startup_keeps_existing_git_repo_clean(self, tmp_path: Path, monkeypatch):
        legacy_marker = _init_existing_repo(
            tmp_path,
            gitignore_text="node_modules/\n",
        )

        _start_api(tmp_path, monkeypatch)

        assert (tmp_path / ".runsight").is_dir()
        assert (tmp_path / "custom" / "workflows" / ".canvas").is_dir()
        assert legacy_marker.exists()
        assert legacy_marker.read_text(encoding="utf-8") == "version: 1\nbase_path: .\n"
        assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n"
        assert _git(tmp_path, "status", "--short").stdout.strip() == ""

    def test_full_api_startup_keeps_gitfile_repo_clean_and_head_unchanged(
        self, tmp_path: Path, monkeypatch
    ):
        worktree_root = _init_gitfile_worktree(
            tmp_path,
            gitignore_text="node_modules/\n.env\n",
        )
        legacy_marker = worktree_root / ".runsight-project"
        head_before = _git(worktree_root, "rev-parse", "HEAD").stdout.strip()

        _start_api(worktree_root, monkeypatch)

        assert (worktree_root / ".git").is_file()
        assert (worktree_root / ".runsight").is_dir()
        assert (worktree_root / "custom" / "workflows" / ".canvas").is_dir()
        assert legacy_marker.exists()
        assert legacy_marker.read_text(encoding="utf-8") == "version: 1\nbase_path: .\n"
        assert (worktree_root / ".gitignore").read_text(encoding="utf-8") == (
            "node_modules/\n.env\n"
        )
        assert _git(worktree_root, "rev-parse", "HEAD").stdout.strip() == head_before
        assert _git(worktree_root, "status", "--short").stdout.strip() == ""

    def test_full_api_startup_keeps_existing_warning_loggers_enabled(
        self, tmp_path: Path, monkeypatch, caplog
    ):
        _init_existing_repo(tmp_path)

        _start_api(tmp_path, monkeypatch)

        malformed_provider = tmp_path / "custom" / "providers" / "broken.yaml"
        malformed_provider.parent.mkdir(parents=True, exist_ok=True)
        malformed_provider.write_text("not: valid: yaml: {{{}}", encoding="utf-8")

        repo = FileSystemProviderRepo(base_path=str(tmp_path))
        with caplog.at_level(logging.WARNING):
            repo.list_all()

        assert any("Failed to load provider file" in record.message for record in caplog.records)
