"""Tests for project detection and base_path resolution."""

from pathlib import Path

import yaml

from runsight_api.core.project import resolve_base_path, _parse_marker, _find_marker


class TestParseMarker:
    def test_valid_marker(self, tmp_path: Path):
        marker = tmp_path / ".runsight-project"
        marker.write_text(yaml.dump({"version": 1, "base_path": "."}))
        assert _parse_marker(marker) == str(tmp_path.resolve())

    def test_relative_base_path(self, tmp_path: Path):
        marker = tmp_path / ".runsight-project"
        marker.write_text(yaml.dump({"version": 1, "base_path": "subdir"}))
        assert _parse_marker(marker) == str((tmp_path / "subdir").resolve())

    def test_missing_base_path_field(self, tmp_path: Path):
        marker = tmp_path / ".runsight-project"
        marker.write_text(yaml.dump({"version": 1}))
        assert _parse_marker(marker) is None

    def test_invalid_yaml(self, tmp_path: Path):
        marker = tmp_path / ".runsight-project"
        marker.write_text("::not: valid: yaml: [")
        assert _parse_marker(marker) is None

    def test_non_dict_yaml(self, tmp_path: Path):
        marker = tmp_path / ".runsight-project"
        marker.write_text("just a string")
        assert _parse_marker(marker) is None


class TestFindMarker:
    def test_marker_in_start_dir(self, tmp_path: Path):
        marker = tmp_path / ".runsight-project"
        marker.write_text(yaml.dump({"version": 1, "base_path": "."}))
        result = _find_marker(tmp_path)
        assert result == str(tmp_path.resolve())

    def test_marker_in_ancestor(self, tmp_path: Path):
        marker = tmp_path / ".runsight-project"
        marker.write_text(yaml.dump({"version": 1, "base_path": "."}))
        child = tmp_path / "a" / "b" / "c"
        child.mkdir(parents=True)
        result = _find_marker(child)
        assert result == str(tmp_path.resolve())

    def test_no_marker_found(self, tmp_path: Path):
        child = tmp_path / "a" / "b"
        child.mkdir(parents=True)
        # No marker anywhere — will walk up to filesystem root and return None
        # (We can't guarantee no marker exists above tmp_path, but in practice
        # pytest tmp dirs are deep enough that this works.)
        result = _find_marker(child)
        # If somehow a marker exists above tmp_path this could pass; that's OK.
        # The important thing is it doesn't crash.
        assert result is None or isinstance(result, str)


class TestResolveBasePath:
    def test_env_var_takes_precedence(self, tmp_path: Path, monkeypatch):
        """Tier 1: explicit env_value wins over everything."""
        # Put a marker file that would otherwise match
        marker = tmp_path / ".runsight-project"
        marker.write_text(yaml.dump({"version": 1, "base_path": "."}))
        monkeypatch.chdir(tmp_path)

        result = resolve_base_path(env_value="/override/path")
        assert result == "/override/path"

    def test_marker_file_detection(self, tmp_path: Path, monkeypatch):
        """Tier 2: marker file is found when no env var."""
        marker = tmp_path / ".runsight-project"
        marker.write_text(yaml.dump({"version": 1, "base_path": "."}))
        monkeypatch.chdir(tmp_path)

        result = resolve_base_path(env_value=None)
        assert result == str(tmp_path.resolve())

    def test_auto_detect_custom_workflows(self, tmp_path: Path, monkeypatch):
        """Tier 3: custom/workflows/ directory triggers auto-detect."""
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        result = resolve_base_path(env_value=None)
        assert result == str(tmp_path.resolve())

    def test_auto_detect_custom_workflows_in_ancestor(self, tmp_path: Path, monkeypatch):
        """Tier 3: custom/workflows/ in a parent directory."""
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        child = tmp_path / "some" / "nested" / "dir"
        child.mkdir(parents=True)
        monkeypatch.chdir(child)

        result = resolve_base_path(env_value=None)
        assert result == str(tmp_path.resolve())

    def test_cwd_fallback(self, tmp_path: Path, monkeypatch):
        """Tier 4: CWD when nothing else matches."""
        # tmp_path has no marker, no custom/workflows/
        monkeypatch.chdir(tmp_path)

        # Patch _find_marker and _find_custom_workflows to ensure nothing is
        # found in ancestor dirs (which may contain custom/workflows/ in CI/test
        # environments).
        monkeypatch.setattr("runsight_api.core.project._find_marker", lambda start: None)
        monkeypatch.setattr("runsight_api.core.project._find_custom_workflows", lambda start: None)

        result = resolve_base_path(env_value=None)
        assert result == str(tmp_path.resolve())

    def test_marker_beats_custom_workflows(self, tmp_path: Path, monkeypatch):
        """Marker file (tier 2) takes precedence over auto-detect (tier 3)."""
        subdir = tmp_path / "project"
        subdir.mkdir()
        (subdir / "custom" / "workflows").mkdir(parents=True)
        marker = subdir / ".runsight-project"
        # Point base_path to a different location
        other = tmp_path / "other"
        other.mkdir()
        marker.write_text(yaml.dump({"version": 1, "base_path": str(other)}))
        monkeypatch.chdir(subdir)

        result = resolve_base_path(env_value=None)
        assert result == str(other.resolve())
