"""Smoke coverage for completed YAML DX sugar at runtime."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml


class _ScriptedRunner:
    def __init__(self, behaviors=None):
        self.behaviors = behaviors or {}
        self.model_name = "gpt-4o-mini"
        self.attempts: dict[str, int] = {}

    async def execute(self, instruction: str, context, soul, messages=None, **kwargs):
        soul_id = soul.id
        attempt = self.attempts.get(soul_id, 0) + 1
        self.attempts[soul_id] = attempt
        behavior = self.behaviors.get(soul_id)
        output = behavior(attempt, instruction, soul, context) if behavior else ""
        return SimpleNamespace(output=str(output), cost_usd=0.0, total_tokens=0, exit_handle=None)


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    workflow_file = base_dir / name
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _result_snapshot(state: WorkflowState) -> list[tuple[str, str, str | None]]:
    return [
        (block_id, result.output, result.exit_handle)
        for block_id, result in state.results.items()
        if block_id != "workflow" and isinstance(result, BlockResult)
    ]


@pytest.mark.asyncio
async def test_depends_chain_executes_like_explicit_transitions(tmp_path: Path) -> None:
    sugar_path = _write_workflow_file(
        tmp_path,
        "depends_sugar.yaml",
        """\
        version: "1.0"
        id: depends-sugar
        kind: workflow
        blocks:
          step_a:
            type: code
            code: |
              def main(data):
                  return {"step": "A"}
          step_b:
            type: code
            inputs:
              step_a_result:
                from: step_a
            code: |
              def main(data):
                  _ = data["step_a_result"]
                  return {"step": "B", "seen": ["step_a"]}
            depends: step_a
          step_c:
            type: code
            inputs:
              step_b_result:
                from: step_b
            code: |
              def main(data):
                  _ = data["step_b_result"]
                  return {"step": "C", "seen": ["step_b"]}
            depends: step_b
        workflow:
          name: depends_sugar
          entry: step_a
        """,
    )
    explicit_path = _write_workflow_file(
        tmp_path,
        "depends_explicit.yaml",
        """\
        version: "1.0"
        id: depends-explicit
        kind: workflow
        blocks:
          step_a:
            type: code
            code: |
              def main(data):
                  return {"step": "A"}
          step_b:
            type: code
            inputs:
              step_a_result:
                from: step_a
            code: |
              def main(data):
                  _ = data["step_a_result"]
                  return {"step": "B", "seen": ["step_a"]}
          step_c:
            type: code
            inputs:
              step_b_result:
                from: step_b
            code: |
              def main(data):
                  _ = data["step_b_result"]
                  return {"step": "C", "seen": ["step_b"]}
        workflow:
          name: depends_explicit
          entry: step_a
          transitions:
            - from: step_a
              to: step_b
            - from: step_b
              to: step_c
        """,
    )

    sugar_state = await parse_workflow_yaml(sugar_path, runner=_ScriptedRunner()).run(
        WorkflowState()
    )
    explicit_state = await parse_workflow_yaml(explicit_path, runner=_ScriptedRunner()).run(
        WorkflowState()
    )

    assert [block_id for block_id, _output, _exit in _result_snapshot(sugar_state)] == [
        "step_a",
        "step_b",
        "step_c",
    ]
    assert json.loads(sugar_state.results["step_b"].output)["seen"] == ["step_a"]
    assert _result_snapshot(sugar_state) == _result_snapshot(explicit_state)


@pytest.mark.asyncio
async def test_gate_shorthand_routes_by_exit_handle_at_runtime(tmp_path: Path) -> None:
    workflow_path = _write_workflow_file(
        tmp_path,
        "gate_shorthand.yaml",
        """\
        version: "1.0"
        id: gate-shorthand
        kind: workflow
        souls:
          evaluator:
            id: evaluator
            kind: soul
            name: Evaluator
            role: Evaluator
            system_prompt: Evaluate carefully.
        blocks:
          analyze:
            type: code
            inputs:
              status_value:
                from: shared_memory.status
            code: |
              def main(data):
                  return {"status": data["status_value"]}
          quality_gate:
            type: gate
            soul_ref: evaluator
            eval_key: analyze
            pass: approve
            fail: reject
          approve:
            type: code
            code: |
              def main(data):
                  return {"branch": "approve"}
          reject:
            type: code
            code: |
              def main(data):
                  return {"branch": "reject"}
        workflow:
          name: gate_shorthand
          entry: analyze
          transitions:
            - from: analyze
              to: quality_gate
        """,
    )
    runner = _ScriptedRunner(
        {
            "evaluator": lambda _attempt, _instruction, _soul, context=None: (
                "PASS" if '"status": "approved"' in (context or "") else "FAIL"
            )
        }
    )

    final_state = await parse_workflow_yaml(workflow_path, runner=runner).run(
        WorkflowState(shared_memory={"status": "approved"})
    )

    assert final_state.results["quality_gate"].exit_handle == "pass"
    assert "approve" in final_state.results
    assert "reject" not in final_state.results
