"""Red tests for RUN-963: deterministic workspace resolution without markers."""

from pathlib import Path

import pytest

from runsight_api.core.config import Settings, ensure_project_dirs
from runsight_api.core.project import resolve_base_path


class TestResolveBasePathDeterministicPolicy:
    """Workspace resolution should never depend on legacy marker walk-up."""

    def test_ignores_legacy_marker_in_launch_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        redirected = tmp_path / "redirected"
        redirected.mkdir()
        marker = tmp_path / ".runsight-project"
        marker.write_text(
            f"version: 1\nbase_path: {redirected}\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        assert resolve_base_path(env_value=None) == str(tmp_path.resolve())

    def test_does_not_walk_up_to_ancestor_custom_workflows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        launch_dir = tmp_path / "nested" / "launch"
        launch_dir.mkdir(parents=True)
        monkeypatch.chdir(launch_dir)

        assert resolve_base_path(env_value=None) == str(launch_dir.resolve())


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
        monkeypatch.delenv("RUNSIGHT_BASE_PATH", raising=False)
        monkeypatch.delenv("RUNSIGHT_DB_URL", raising=False)

        settings = Settings()
        ensure_project_dirs(settings)

        assert Path(settings.base_path).resolve() == launch_dir.resolve()
        assert (launch_dir / ".runsight").is_dir()
        assert (launch_dir / "custom" / "workflows").is_dir()
        assert not (launch_dir / ".runsight-project").exists()
        assert not (redirected / ".runsight").exists()

    def test_bootstrap_does_not_create_legacy_marker_file(self, tmp_path: Path):
        settings = Settings(base_path=str(tmp_path))

        ensure_project_dirs(settings)

        assert (tmp_path / ".runsight").is_dir()
        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert not (tmp_path / ".runsight-project").exists()

    def test_explicit_base_path_wins_without_writing_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()
        base_path = tmp_path / "explicit-workspace"
        base_path.mkdir()
        monkeypatch.chdir(launch_dir)

        settings = Settings(base_path=str(base_path))
        ensure_project_dirs(settings)

        assert (base_path / ".runsight").is_dir()
        assert (base_path / "custom" / "workflows").is_dir()
        assert (base_path / "custom" / "souls").is_dir()
        assert not (base_path / ".runsight-project").exists()
        assert not (launch_dir / ".runsight").exists()
        assert not (launch_dir / "custom").exists()
