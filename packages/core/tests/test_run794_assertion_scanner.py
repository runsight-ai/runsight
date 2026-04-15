"""Red tests for RUN-794: assertion manifest scanner architecture."""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from pydantic import BaseModel, ValidationError


def _load_discovery_module():
    import runsight_core.yaml.discovery as discovery_module

    return discovery_module


def _load_assertion_module():
    return importlib.import_module("runsight_core.yaml.discovery._assertion")


def _load_contract_module():
    return importlib.import_module("runsight_core.assertions.contract")


def _write_assertion_fixture(
    base_dir: Path,
    *,
    stem: str = "budget_guard",
    assertion_id: str | None = None,
    name: str = "Budget Guard Display",
    returns: str = "bool",
    source_name: str = "budget_guard.py",
    code: str = "def get_assert(output, context):\n    return True\n",
    params: dict | None = None,
    manifest_overrides: dict | None = None,
    drop_fields: set[str] | None = None,
    write_source: bool = True,
) -> tuple[Path, Path]:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": "1.0",
        "id": assertion_id or stem,
        "kind": "assertion",
        "name": name,
        "description": "Keeps cost under budget.",
        "returns": returns,
        "source": source_name,
    }
    if params is not None:
        manifest["params"] = params
    if manifest_overrides:
        manifest.update(manifest_overrides)
    if drop_fields:
        for field in drop_fields:
            manifest.pop(field, None)

    manifest_path = assertions_dir / f"{stem}.yaml"
    source_path = assertions_dir / source_name
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    if write_source:
        source_path.write_text(code, encoding="utf-8")
    return manifest_path, source_path


class TestAssertionScannerPublicSurface:
    def test_public_discovery_surface_exports_assertion_scanner_and_manifest_types(self):
        discovery_module = _load_discovery_module()

        assert hasattr(discovery_module, "AssertionScanner")
        assert hasattr(discovery_module, "AssertionManifest")
        assert hasattr(discovery_module, "AssertionMeta")
        assert issubclass(discovery_module.AssertionScanner, discovery_module.BaseScanner)

    def test_contract_module_exposes_shared_assertion_function_signature_constants(self):
        contract_module = _load_contract_module()

        assert contract_module.ASSERTION_FUNCTION_NAME == "get_assert"
        assert contract_module.ASSERTION_FUNCTION_PARAMS == ("output", "context")

    def test_assertion_module_does_not_reintroduce_legacy_discover_custom_helpers(self):
        assertion_module = _load_assertion_module()
        source = Path(assertion_module.__file__).read_text(encoding="utf-8")

        assert re.search(r"(?<!\w)discover_custom_(?!\w)", source) is None
        assert not any(name.startswith("discover_custom_") for name in vars(assertion_module))

    def test_public_discovery_surface_does_not_export_legacy_discover_custom_helpers(self):
        discovery_module = _load_discovery_module()

        assert not any(name.startswith("discover_custom_") for name in vars(discovery_module))

    def test_assertion_module_no_longer_exposes_hand_rolled_manifest_field_helpers(self):
        assertion_module = _load_assertion_module()

        assert not hasattr(assertion_module, "_require_string")
        assert not hasattr(assertion_module, "_require_optional_mapping")


class TestAssertionManifestModel:
    def test_assertion_manifest_is_a_pydantic_model(self):
        assertion_module = _load_assertion_module()

        assert issubclass(assertion_module.AssertionManifest, BaseModel)

    @pytest.mark.parametrize(
        "manifest_overrides",
        [
            {"timeout_seconds": 10},
            {"returns": "number"},
        ],
    )
    def test_assertion_manifest_model_rejects_extra_fields_and_invalid_returns(
        self, manifest_overrides: dict
    ):
        assertion_module = _load_assertion_module()
        raw = {
            "version": "1.0",
            "name": "Budget Guard Display",
            "description": "Keeps cost under budget.",
            "returns": "bool",
            "source": "budget_guard.py",
        }
        raw.update(manifest_overrides)

        with pytest.raises(ValidationError):
            assertion_module.AssertionManifest.model_validate(raw)

    @pytest.mark.parametrize("drop_field", ["version", "name", "description", "returns", "source"])
    def test_assertion_manifest_model_rejects_missing_required_fields(self, drop_field: str):
        assertion_module = _load_assertion_module()
        raw = {
            "version": "1.0",
            "name": "Budget Guard Display",
            "description": "Keeps cost under budget.",
            "returns": "bool",
            "source": "budget_guard.py",
        }
        raw.pop(drop_field)

        with pytest.raises(ValidationError):
            assertion_module.AssertionManifest.model_validate(raw)


