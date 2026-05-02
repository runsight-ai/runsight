"""Source startup bootstraps the selected workspace without legacy markers."""

from pathlib import Path

import pytest

from tests.core.workspace_resolution_helpers import _apply_minimal_process_env
from runsight_api.core.config import Settings, ensure_project_dirs


class TestStartupWorkspaceBootstrap:
    """Application startup should use the chosen workspace root directly."""

    def test_source_startup_uses_launch_directory_instead_of_ancestor_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        workspace_root = tmp_path / "workspace-root"
        workspace_root.mkdir()
        redirected = tmp_path / "redirected-root"
        redirected.mkdir()
        marker = workspace_root / ".runsight-project"
        marker.write_text(
            f"version: 1\nbase_path: {redirected}\n",
            encoding="utf-8",
        )
        launch_dir = workspace_root / "nested" / "launch"
        launch_dir.mkdir(parents=True)
        monkeypatch.chdir(launch_dir)
        _apply_minimal_process_env(monkeypatch, home=tmp_path / "home")

        settings = Settings()
        ensure_project_dirs(settings)

        assert Path(settings.base_path).resolve() == launch_dir.resolve()
        assert (launch_dir / ".runsight").is_dir()
        assert (launch_dir / "custom" / "workflows").is_dir()
        assert not (launch_dir / ".runsight-project").exists()
        assert not (redirected / ".runsight").exists()

    def test_bootstrap_does_not_create_legacy_marker_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _apply_minimal_process_env(monkeypatch, home=tmp_path / "home")
        settings = Settings(base_path=str(tmp_path))

        ensure_project_dirs(settings)

        assert (tmp_path / ".runsight").is_dir()
        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert not (tmp_path / ".runsight-project").exists()

    def test_runsight_base_path_env_wins_without_writing_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()
        base_path = tmp_path / "explicit-workspace"
        base_path.mkdir()
        monkeypatch.chdir(launch_dir)
        _apply_minimal_process_env(
            monkeypatch,
            home=tmp_path / "home",
            env={"RUNSIGHT_BASE_PATH": str(base_path)},
        )

        settings = Settings()
        ensure_project_dirs(settings)

        assert Path(settings.base_path).resolve() == base_path.resolve()
        assert (base_path / ".runsight").is_dir()
        assert (base_path / "custom" / "workflows").is_dir()
        assert (base_path / "custom" / "souls").is_dir()
        assert not (base_path / ".runsight-project").exists()
        assert not (launch_dir / ".runsight").exists()
        assert not (launch_dir / "custom").exists()
