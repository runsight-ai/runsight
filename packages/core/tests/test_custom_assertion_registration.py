"""Tests for custom assertion discovery and registration wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from custom_assertion_registration_helpers import (
    assertion_context,
    load_custom_assertion_module,
    load_discovery_module,
    load_parser_module,
    load_registry_module,
    workflow_with_block_assertion,
    workflow_with_eval_assertion,
    write_assertion_fixture,
    write_workflow_file,
)
from runsight_core.assertions.registry import run_assertion
from runsight_core.eval.runner import run_eval
from runsight_core.yaml.parser import parse_workflow_yaml


class TestRegisterCustomAssertions:
    def test_register_custom_assertions_registers_slug_key_and_uses_assertion_id(
        self, tmp_path: Path, monkeypatch
    ):
        discovery_module = load_discovery_module()
        registry_module = load_registry_module()
        write_assertion_fixture(
            tmp_path,
            stem="tone_check",
            name="Tone Check Display Name",
        )
        index = discovery_module.AssertionScanner(tmp_path).scan()
        captured_build: list[dict[str, Any]] = []
        captured_register: list[tuple[str, type]] = []

        class _Adapter:
            type = "custom:tone_check"

        def fake_build_adapter_class(*, plugin_name: str, code: str, returns: str) -> type:
            captured_build.append({"plugin_name": plugin_name, "code": code, "returns": returns})
            return _Adapter

        monkeypatch.setattr(
            registry_module,
            "_build_adapter_class",
            fake_build_adapter_class,
            raising=False,
        )
        monkeypatch.setattr(
            registry_module,
            "register_assertion",
            lambda key, handler: captured_register.append((key, handler)),
            raising=False,
        )

        registry_module.register_custom_assertions(index)

        assert captured_build == [
            {
                "plugin_name": "tone_check",
                "code": index.ids()["tone_check"].code,
                "returns": "bool",
            }
        ]
        assert captured_register == [("custom:tone_check", _Adapter)]

    def test_register_custom_assertions_is_idempotent_for_same_index(
        self, tmp_path: Path, monkeypatch
    ):
        discovery_module = load_discovery_module()
        registry_module = load_registry_module()
        write_assertion_fixture(tmp_path, stem="tone_check", name="Tone Check Display Name")
        index = discovery_module.AssertionScanner(tmp_path).scan()

        class _Adapter:
            type = "custom:tone_check"

        monkeypatch.setattr(
            registry_module,
            "_build_adapter_class",
            lambda **kwargs: _Adapter,
            raising=False,
        )
        monkeypatch.setattr(registry_module, "_REGISTRY", {}, raising=False)

        registry_module.register_custom_assertions(index)
        registry_module.register_custom_assertions(index)

        assert registry_module._get_handler("custom:tone_check") is _Adapter

    def test_register_custom_assertions_noops_when_index_is_empty(self, monkeypatch):
        discovery_module = load_discovery_module()
        registry_module = load_registry_module()
        register_calls: list[str] = []

        monkeypatch.setattr(
            registry_module,
            "register_assertion",
            lambda key, handler: register_calls.append(key),
            raising=False,
        )

        registry_module.register_custom_assertions(discovery_module.ScanIndex())

        assert register_calls == []

    def test_register_custom_assertions_stores_param_schemas_keyed_by_plugin_name(
        self, tmp_path: Path, monkeypatch
    ):
        custom_module = load_custom_assertion_module()
        discovery_module = load_discovery_module()
        registry_module = load_registry_module()
        params_schema = {
            "type": "object",
            "properties": {"budget": {"type": "number"}},
            "required": ["budget"],
        }
        write_assertion_fixture(
            tmp_path,
            stem="tone_check",
            name="Tone Check Display Name",
            params=params_schema,
        )
        index = discovery_module.AssertionScanner(tmp_path).scan()

        monkeypatch.setattr(custom_module, "_PARAM_SCHEMAS", {}, raising=False)
        monkeypatch.setattr(
            registry_module,
            "_build_adapter_class",
            lambda **kwargs: type("ToneCheckAdapter", (), {"type": "custom:tone_check"}),
            raising=False,
        )

        registry_module.register_custom_assertions(index)

        assert custom_module._PARAM_SCHEMAS == {"tone_check": params_schema}


class TestAssertionScannerDuplicateStem:
    def test_assertion_scanner_rejects_duplicate_yaml_stems(self, tmp_path: Path, monkeypatch):
        discovery_module = load_discovery_module()
        scanner = discovery_module.AssertionScanner(tmp_path)
        first = write_assertion_fixture(tmp_path, stem="tone_check")
        nested_dir = tmp_path / "custom" / "assertions" / "nested"
        nested_dir.mkdir(parents=True, exist_ok=True)
        second = nested_dir / "tone_check.yaml"
        second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
        (nested_dir / "tone_check.py").write_text(
            "def get_assert(output, context):\n    return True\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            scanner,
            "_glob_yaml_files",
            lambda directory: [first, second],
        )

        with pytest.raises(ValueError) as exc_info:
            scanner.scan()

        message = str(exc_info.value)
        assert "duplicate custom assertion id collision" in message
        assert "tone_check" in message


class TestParseWorkflowYamlCustomAssertionIntegration:
    def test_parse_workflow_yaml_registers_custom_assertions_for_dispatch(
        self, tmp_path: Path, monkeypatch
    ):
        registry_module = load_registry_module()
        write_assertion_fixture(
            tmp_path,
            stem="tone_check",
            name="Tone Check Display Name",
            code="def get_assert(output, context):\n    return output == 'calm response'\n",
        )
        workflow_path = write_workflow_file(
            tmp_path,
            workflow_with_block_assertion("custom:tone_check"),
        )
        monkeypatch.setattr(registry_module, "_REGISTRY", {}, raising=False)

        workflow = parse_workflow_yaml(str(workflow_path))
        block = workflow._blocks["analyze"]
        result = run_assertion(
            type=block.assertions[0]["type"],
            output="calm response",
            context=assertion_context(),
        )

        assert result.passed is True

    def test_parse_workflow_yaml_treats_missing_custom_assertions_dir_as_no_op(
        self, tmp_path: Path, monkeypatch
    ):
        parser_module = load_parser_module()
        discovery_module = load_discovery_module()
        workflow_path = write_workflow_file(
            tmp_path,
            workflow_with_block_assertion("contains"),
        )
        scanner_bases: list[Path] = []
        registered_indexes: list[object] = []

        class _AssertionScanner:
            def __init__(self, base_dir: str | Path) -> None:
                scanner_bases.append(Path(base_dir).resolve())

            def scan(self):
                return discovery_module.ScanIndex()

        def fake_register_custom_assertions(index) -> None:
            registered_indexes.append(index)

        monkeypatch.setattr(
            parser_module,
            "AssertionScanner",
            _AssertionScanner,
            raising=False,
        )
        monkeypatch.setattr(
            parser_module,
            "register_custom_assertions",
            fake_register_custom_assertions,
            raising=False,
        )

        workflow = parse_workflow_yaml(str(workflow_path))

        assert workflow.name == "custom_assertion_parse_flow"
        assert scanner_bases == [tmp_path.resolve()]
        assert len(registered_indexes) == 1
        assert isinstance(registered_indexes[0], discovery_module.ScanIndex)
        assert registered_indexes[0].ids() == {}

    def test_parse_workflow_yaml_surfaces_duplicate_custom_assertion_stem_errors(
        self, tmp_path: Path, monkeypatch
    ):
        parser_module = load_parser_module()
        workflow_path = write_workflow_file(
            tmp_path,
            workflow_with_block_assertion("custom:tone_check"),
        )

        class _AssertionScanner:
            def __init__(self, base_dir: str | Path) -> None:
                self.base_dir = Path(base_dir)

            def scan(self):
                raise ValueError("tone_check.yaml: duplicate custom assertion id collision")

        monkeypatch.setattr(
            parser_module,
            "AssertionScanner",
            _AssertionScanner,
            raising=False,
        )

        with pytest.raises(ValueError, match="duplicate custom assertion id collision"):
            parse_workflow_yaml(str(workflow_path))


class TestRunEvalCustomAssertionIntegration:
    @pytest.mark.asyncio
    async def test_run_eval_discovers_and_registers_custom_assertions_from_workflow_path(
        self, tmp_path: Path, monkeypatch
    ):
        registry_module = load_registry_module()
        write_assertion_fixture(
            tmp_path,
            stem="tone_check",
            name="Tone Check Display Name",
            code="def get_assert(output, context):\n    return output == 'calm response'\n",
        )
        workflow_path = write_workflow_file(
            tmp_path,
            workflow_with_eval_assertion("custom:tone_check"),
        )
        monkeypatch.setattr(registry_module, "_REGISTRY", {}, raising=False)

        result = await run_eval(str(workflow_path))

        assert result.passed is True
        assert result.case_results[0].block_results["analyze"].results[0].passed is True
