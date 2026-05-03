"""Workspace scaffold smoke coverage."""

from pathlib import Path

from runsight_api.core.config import Settings, ensure_project_dirs
from runsight_api.core.project import scaffold_project


def test_scaffold_project_creates_custom_dirs_and_gitignore(tmp_path: Path) -> None:
    scaffold_project(tmp_path)

    assert (tmp_path / "custom" / "workflows").is_dir()
    assert (tmp_path / "custom" / "souls").is_dir()
    assert (tmp_path / "custom" / "tools").is_dir()

    gitignore = tmp_path / ".gitignore"
    assert gitignore.is_file()
    assert ".canvas/" in gitignore.read_text(encoding="utf-8")
    assert ".runsight/" in gitignore.read_text(encoding="utf-8")


def test_scaffold_project_is_idempotent_for_existing_workspace(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\n", encoding="utf-8")

    scaffold_project(tmp_path)
    scaffold_project(tmp_path)

    assert gitignore.read_text(encoding="utf-8").count(".canvas/") == 1
    assert gitignore.read_text(encoding="utf-8").count(".runsight/") == 1
    assert "node_modules/" in gitignore.read_text(encoding="utf-8")


def test_startup_uses_scaffold_and_creates_runtime_dirs(tmp_path: Path) -> None:
    settings = Settings(base_path=str(tmp_path))

    ensure_project_dirs(settings)

    assert (tmp_path / ".runsight").is_dir()
    assert (tmp_path / "custom" / "workflows" / ".canvas").is_dir()
    assert (tmp_path / "custom" / "souls").is_dir()
    assert (tmp_path / "custom" / "tools").is_dir()
