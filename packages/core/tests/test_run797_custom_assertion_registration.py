"""Red tests for RUN-797: custom assertion discovery and registration wiring."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from runsight_core.assertions.base import AssertionContext
from runsight_core.assertions.registry import run_assertion
from runsight_core.eval.runner import run_eval
from runsight_core.yaml.parser import parse_workflow_yaml


def _load_registry_module():
    return importlib.import_module("runsight_core.assertions.registry")


def _load_parser_module():
    return importlib.import_module("runsight_core.yaml.parser")


def _load_discovery_module():
    return importlib.import_module("runsight_core.yaml.discovery")


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _write_assertion_fixture(
    base_dir: Path,
    *,
    stem: str = "tone_check",
    name: str = "Tone Check Display Name",
    returns: str = "bool",
    source_name: str | None = None,
    code: str = "def get_assert(output, context):\n    return 'calm' in output\n",
) -> Path:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)

    if source_name is None:
        source_name = f"{stem}.py"

    manifest_path = assertions_dir / f"{stem}.yaml"
    source_path = assertions_dir / source_name
    manifest = {
        "version": "1.0",
        "name": name,
        "description": "Checks the output tone.",
        "returns": returns,
        "source": source_name,
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    source_path.write_text(code, encoding="utf-8")
    return manifest_path


def _write_workflow_file(base_dir: Path, data: dict[str, Any]) -> Path:
    workflow_path = base_dir / "workflow.yaml"
    return _write_yaml(workflow_path, data)


def _workflow_with_block_assertion(assertion_type: str) -> dict[str, Any]:
    return {
        "version": "1.0",
        "config": {"model_name": "gpt-4o"},
        "blocks": {
            "analyze": {
                "type": "code",
                "code": "def main(data):\n    return 'fixture output'\n",
                "assertions": [{"type": assertion_type}],
            }
        },
        "workflow": {
            "name": "custom_assertion_parse_flow",
            "entry": "analyze",
            "transitions": [{"from": "analyze", "to": None}],
        },
    }


def _workflow_with_eval_assertion(assertion_type: str) -> dict[str, Any]:
    return {
        "version": "1.0",
        "config": {"model_name": "gpt-4o"},
        "blocks": {
            "analyze": {
                "type": "code",
                "code": "def main(data):\n    return 'ignored in fixture mode'\n",
            }
        },
        "workflow": {
            "name": "custom_assertion_eval_flow",
            "entry": "analyze",
            "transitions": [{"from": "analyze", "to": None}],
        },
        "eval": {
            "threshold": 1.0,
            "cases": [
                {
                    "id": "tone_case",
                    "fixtures": {"analyze": "calm response"},
                    "expected": {"analyze": [{"type": assertion_type}]},
                }
            ],
        },
    }


def _assertion_context(output: str = "calm response") -> AssertionContext:
    return AssertionContext(
        output=output,
        prompt="Summarize calmly.",
        prompt_hash="prompt-hash",
        soul_id="tone_soul",
        soul_version="1.0",
        block_id="analyze",
        block_type="code",
        cost_usd=0.01,
        total_tokens=42,
        latency_ms=12.0,
        variables={"topic": "calm"},
        run_id="run-1",
        workflow_id="workflow-1",
    )


class TestRegisterCustomAssertions:
    def test_register_custom_assertions_registers_slug_key_and_uses_assertion_id(
        self, tmp_path: Path, monkeypatch
    ):
        discovery_module = _load_discovery_module()
        registry_module = _load_registry_module()
        _write_assertion_fixture(
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
                "code": index.stems()["tone_check"].code,
                "returns": "bool",
            }
        ]
        assert captured_register == [("custom:tone_check", _Adapter)]

    def test_register_custom_assertions_is_idempotent_for_same_index(
        self, tmp_path: Path, monkeypatch
    ):
        discovery_module = _load_discovery_module()
        registry_module = _load_registry_module()
        _write_assertion_fixture(tmp_path, stem="tone_check", name="Tone Check Display Name")
        index = discovery_module.AssertionScanner(tmp_path).scan()
        build_calls: list[str] = []
        register_calls: list[str] = []

        class _Adapter:
            type = "custom:tone_check"

        monkeypatch.setattr(
            registry_module,
            "_build_adapter_class",
            lambda **kwargs: build_calls.append(kwargs["plugin_name"]) or _Adapter,
            raising=False,
        )
        monkeypatch.setattr(
            registry_module,
            "register_assertion",
            lambda key, handler: register_calls.append(key),
            raising=False,
        )

        registry_module.register_custom_assertions(index)
        registry_module.register_custom_assertions(index)

        assert build_calls == ["tone_check"]
        assert register_calls == ["custom:tone_check"]

    def test_register_custom_assertions_noops_when_index_is_empty(self, monkeypatch):
        discovery_module = _load_discovery_module()
        registry_module = _load_registry_module()
        register_calls: list[str] = []

        monkeypatch.setattr(
            registry_module,
            "register_assertion",
            lambda key, handler: register_calls.append(key),
            raising=False,
        )

        registry_module.register_custom_assertions(discovery_module.ScanIndex())

        assert register_calls == []


class TestAssertionScannerDuplicateStem:
    def test_assertion_scanner_rejects_duplicate_yaml_stems(self, tmp_path: Path, monkeypatch):
        discovery_module = _load_discovery_module()
        scanner = discovery_module.AssertionScanner(tmp_path)
        first = _write_assertion_fixture(tmp_path, stem="tone_check")
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
        registry_module = _load_registry_module()
        _write_assertion_fixture(
            tmp_path,
            stem="tone_check",
            name="Tone Check Display Name",
            code="def get_assert(output, context):\n    return output == 'calm response'\n",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            _workflow_with_block_assertion("custom:tone_check"),
        )
        monkeypatch.setattr(registry_module, "_REGISTRY", {}, raising=False)

        workflow = parse_workflow_yaml(str(workflow_path))
        block = workflow._blocks["analyze"]
        result = run_assertion(
            type=block.assertions[0]["type"],
            output="calm response",
            context=_assertion_context(),
        )

        assert result.passed is True

    def test_parse_workflow_yaml_treats_missing_custom_assertions_dir_as_no_op(
        self, tmp_path: Path, monkeypatch
    ):
        parser_module = _load_parser_module()
        discovery_module = _load_discovery_module()
        workflow_path = _write_workflow_file(
            tmp_path,
            _workflow_with_block_assertion("contains"),
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
        assert registered_indexes[0].stems() == {}

    def test_parse_workflow_yaml_surfaces_duplicate_custom_assertion_stem_errors(
        self, tmp_path: Path, monkeypatch
    ):
        parser_module = _load_parser_module()
        workflow_path = _write_workflow_file(
            tmp_path,
            _workflow_with_block_assertion("custom:tone_check"),
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
        registry_module = _load_registry_module()
        _write_assertion_fixture(
            tmp_path,
            stem="tone_check",
            name="Tone Check Display Name",
            code="def get_assert(output, context):\n    return output == 'calm response'\n",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            _workflow_with_eval_assertion("custom:tone_check"),
        )
        monkeypatch.setattr(registry_module, "_REGISTRY", {}, raising=False)

        result = await run_eval(str(workflow_path))

        assert result.passed is True
        assert result.case_results[0].block_results["analyze"].results[0].passed is True
