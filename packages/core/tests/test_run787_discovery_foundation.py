from __future__ import annotations

from pathlib import Path

import pytest


class ParsedYaml(str):
    id: str

    def __new__(cls, value: str, entity_id: str) -> "ParsedYaml":
        item = str.__new__(cls, value)
        item.id = entity_id
        return item


def test_discovery_package_exports_foundation_types() -> None:
    from runsight_core.yaml.discovery._base import (
        AssetType,
        BaseScanner,
        ScanError,
        ScanIndex,
        ScanResult,
    )

    assert AssetType.SOUL.name == "SOUL"
    assert AssetType.TOOL.name == "TOOL"
    assert AssetType.WORKFLOW.name == "WORKFLOW"
    assert ScanError(file_path=Path("x.yaml"), message="oops").message == "oops"
    assert BaseScanner is not None
    assert ScanResult is not None
    assert ScanIndex is not None


def test_base_scanner_is_abstract_and_scans_filesystem_yaml(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            assert path.suffix in {".yaml", ".yml"}
            assert raw_yaml.strip()
            return ParsedYaml(raw_yaml.strip(), path.stem)

    with pytest.raises(TypeError):
        BaseScanner(tmp_path)

    assets_dir = tmp_path / "custom" / "test-assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "alpha.yaml").write_text("alpha: 1\n", encoding="utf-8")
    (assets_dir / "beta.yml").write_text("beta: 2\n", encoding="utf-8")
    (assets_dir / "notes.txt").write_text("ignore me\n", encoding="utf-8")

    index = StringScanner(tmp_path).scan()
    assert isinstance(index, ScanIndex)
    assert index.ids() == {"alpha": "alpha: 1", "beta": "beta: 2"}
    assert index.get("alpha") is not None
    assert index.get("custom/test-assets/alpha.yaml") is None
    assert index.get("custom/test-assets/beta.yml") is None
    assert index.without_ids({"alpha"}).ids() == {"beta": "beta: 2"}
    assert index.get("missing") is None


def test_base_scanner_resolve_ref_uses_embedded_id_index_only(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            return ParsedYaml(raw_yaml.strip(), path.stem)

    assets_dir = tmp_path / "custom" / "test-assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "ref_a.yaml").write_text("from_file: true\n", encoding="utf-8")
    (assets_dir / "ref_b.yml").write_text("from_file: true\n", encoding="utf-8")

    scanner = StringScanner(tmp_path)
    index = scanner.scan()

    resolved = scanner.resolve_ref("ref_a", index=index)
    assert resolved is not None
    assert resolved.stem == "ref_a"
    assert scanner.resolve_ref("ref_a.yaml") is None
    assert scanner.resolve_ref("ref_b") is None
    assert scanner.resolve_ref("custom/test-assets/ref_a.yaml", index=index) is None
    assert scanner.resolve_ref("custom/test-assets/ref_b.yml", index=index) is None


def test_base_scanner_git_scan_uses_git_service_and_ls_tree(tmp_path: Path, monkeypatch) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class FakeGitService:
        def __init__(self, repo_path: Path) -> None:
            self.repo_path = repo_path
            self.read_calls: list[tuple[str, str]] = []

        def read_file(self, path: str, ref: str) -> str:
            self.read_calls.append((path, ref))
            if path.endswith("alpha.yaml"):
                return "alpha: git\n"
            if path.endswith("beta.yml"):
                return "beta: git\n"
            raise AssertionError(f"unexpected path: {path}")

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            return ParsedYaml(raw_yaml.strip(), path.stem)

    git_service = FakeGitService(tmp_path)
    seen_commands: list[list[str]] = []

    class Completed:
        def __init__(self, stdout: str, returncode: int = 0) -> None:
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(cmd, cwd, capture_output, text, check):
        seen_commands.append(cmd)
        assert cwd == str(tmp_path)
        assert capture_output is True
        assert text is True
        assert check is False
        return Completed("custom/test-assets/alpha.yaml\ncustom/test-assets/beta.yml\n")

    monkeypatch.setattr("subprocess.run", fake_run)

    index = StringScanner(tmp_path).scan(git_ref="feature/test", git_service=git_service)
    assert seen_commands == [
        ["git", "ls-tree", "-r", "--name-only", "feature/test", "--", "custom/test-assets/"]
    ]
    assert git_service.read_calls == [
        ("custom/test-assets/alpha.yaml", "feature/test"),
        ("custom/test-assets/beta.yml", "feature/test"),
    ]
    assert index.ids() == {"alpha": "alpha: git", "beta": "beta: git"}


def test_base_scanner_git_scan_returns_empty_index_when_ls_tree_fails(
    tmp_path: Path, monkeypatch
) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class FakeGitService:
        def __init__(self, repo_path: Path) -> None:
            self.repo_path = repo_path

        def read_file(self, path: str, ref: str) -> str:
            raise AssertionError("read_file should not be called when ls-tree fails")

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            return ParsedYaml(raw_yaml.strip(), path.stem)

    class Completed:
        def __init__(self, stdout: str, returncode: int) -> None:
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(cmd, cwd, capture_output, text, check):
        return Completed("", 1)

    monkeypatch.setattr("subprocess.run", fake_run)

    index = StringScanner(tmp_path).scan(
        git_ref="feature/test", git_service=FakeGitService(tmp_path)
    )
    assert index.get_all() == []
    assert index.ids() == {}


def test_base_scanner_reports_invalid_yaml_with_filename(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            if raw_yaml.strip() == "[]":
                raise ValueError(f"{path.name}: YAML content is not a mapping")
            return ParsedYaml(raw_yaml.strip(), path.stem)

    assets_dir = tmp_path / "custom" / "test-assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "broken.yaml").write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="broken.yaml"):
        StringScanner(tmp_path).scan()


def test_base_scanner_skips_null_yaml_files(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            return ParsedYaml(raw_yaml.strip(), path.stem)

    assets_dir = tmp_path / "custom" / "test-assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "empty.yaml").write_text("null\n", encoding="utf-8")
    (assets_dir / "real.yaml").write_text("real: value\n", encoding="utf-8")

    index = StringScanner(tmp_path).scan()
    assert index.ids() == {"real": "real: value"}


def test_base_scanner_duplicate_ids_last_yaml_wins(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            return ParsedYaml(raw_yaml.strip(), path.stem)

    assets_dir = tmp_path / "custom" / "test-assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "duplicate.yaml").write_text("from_yaml: true\n", encoding="utf-8")
    (assets_dir / "duplicate.yml").write_text("from_yml: true\n", encoding="utf-8")

    index = StringScanner(tmp_path).scan()
    assert index.ids() == {"duplicate": "from_yml: true"}


def test_base_scanner_skips_missing_asset_dir(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class StringScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            return ParsedYaml(raw_yaml, path.stem)

    index = StringScanner(tmp_path).scan()
    assert index.get_all() == []
    assert index.ids() == {}


def test_base_scanner_requires_embedded_id(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery._base import BaseScanner

    class MissingIdScanner(BaseScanner[str]):
        asset_subdir = "custom/test-assets"

        def _parse_file(self, path: Path, raw_yaml: str) -> str:
            return raw_yaml.strip()

    assets_dir = tmp_path / "custom" / "test-assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "broken.yaml").write_text("broken: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="broken.yaml"):
        MissingIdScanner(tmp_path).scan()
