"""Tests for deterministic workspace resolution."""

from pathlib import Path

import pytest

from runsight_api.core.project import resolve_base_path


class TestResolveBasePath:
    def test_env_var_takes_precedence_over_launch_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        launch_dir = tmp_path / "launch"
        launch_dir.mkdir()
        monkeypatch.chdir(launch_dir)

        result = resolve_base_path(env_value="/override/path")

        assert result == "/override/path"

    def test_without_env_uses_launch_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        launch_dir = tmp_path / "nested" / "launch"
        launch_dir.mkdir(parents=True)
        monkeypatch.chdir(launch_dir)

        result = resolve_base_path(env_value=None)

        assert result == str(launch_dir.resolve())

    def test_without_env_ignores_legacy_marker_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        redirected = tmp_path / "redirected"
        redirected.mkdir()
        (tmp_path / ".runsight-project").write_text(
            f"version: 1\nbase_path: {redirected}\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        result = resolve_base_path(env_value=None)

        assert result == str(tmp_path.resolve())

    def test_without_env_does_not_walk_up_to_ancestor_custom_workflows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        launch_dir = tmp_path / "nested" / "launch"
        launch_dir.mkdir(parents=True)
        monkeypatch.chdir(launch_dir)

        result = resolve_base_path(env_value=None)

        assert result == str(launch_dir.resolve())
