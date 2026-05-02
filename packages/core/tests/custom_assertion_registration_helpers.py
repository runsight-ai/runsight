"""Fixture builders for custom assertion discovery and registration tests."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml
from runsight_core.assertions.base import AssertionContext


def load_registry_module():
    return importlib.import_module("runsight_core.assertions.registry")


def load_parser_module():
    return importlib.import_module("runsight_core.yaml.parser")


def load_discovery_module():
    return importlib.import_module("runsight_core.yaml.discovery")


def load_custom_assertion_module():
    return importlib.import_module("runsight_core.assertions.custom")


def write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def write_assertion_fixture(
    base_dir: Path,
    *,
    stem: str = "tone_check",
    name: str = "Tone Check Display Name",
    returns: str = "bool",
    source_name: str | None = None,
    code: str = "def get_assert(output, context):\n    return 'calm' in output\n",
    params: dict[str, Any] | None = None,
) -> Path:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)

    if source_name is None:
        source_name = f"{stem}.py"

    manifest_path = assertions_dir / f"{stem}.yaml"
    source_path = assertions_dir / source_name
    manifest = {
        "version": "1.0",
        "id": stem,
        "kind": "assertion",
        "name": name,
        "description": "Checks the output tone.",
        "returns": returns,
        "source": source_name,
    }
    if params is not None:
        manifest["params"] = params
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    source_path.write_text(code, encoding="utf-8")
    return manifest_path


def write_workflow_file(base_dir: Path, data: dict[str, Any]) -> Path:
    workflow_path = base_dir / "workflow.yaml"
    return write_yaml(workflow_path, data)


def workflow_with_block_assertion(assertion_type: str) -> dict[str, Any]:
    return {
        "version": "1.0",
        "id": "custom_assertion_parse_flow",
        "kind": "workflow",
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


def workflow_with_eval_assertion(assertion_type: str) -> dict[str, Any]:
    return {
        "version": "1.0",
        "id": "custom_assertion_eval_flow",
        "kind": "workflow",
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


def assertion_context(output: str = "calm response") -> AssertionContext:
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
        run_id="custom-assertion-registration-run",
        workflow_id="custom-assertion-registration-workflow",
    )