class TestDiscoverCustomAssertions:
    def test_missing_custom_assertions_directory_returns_empty_scan_index(self, tmp_path: Path):
        discovery_module = _load_discovery_module()

        result = discovery_module.AssertionScanner(tmp_path).scan()

        assert isinstance(result, discovery_module.ScanIndex)
        assert result.ids() == {}

    def test_valid_manifest_and_source_scan_into_nested_assertion_meta(self, tmp_path: Path):
        discovery_module = _load_discovery_module()
        assertion_module = _load_assertion_module()
        manifest_path, source_path = _write_assertion_fixture(
            tmp_path,
            params={
                "type": "object",
                "properties": {"threshold": {"type": "number"}},
                "required": ["threshold"],
            },
        )

        index = discovery_module.AssertionScanner(tmp_path).scan()
        meta = index.ids()["budget_guard"]

        assert isinstance(meta, assertion_module.AssertionMeta)
        assert meta.assertion_id == "budget_guard"
        assert meta.file_path.resolve() == manifest_path.resolve()
        assert meta.code == source_path.read_text(encoding="utf-8")
        assert meta.manifest.name == "Budget Guard Display"
        assert meta.manifest.description == "Keeps cost under budget."
        assert meta.manifest.returns == "bool"
        assert meta.manifest.source == "budget_guard.py"
        assert meta.manifest.params == {
            "type": "object",
            "properties": {"threshold": {"type": "number"}},
            "required": ["threshold"],
        }

    def test_assertion_meta_does_not_expose_flattened_manifest_fields_directly(
        self, tmp_path: Path
    ):
        discovery_module = _load_discovery_module()
        _write_assertion_fixture(tmp_path)

        meta = discovery_module.AssertionScanner(tmp_path).scan().ids()["budget_guard"]

        assert not hasattr(meta, "name")
        assert not hasattr(meta, "description")
        assert not hasattr(meta, "returns")
        assert not hasattr(meta, "source")
        assert not hasattr(meta, "version")
        assert not hasattr(meta, "params")

    def test_embedded_id_is_canonical_identity_and_manifest_name_is_display_only(
        self, tmp_path: Path
    ):
        discovery_module = _load_discovery_module()
        _write_assertion_fixture(
            tmp_path,
            assertion_id="budget_guard_embedded",
            stem="budget_guard_embedded",
            name="Friendly Display Title",
            source_name="friendly_name.py",
        )

        meta = discovery_module.AssertionScanner(tmp_path).scan().ids()["budget_guard_embedded"]

        assert meta.assertion_id == "budget_guard_embedded"
        assert meta.manifest.name == "Friendly Display Title"
        assert meta.assertion_id != meta.manifest.name

    def test_scanner_uses_assertion_manifest_model_validate(self, tmp_path: Path, monkeypatch):
        discovery_module = _load_discovery_module()
        assertion_module = _load_assertion_module()
        _write_assertion_fixture(tmp_path)
        calls: list[object] = []
        original = assertion_module.AssertionManifest.model_validate

        def spy_model_validate(cls, raw: object, *args, **kwargs):
            calls.append(raw)
            return original(raw, *args, **kwargs)

        monkeypatch.setattr(
            assertion_module,
            "AssertionManifest",
            assertion_module.AssertionManifest,
        )
        monkeypatch.setattr(
            assertion_module.AssertionManifest,
            "model_validate",
            classmethod(spy_model_validate),
        )

        discovery_module.AssertionScanner(tmp_path).scan()

        assert calls
        assert isinstance(calls[0], dict)
        assert calls[0]["name"] == "Budget Guard Display"

    @pytest.mark.parametrize(
        ("manifest_overrides", "drop_fields", "expected_fragment"),
        [
            ({"timeout_seconds": 10}, None, "timeout_seconds"),
            ({"returns": "number"}, None, "returns"),
            (None, {"version"}, "version"),
        ],
    )
    def test_scanner_wraps_manifest_model_validation_errors_with_filename(
        self,
        tmp_path: Path,
        manifest_overrides: dict | None,
        drop_fields: set[str] | None,
        expected_fragment: str,
    ):
        discovery_module = _load_discovery_module()
        _write_assertion_fixture(
            tmp_path,
            manifest_overrides=manifest_overrides,
            drop_fields=drop_fields,
        )

        with pytest.raises(ValueError) as exc_info:
            discovery_module.AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert expected_fragment in message

    def test_scanner_accepts_shared_get_assert_output_context_contract(self, tmp_path: Path):
        discovery_module = _load_discovery_module()
        _write_assertion_fixture(
            tmp_path,
            code=dedent(
                """\
                def get_assert(output, context):
                    return output == "needle in haystack"
                """
            ),
        )

        meta = discovery_module.AssertionScanner(tmp_path).scan().ids()["budget_guard"]

        assert meta.code is not None

    @pytest.mark.parametrize(
        ("code", "expected_fragment"),
        [
            (
                dedent(
                    """\
                    def get_assert(args):
                        return True
                    """
                ),
                "output",
            ),
            (
                dedent(
                    """\
                    def get_assert(output):
                        return True
                    """
                ),
                "context",
            ),
            (
                dedent(
                    """\
                    def get_assert(output, context, extra):
                        return True
                    """
                ),
                "get_assert",
            ),
        ],
    )
    def test_scanner_rejects_legacy_or_wrong_arity_assertion_contract(
        self, tmp_path: Path, code: str, expected_fragment: str
    ):
        discovery_module = _load_discovery_module()
        _write_assertion_fixture(tmp_path, code=code)

        with pytest.raises(ValueError) as exc_info:
            discovery_module.AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "budget_guard.yaml" in message
        assert expected_fragment in message

    def test_reserved_builtin_collision_uses_embedded_id(self, tmp_path: Path):
        discovery_module = _load_discovery_module()
        _write_assertion_fixture(
            tmp_path,
            stem="different_slug",
            assertion_id="contains",
            name="Totally Different Display Name",
            source_name="contains.py",
        )

        with pytest.raises(ValueError) as exc_info:
            discovery_module.AssertionScanner(tmp_path).scan()

        message = str(exc_info.value)
        assert "different_slug.yaml" in message
        assert "contains" in message
        assert "builtin" in message or "reserved" in message
