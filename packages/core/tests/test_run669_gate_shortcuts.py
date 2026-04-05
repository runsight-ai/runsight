"""Failing tests for RUN-669: gate pass/fail shorthand routing."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile


def _write_soul_file(base_dir: Path, name: str = "evaluator") -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(
        dedent(
            """\
            id: evaluator
            role: Evaluator
            system_prompt: Evaluate carefully.
            """
        ),
        encoding="utf-8",
    )


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


class TestGateShortcutSchema:
    """GateBlockDef should accept and validate the new shorthand fields."""

    def test_model_validate_accepts_pass_fail_yaml_aliases(self):
        file_def = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "gate_shortcuts", "entry": "quality_gate"},
                "blocks": {
                    "quality_gate": {
                        "type": "gate",
                        "soul_ref": "evaluator",
                        "eval_key": "draft",
                        "pass": "approve",
                        "fail": "reject",
                    },
                    "approve": {"type": "code", "code": "def main(data):\n    return 'ok'"},
                    "reject": {"type": "code", "code": "def main(data):\n    return 'nope'"},
                },
            }
        )

        gate_def = file_def.blocks["quality_gate"]
        assert gate_def.pass_ == "approve"
        assert gate_def.fail_ == "reject"

    def test_model_validate_rejects_only_pass_without_fail(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(both.*pass.*fail|pass.*fail|fail.*pass)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "gate_shortcuts", "entry": "quality_gate"},
                    "blocks": {
                        "quality_gate": {
                            "type": "gate",
                            "soul_ref": "evaluator",
                            "eval_key": "draft",
                            "pass": "approve",
                        },
                        "approve": {
                            "type": "code",
                            "code": "def main(data):\n    return 'ok'",
                        },
                    },
                }
            )


class TestGateShortcutParser:
    """Parser should expand gate shorthand into conditional transitions."""

    def test_gate_pass_fail_shortcuts_expand_to_conditional_transitions(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              quality_gate:
                type: gate
                soul_ref: evaluator
                eval_key: draft
                pass: approve
                fail: reject
              approve:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"status": "rejected"}
            workflow:
              name: gate_shortcuts
              entry: quality_gate
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._conditional_transitions["quality_gate"] == {
            "pass": "approve",
            "fail": "reject",
            "default": "reject",
        }

    def test_gate_shortcuts_conflict_with_explicit_conditional_transitions(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              quality_gate:
                type: gate
                soul_ref: evaluator
                eval_key: draft
                pass: approve
                fail: reject
              approve:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"status": "rejected"}
            workflow:
              name: gate_shortcuts_conflict
              entry: quality_gate
              conditional_transitions:
                - from: quality_gate
                  pass: approve
                  fail: reject
                  default: reject
            """,
        )

        with pytest.raises(ValueError, match=r"already has a conditional transition"):
            parse_workflow_yaml(workflow_path)

    def test_gate_without_shortcuts_remains_backward_compatible(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              quality_gate:
                type: gate
                soul_ref: evaluator
                eval_key: draft
              approve:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"status": "rejected"}
            workflow:
              name: gate_explicit
              entry: quality_gate
              conditional_transitions:
                - from: quality_gate
                  pass: approve
                  fail: reject
                  default: reject
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._conditional_transitions["quality_gate"] == {
            "pass": "approve",
            "fail": "reject",
            "default": "reject",
        }
