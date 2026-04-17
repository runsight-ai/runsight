"""End-to-end runtime tests for completed YAML DX sugar features."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml


class _ScriptedRunner:
    """Deterministic runner for exercising parsed LLM-backed blocks end-to-end."""

    def __init__(self, behaviors=None):
        self.behaviors = behaviors or {}
        # GateBlock goes through fit_to_budget(), so use a real mapped model name.
        self.model_name = "gpt-4o-mini"
        self.calls: list[tuple[str, str, str | None]] = []
        self.attempts: dict[str, int] = {}

    async def execute(self, instruction: str, context, soul, messages=None, **kwargs):
        soul_id = soul.id
        attempt = self.attempts.get(soul_id, 0) + 1
        self.attempts[soul_id] = attempt
        self.calls.append((soul_id, instruction, context))

        behavior = self.behaviors.get(soul_id)
        if behavior is None:
            output = f"{soul_id}|{instruction}|{context or ''}"
        else:
            output = behavior(attempt, instruction, soul, context)

        if isinstance(output, BaseException):
            raise output

        return SimpleNamespace(output=str(output), cost_usd=0.0, total_tokens=0, exit_handle=None)


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    workflow_file = base_dir / name
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _result_snapshot(state: WorkflowState) -> list[tuple[str, str, str | None]]:
    snapshot: list[tuple[str, str, str | None]] = []
    for block_id, result in state.results.items():
        if isinstance(result, BlockResult):
            snapshot.append((block_id, result.output, result.exit_handle))
        else:
            snapshot.append((block_id, str(result), None))
    return snapshot


@pytest.mark.asyncio
class TestYamlDxSugarE2E:
    """Completed YAML DX sugar should behave transparently at runtime."""

    async def test_inline_soul_workflow_executes_to_completion_and_produces_output(self):
        workflow = parse_workflow_yaml(
            dedent(
                """\
                version: "1.0"
                id: inline-soul-e2e
                kind: workflow
                souls:
                  writer:
                    id: writer
                    kind: soul
                    name: Inline Writer
                    role: Inline Writer
                    system_prompt: Draft carefully.
                blocks:
                  draft:
                    type: linear
                    soul_ref: writer
                workflow:
                  name: inline_soul_e2e
                  entry: draft
                  transitions:
                    - from: draft
                      to: null
                """
            ),
            runner=_ScriptedRunner(),
        )

        final_state = await workflow.run(WorkflowState())

        # "workflow" is a sentinel key seeded by Workflow.run(); exclude it from snapshot.
        # exit_handle may be "done" when the block terminates normally.
        block_snapshot = [t for t in _result_snapshot(final_state) if t[0] != "workflow"]
        assert len(block_snapshot) == 1
        assert block_snapshot[0][0] == "draft"
        assert block_snapshot[0][1] == "writer||"

    async def test_depends_chain_executes_in_order_and_matches_explicit_workflow(
        self, tmp_path: Path
    ):
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
                  step_a_result:
                    from: step_a
                  step_b_result:
                    from: step_b
                code: |
                  def main(data):
                      _ = data["step_a_result"]
                      _ = data["step_b_result"]
                      return {"step": "C", "seen": ["step_a", "step_b"]}
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
                  step_a_result:
                    from: step_a
                  step_b_result:
                    from: step_b
                code: |
                  def main(data):
                      _ = data["step_a_result"]
                      _ = data["step_b_result"]
                      return {"step": "C", "seen": ["step_a", "step_b"]}
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

        sugar_workflow = parse_workflow_yaml(sugar_path, runner=_ScriptedRunner())
        explicit_workflow = parse_workflow_yaml(explicit_path, runner=_ScriptedRunner())

        sugar_state = await sugar_workflow.run(WorkflowState())
        explicit_state = await explicit_workflow.run(WorkflowState())

        # "workflow" is a sentinel key seeded by Workflow.run(); exclude it from comparisons
        sugar_block_keys = [k for k in sugar_state.results.keys() if k != "workflow"]
        assert sugar_block_keys == ["step_a", "step_b", "step_c"]
        step_b_seen = [
            k for k in json.loads(sugar_state.results["step_b"].output)["seen"] if k != "workflow"
        ]
        assert step_b_seen == ["step_a"]
        step_c_seen = [
            k for k in json.loads(sugar_state.results["step_c"].output)["seen"] if k != "workflow"
        ]
        assert step_c_seen == ["step_a", "step_b"]
        assert _result_snapshot(sugar_state) == _result_snapshot(explicit_state)

    @pytest.mark.parametrize(
        ("status", "expected_exit", "expected_terminal"),
        [
            ("approved", "pass", "approve"),
            ("rejected", "fail", "reject"),
        ],
    )
    async def test_gate_shorthand_routes_to_correct_successor_based_on_exit_handle(
        self,
        tmp_path: Path,
        status: str,
        expected_exit: str,
        expected_terminal: str,
    ):
        workflow_path = _write_workflow_file(
            tmp_path,
            f"gate_{status}.yaml",
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
                "evaluator": lambda attempt, instruction, soul, context=None: (
                    "PASS"
                    if '"status": "approved"' in (context or "")
                    else "FAIL: content rejected"
                )
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState(shared_memory={"status": status}))

        assert final_state.results["quality_gate"].exit_handle == expected_exit
        assert expected_terminal in final_state.results
        unexpected_terminal = "reject" if expected_terminal == "approve" else "approve"
        assert unexpected_terminal not in final_state.results

    async def test_error_route_contains_failure_and_workflow_completes(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "error_route.yaml",
            """\
            version: "1.0"
            id: error-route
            kind: workflow
            souls:
              risky:
                id: risky
                kind: soul
                name: Risky Writer
                role: Risky Writer
                system_prompt: This will fail.
            blocks:
              risky:
                type: linear
                soul_ref: risky
                error_route: handler
              handler:
                type: code
                inputs:
                  routed_error:
                    from: shared_memory.__error__risky
                code: |
                  def main(data):
                      err = data["routed_error"]
                      return {"handled": err["message"], "type": err["type"]}
            workflow:
              name: error_route
              entry: risky
            """,
        )

        runner = _ScriptedRunner(
            {
                "risky": lambda attempt, instruction, soul, context=None: RuntimeError(
                    "primary explosion"
                )
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        assert final_state.results["risky"].exit_handle == "error"
        assert final_state.results["risky"].metadata == {
            "error_type": "RuntimeError",
            "error_message": "primary explosion",
            "block_id": "risky",
        }
        assert final_state.shared_memory["__error__risky"] == {
            "type": "RuntimeError",
            "message": "primary explosion",
        }
        assert json.loads(final_state.results["handler"].output) == {
            "handled": "primary explosion",
            "type": "RuntimeError",
        }

    async def test_retry_exhaustion_routes_to_handler_after_all_attempts(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "retry_error_route.yaml",
            """\
            version: "1.0"
            id: retry-error-route
            kind: workflow
            souls:
              retryer:
                id: retryer
                kind: soul
                name: Retryer
                role: Retryer
                system_prompt: This will exhaust retries.
            blocks:
              risky:
                type: linear
                soul_ref: retryer
                error_route: handler
                retry_config:
                  max_attempts: 3
                  backoff: fixed
                  backoff_base_seconds: 0.1
              handler:
                type: code
                inputs:
                  routed_error:
                    from: shared_memory.__error__risky
                code: |
                  def main(data):
                      err = data["routed_error"]
                      return {"handled": err["message"], "type": err["type"]}
            workflow:
              name: retry_error_route
              entry: risky
            """,
        )

        runner = _ScriptedRunner(
            {
                "retryer": lambda attempt, instruction, soul, context=None: RuntimeError(
                    "retry exhausted"
                )
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            final_state = await workflow.run(WorkflowState())

        assert runner.attempts["retryer"] == 3
        assert final_state.results["risky"].exit_handle == "error"
        assert final_state.results["risky"].metadata["error_message"] == "retry exhausted"
        assert final_state.shared_memory["__error__risky"]["message"] == "retry exhausted"
        assert json.loads(final_state.results["handler"].output) == {
            "handled": "retry exhausted",
            "type": "RuntimeError",
        }

    @pytest.mark.parametrize(
        ("status", "expected_terminal"), [("approved", "publish"), ("draft", "archive")]
    )
    async def test_routes_shorthand_branches_correctly_and_matches_explicit_condition_workflow(
        self, tmp_path: Path, status: str, expected_terminal: str
    ):
        sugar_path = _write_workflow_file(
            tmp_path,
            f"routes_sugar_{status}.yaml",
            """\
            version: "1.0"
            id: routes-sugar
            kind: workflow
            blocks:
              review:
                type: code
                inputs:
                  status_value:
                    from: shared_memory.status
                code: |
                  def main(data):
                      return {"status": data["status_value"]}
                routes:
                  - case: publish
                    when:
                      conditions:
                        - eval_key: status
                          operator: equals
                          value: approved
                    goto: publish
                  - case: archive
                    default: true
                    goto: archive
              publish:
                type: code
                code: |
                  def main(data):
                      return {"done": "publish"}
              archive:
                type: code
                code: |
                  def main(data):
                      return {"done": "archive"}
            workflow:
              name: routes_sugar
              entry: review
            """,
        )
        explicit_path = _write_workflow_file(
            tmp_path,
            f"routes_explicit_{status}.yaml",
            """\
            version: "1.0"
            id: routes-explicit
            kind: workflow
            blocks:
              review:
                type: code
                inputs:
                  status_value:
                    from: shared_memory.status
                code: |
                  def main(data):
                      return {"status": data["status_value"]}
                output_conditions:
                  - case_id: publish
                    condition_group:
                      conditions:
                        - eval_key: status
                          operator: equals
                          value: approved
                  - case_id: archive
                    default: true
              publish:
                type: code
                code: |
                  def main(data):
                      return {"done": "publish"}
              archive:
                type: code
                code: |
                  def main(data):
                      return {"done": "archive"}
            workflow:
              name: routes_explicit
              entry: review
              conditional_transitions:
                - from: review
                  publish: publish
                  archive: archive
                  default: archive
            """,
        )

        sugar_workflow = parse_workflow_yaml(sugar_path, runner=_ScriptedRunner())
        explicit_workflow = parse_workflow_yaml(explicit_path, runner=_ScriptedRunner())

        sugar_state = await sugar_workflow.run(WorkflowState(shared_memory={"status": status}))
        explicit_state = await explicit_workflow.run(
            WorkflowState(shared_memory={"status": status})
        )

        assert expected_terminal in sugar_state.results
        assert _result_snapshot(sugar_state) == _result_snapshot(explicit_state)
