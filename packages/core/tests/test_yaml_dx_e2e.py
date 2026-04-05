"""End-to-end runtime tests for completed YAML DX sugar features."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.primitives import Task
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

    async def execute_task(self, task: Task, soul, messages=None):
        soul_id = soul.id
        attempt = self.attempts.get(soul_id, 0) + 1
        self.attempts[soul_id] = attempt
        self.calls.append((soul_id, task.instruction, task.context))

        behavior = self.behaviors.get(soul_id)
        if behavior is None:
            output = f"{soul_id}|{task.instruction}|{task.context or ''}"
        else:
            output = behavior(attempt, task, soul)

        if isinstance(output, BaseException):
            raise output

        return SimpleNamespace(output=str(output), cost_usd=0.0, total_tokens=0)


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
                souls:
                  writer:
                    id: writer
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

        final_state = await workflow.run(
            WorkflowState(
                current_task=Task(
                    id="draft-task",
                    instruction="Write a summary",
                    context="Purple team context",
                )
            )
        )

        assert _result_snapshot(final_state) == [
            ("draft", "writer|Write a summary|Purple team context", None)
        ]

    async def test_depends_chain_executes_in_order_and_matches_explicit_workflow(
        self, tmp_path: Path
    ):
        sugar_path = _write_workflow_file(
            tmp_path,
            "depends_sugar.yaml",
            """\
            version: "1.0"
            blocks:
              step_a:
                type: code
                code: |
                  def main(data):
                      return {"step": "A"}
              step_b:
                type: code
                code: |
                  def main(data):
                      return {"step": "B", "seen": list(data["results"].keys())}
                depends: step_a
              step_c:
                type: code
                code: |
                  def main(data):
                      return {"step": "C", "seen": list(data["results"].keys())}
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
            blocks:
              step_a:
                type: code
                code: |
                  def main(data):
                      return {"step": "A"}
              step_b:
                type: code
                code: |
                  def main(data):
                      return {"step": "B", "seen": list(data["results"].keys())}
              step_c:
                type: code
                code: |
                  def main(data):
                      return {"step": "C", "seen": list(data["results"].keys())}
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

        assert list(sugar_state.results.keys()) == ["step_a", "step_b", "step_c"]
        assert json.loads(sugar_state.results["step_b"].output)["seen"] == ["step_a"]
        assert json.loads(sugar_state.results["step_c"].output)["seen"] == ["step_a", "step_b"]
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
            souls:
              evaluator:
                id: evaluator
                role: Evaluator
                system_prompt: Evaluate carefully.
            blocks:
              analyze:
                type: code
                code: |
                  def main(data):
                      return {"status": data["shared_memory"]["status"]}
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
                "evaluator": lambda attempt, task, soul: (
                    "PASS"
                    if '"status": "approved"' in (task.context or "")
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
            souls:
              risky:
                id: risky
                role: Risky Writer
                system_prompt: This will fail.
            blocks:
              risky:
                type: linear
                soul_ref: risky
                error_route: handler
              handler:
                type: code
                code: |
                  def main(data):
                      err = data["shared_memory"]["__error__risky"]
                      return {"handled": err["message"], "type": err["type"]}
            workflow:
              name: error_route
              entry: risky
            """,
        )

        runner = _ScriptedRunner(
            {"risky": lambda attempt, task, soul: RuntimeError("primary explosion")}
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(
            WorkflowState(current_task=Task(id="risky-task", instruction="fail", context="boom"))
        )

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
            souls:
              retryer:
                id: retryer
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
                code: |
                  def main(data):
                      err = data["shared_memory"]["__error__risky"]
                      return {"handled": err["message"], "type": err["type"]}
            workflow:
              name: retry_error_route
              entry: risky
            """,
        )

        runner = _ScriptedRunner(
            {"retryer": lambda attempt, task, soul: RuntimeError("retry exhausted")}
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            final_state = await workflow.run(
                WorkflowState(
                    current_task=Task(id="retry-task", instruction="retry", context="please")
                )
            )

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
            blocks:
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": data["shared_memory"]["status"]}
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
            blocks:
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": data["shared_memory"]["status"]}
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
