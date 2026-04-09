"""Red tests for RUN-794: YAML assertion manifest discovery and validation."""

from __future__ import annotations

import importlib
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

    manifest_path = assertions_dir / f"{stem}.yaml"
    source_path = assertions_dir / source_name
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    source_path.write_text(code, encoding="utf-8")
    return manifest_path, source_path


class TestAssertionScannerPublicSurface:
    def test_assertion_scanner_uses_base_scanner_pattern(self):
        AssertionScanner, AssertionMeta, BaseScanner, ScanIndex, assertion_module = _load_symbols()

        assert issubclass(AssertionScanner, BaseScanner)
        assert AssertionMeta.__module__ == assertion_module.AssertionMeta.__module__
        assert ScanIndex is not None

    def test_assertion_scanner_module_does_not_reintroduce_legacy_discover_custom_assets(self):
        _, _, _, _, assertion_module = _load_symbols()

        source = Path(assertion_module.__file__).read_text(encoding="utf-8")
        assert "discover_custom_assets" not in source
        assert not hasattr(assertion_module, "discover_custom_assets")


class TestDiscoverCustomAssertions:
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

    def test_bad_get_assert_signature_raises_value_error(self, tmp_path: Path):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(
            tmp_path,
            code=dedent(
                """\
                def get_assert():
                    return True
                """
            ),
        )

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert "get_assert" in message

    def test_reserved_builtin_assertion_name_collision_raises_value_error(self, tmp_path: Path):
        AssertionScanner, _, _, _, _ = _load_symbols()
        _write_assertion_fixture(tmp_path, stem="contains", source_name="contains.py")

        with pytest.raises(ValueError) as exc_info:
            AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "contains.yaml" in message
        assert "contains" in message
        assert "builtin" in message or "reserved" in message
