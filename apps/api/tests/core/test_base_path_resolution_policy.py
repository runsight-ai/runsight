"""Base path resolution ignores legacy markers and ancestor custom workflows."""

from pathlib import Path

import pytest

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
