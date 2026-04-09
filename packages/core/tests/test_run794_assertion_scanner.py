"""Red tests for RUN-794: YAML assertion manifest discovery and validation."""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from textwrap import dedent

import pytest
import yaml


def _load_symbols():
    from runsight_core.yaml.discovery import AssertionScanner, BaseScanner, ScanIndex

    assertion_module = importlib.import_module("runsight_core.yaml.discovery._assertion")
    return (
        AssertionScanner,
        assertion_module.AssertionMeta,
        BaseScanner,
        ScanIndex,
        assertion_module,
    )


def _write_assertion_fixture(
    base_dir: Path,
    *,
    stem: str = "budget_guard",
    returns: str = "bool",
    source_name: str = "budget_guard.py",
    code: str = "def get_assert(args):\n    return True\n",
    params: dict | None = None,
    extra_fields: dict | None = None,
    manifest_overrides: dict | None = None,
    drop_fields: set[str] | None = None,
    write_source: bool = True,
    source_is_directory: bool = False,
) -> tuple[Path, Path]:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": "1.0",
        "name": "Budget Guard",
        "description": "Keeps cost under budget.",
        "returns": returns,
        "source": source_name,
    }
    if params is not None:
        manifest["params"] = params
    if extra_fields:
        manifest.update(extra_fields)
    if manifest_overrides:
        manifest.update(manifest_overrides)
    if drop_fields:
        for field in drop_fields:
            manifest.pop(field, None)

    manifest_path = assertions_dir / f"{stem}.yaml"
    source_path = assertions_dir / source_name
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    if write_source:
        if source_is_directory:
            source_path.mkdir()
        else:
            source_path.write_text(code, encoding="utf-8")
    return manifest_path, source_path


class TestAssertionScannerPublicSurface:
    def test_assertion_scanner_uses_base_scanner_pattern(self):
        AssertionScanner, AssertionMeta, BaseScanner, ScanIndex, assertion_module = _load_symbols()

        assert issubclass(AssertionScanner, BaseScanner)
        assert AssertionMeta.__module__ == assertion_module.AssertionMeta.__module__
        assert ScanIndex is not None

    def test_assertion_scanner_module_does_not_reintroduce_legacy_discover_custom_helpers(self):
        _, _, _, _, assertion_module = _load_symbols()

        source = Path(assertion_module.__file__).read_text(encoding="utf-8")
        assert re.search(r"(?<!\\w)discover_custom_(?!\\w)", source) is None
        assert not any(name.startswith("discover_custom_") for name in vars(assertion_module))

    def test_public_discovery_surface_does_not_export_legacy_discover_custom_helpers(self):
        import runsight_core.yaml.discovery as discovery_module

        assert not any(name.startswith("discover_custom_") for name in vars(discovery_module))


class TestDiscoverCustomAssertions:
    @pytest.mark.parametrize(
        ("drop_fields", "manifest_overrides", "expected_fragment"),
        [
            ({"version"}, None, "version"),
            (None, {"version": 1}, "version"),
            ({"name"}, None, "name"),
            (None, {"name": ""}, "name"),
            ({"description"}, None, "description"),
            (None, {"description": ""}, "description"),
            ({"returns"}, None, "returns"),
            (None, {"returns": ""}, "returns"),
            ({"source"}, None, "source"),
            (None, {"source": ""}, "source"),
        ],
    )
    def test_missing_or_invalid_required_manifest_fields_raise_file_specific_error(
        self,
        tmp_path: Path,
        drop_fields: set[str] | None,
        manifest_overrides: dict | None,
        expected_fragment: str,
    ):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(
            tmp_path,
            drop_fields=drop_fields,
            manifest_overrides=manifest_overrides,
        )

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert expected_fragment in message

    def test_missing_custom_assertions_directory_returns_empty_scan_index(self, tmp_path: Path):
        AssertionScanner, _, _, ScanIndex, _ = _load_symbols()

        result = AssertionScanner(tmp_path).scan()

        assert isinstance(result, ScanIndex)
        assert result.stems() == {}

    def test_valid_manifest_and_source_scan_into_assertion_meta(self, tmp_path: Path):
        AssertionScanner, AssertionMeta, _, _, _ = _load_symbols()
        manifest_path, source_path = _write_assertion_fixture(
            tmp_path,
            params={
                "type": "object",
                "properties": {"threshold": {"type": "number"}},
                "required": ["threshold"],
            },
        )

        index = AssertionScanner(tmp_path).scan()
        discovered = index.stems()

        assert set(discovered) == {"budget_guard"}
        assert isinstance(discovered["budget_guard"], AssertionMeta)
        meta = discovered["budget_guard"]
        assert meta.assertion_id == "budget_guard"
        assert meta.file_path.resolve() == manifest_path.resolve()
        assert meta.version == "1.0"
        assert meta.name == "Budget Guard"
        assert meta.description == "Keeps cost under budget."
        assert meta.returns == "bool"
        assert meta.code == source_path.read_text(encoding="utf-8")
        assert meta.params == {
            "type": "object",
            "properties": {"threshold": {"type": "number"}},
            "required": ["threshold"],
        }
        assert index.get("budget_guard") is not None
        assert index.get("custom/assertions/budget_guard.yaml") is not None

    def test_invalid_returns_value_raises_file_specific_error(self, tmp_path: Path):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(tmp_path, returns="number")

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert "bool" in message
        assert "grading_result" in message

    def test_extra_unsupported_fields_raise_value_error(self, tmp_path: Path):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(tmp_path, extra_fields={"timeout_seconds": 10})

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert "timeout_seconds" in message

    def test_missing_source_file_raises_file_specific_error(self, tmp_path: Path):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(tmp_path, write_source=False)

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert "budget_guard.py" in message
        assert "source" in message

    def test_unreadable_source_path_raises_file_specific_error(self, tmp_path: Path):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(tmp_path, source_is_directory=True)

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert "budget_guard.py" in message
        assert "source" in message

    @pytest.mark.parametrize(
        ("code", "expected_fragment"),
        [
            (
                dedent(
                    """\
                    def get_assert():
                        return True
                    """
                ),
                "get_assert",
            ),
            (
                dedent(
                    """\
                    def get_assert(config, context):
                        return True
                    """
                ),
                "get_assert",
            ),
            (
                dedent(
                    """\
                    def get_assert(payload):
                        return True
                    """
                ),
                "args",
            ),
        ],
    )
    def test_bad_get_assert_signature_raises_value_error(
        self, tmp_path: Path, code: str, expected_fragment: str
    ):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(
            tmp_path,
            code=code,
        )

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert expected_fragment in message

    def test_reserved_builtin_assertion_name_collision_raises_value_error(self, tmp_path: Path):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(tmp_path, stem="contains", source_name="contains.py")

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "contains.yaml" in message
        assert "contains" in message
        assert "builtin" in message or "reserved" in message
