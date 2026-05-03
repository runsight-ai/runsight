"""Smoke coverage for library soul_ref discovery during workflow parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
from parser_yaml_helpers import write_custom_soul_file, write_workflow_file
from runsight_core.yaml.parser import parse_workflow_yaml


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    return write_workflow_file(
        base_dir,
        yaml_content,
        default_id="library-soul-fixture-workflow",
        default_kind="workflow",
    )


def _write_soul_file(base_dir: Path, name: str, *, role: str, prompt: str) -> None:
    write_custom_soul_file(base_dir, name, role=role, prompt=prompt)


def _unwrap(block):
    inner = getattr(block, "inner_block", block)
    return getattr(inner, "block", inner)


def test_parse_workflow_yaml_resolves_library_soul_refs_for_llm_block_shapes(
    tmp_path: Path,
) -> None:
    for soul_name, role in {
        "researcher": "Researcher",
        "evaluator": "Evaluator",
        "summarizer": "Summarizer",
        "agent_a": "Agent A",
        "agent_b": "Agent B",
    }.items():
        _write_soul_file(tmp_path, soul_name, role=role, prompt=f"You are {role}.")

    path = _write_workflow_file(
        tmp_path,
        """\
        version: "1.0"
        id: library-soul-smoke
        kind: workflow
        config:
          model_name: fixture-model
        blocks:
          research:
            type: linear
            soul_ref: researcher
          check:
            type: gate
            soul_ref: evaluator
            eval_key: research
          merge:
            type: synthesize
            soul_ref: summarizer
            input_block_ids:
              - research
          fan:
            type: dispatch
            exits:
              - id: branch_a
                label: Branch A
                soul_ref: agent_a
                task: Do task A
              - id: branch_b
                label: Branch B
                soul_ref: agent_b
                task: Do task B
        workflow:
          name: library_soul_smoke
          entry: research
          transitions:
            - from: research
              to: check
            - from: check
              to: merge
            - from: merge
              to: fan
            - from: fan
              to: null
        """,
    )

    workflow = parse_workflow_yaml(path)

    assert _unwrap(workflow.blocks["research"]).soul.role == "Researcher"
    assert _unwrap(workflow.blocks["check"]).soul.role == "Evaluator"
    assert _unwrap(workflow.blocks["merge"]).soul.role == "Summarizer"
    fan = _unwrap(workflow.blocks["fan"])
    assert [branch.soul.role for branch in fan.branches] == ["Agent A", "Agent B"]


def test_missing_library_soul_ref_reports_available_souls_and_fixture_directory(
    tmp_path: Path,
) -> None:
    _write_soul_file(tmp_path, "alpha", role="Alpha", prompt="A.")
    _write_soul_file(tmp_path, "beta", role="Beta", prompt="B.")
    path = _write_workflow_file(
        tmp_path,
        """\
        version: "1.0"
        id: missing-soul-smoke
        kind: workflow
        config:
          model_name: fixture-model
        blocks:
          step:
            type: linear
            soul_ref: gamma
        workflow:
          name: missing_soul_smoke
          entry: step
          transitions:
            - from: step
              to: null
        """,
    )

    with pytest.raises(ValueError) as exc_info:
        parse_workflow_yaml(path)

    error = str(exc_info.value)
    assert "gamma" in error
    assert "alpha" in error
    assert "beta" in error
    assert "custom/souls/" in error
