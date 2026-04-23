"""Tests for config.ensure_project_dirs."""

from pathlib import Path

from runsight_api.core.config import Settings, ensure_project_dirs


def test_ensure_project_dirs_creates_missing(tmp_path: Path):
    """ensure_project_dirs creates runtime dirs under the selected workspace root."""
    s = Settings(base_path=str(tmp_path))
    ensure_project_dirs(s)

    assert (tmp_path / "custom" / "workflows").is_dir()
    assert (tmp_path / "custom" / "workflows" / ".canvas").is_dir()
    assert (tmp_path / ".runsight").is_dir()
    assert not (tmp_path / ".runsight-project").exists()


def test_ensure_project_dirs_idempotent(tmp_path: Path):
    """Calling ensure_project_dirs twice does not raise."""
    s = Settings(base_path=str(tmp_path))
    ensure_project_dirs(s)
    ensure_project_dirs(s)

    assert (tmp_path / "custom" / "workflows").is_dir()
    assert (tmp_path / ".runsight").is_dir()
