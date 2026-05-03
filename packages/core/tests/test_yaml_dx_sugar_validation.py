"""Integration tests for YAML DX sugar parsing on the completed branch."""

from __future__ import annotations

from pathlib import Path

import pytest
from parser_yaml_helpers import write_custom_soul_file, write_workflow_file
from pydantic import ValidationError
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    return write_workflow_file(base_dir, yaml_content, name=name)


def _write_soul_file(
    base_dir: Path,
    name: str,
    *,
    soul_id: str,
    role: str,
    prompt: str,
    model_name: str | None = None,
) -> None:
    # Use `name` as the embedded id to match the filename stem (scanner requirement).
    # `soul_id` is kept as parameter for call-site compatibility but ignored for the file.
    del soul_id
    soul_name = " ".join(
        word.capitalize() for word in name.replace("_", " ").replace("-", " ").split()
    )
    write_custom_soul_file(
        base_dir,
        name,
        soul_id=name,
        display_name=soul_name,
        role=role,
        prompt=prompt,
        model_name=model_name,
    )


def _unwrap_runtime_block(block):
    inner = getattr(block, "inner_block", block)
    return getattr(inner, "block", inner)


def _output_conditions_snapshot(workflow) -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for block_id, (cases, default_decision) in workflow._output_conditions.items():
        snapshot[block_id] = {
            "default": default_decision,
            "cases": [
                {
                    "case_id": case.case_id,
                    "combinator": case.condition_group.combinator,
                    "conditions": [
                        {
                            "eval_key": condition.eval_key,
                            "operator": condition.operator,
                            "value": condition.value,
                        }
                        for condition in case.condition_group.conditions
                    ],
                }
                for case in cases
            ],
        }
    return snapshot


def _workflow_snapshot(workflow) -> dict[str, object]:
    return {
        "transitions": dict(workflow._transitions),
        "conditional_transitions": {
            block_id: dict(condition_map)
            for block_id, condition_map in workflow._conditional_transitions.items()
        },
        "error_routes": dict(workflow._error_routes),
        "output_conditions": _output_conditions_snapshot(workflow),
    }


class TestYamlDxSugarValidation:
    """Completed parser should reject invalid DX sugar declarations cleanly."""

    def test_inline_soul_key_id_mismatch_error(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(Inline soul key/id mismatch|writer.*reviewer)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "id": "bad-inline-soul",
                    "kind": "workflow",
                    "workflow": {"name": "bad_inline_soul", "entry": "draft"},
                    "souls": {
                        "writer": {
                            "id": "reviewer",
                            "kind": "soul",
                            "name": "Reviewer",
                            "role": "Writer",
                            "system_prompt": "Draft carefully.",
                        }
                    },
                    "blocks": {
                        "draft": {"type": "linear", "soul_ref": "writer"},
                    },
                }
            )

    def test_depends_conflict_with_explicit_transition_error(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "depends_conflict.yaml",
            """\
            version: "1.0"
            id: depends-conflict
            kind: workflow
            souls:
              writer:
                id: writer
                kind: soul
                name: Writer
                role: Writer
                system_prompt: Draft carefully.
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
                depends: fetch
              review:
                type: linear
                soul_ref: writer
            workflow:
              name: depends_conflict
              entry: fetch
              transitions:
                - from: fetch
                  to: review
            """,
        )

        with pytest.raises(ValueError, match=r"depends expansion conflict"):
            parse_workflow_yaml(workflow_path)

    def test_gate_pass_without_fail_error(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(requires both pass and fail|both pass and fail)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "id": "gate-invalid",
                    "kind": "workflow",
                    "workflow": {"name": "gate_invalid", "entry": "quality_gate"},
                    "blocks": {
                        "quality_gate": {
                            "type": "gate",
                            "soul_ref": "evaluator",
                            "eval_key": "draft",
                            "pass": "approve",
                        },
                        "approve": {"type": "code", "code": "def main(data):\n    return 'ok'"},
                    },
                }
            )

    def test_gate_shorthand_conflict_with_explicit_conditional_transitions_error(
        self, tmp_path: Path
    ):
        workflow_path = _write_workflow_file(
            tmp_path,
            "gate_conflict.yaml",
            """\
            version: "1.0"
            id: gate-conflict
            kind: workflow
            souls:
              evaluator:
                id: evaluator
                kind: soul
                name: Evaluator
                role: Evaluator
                system_prompt: Evaluate carefully.
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
              name: gate_conflict
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

    def test_error_route_unknown_target_error(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "error_route_unknown.yaml",
            """\
            version: "1.0"
            id: error-route-unknown
            kind: workflow
            blocks:
              risky:
                type: code
                code: |
                  def main(data):
                      return {"status": "risky"}
                error_route: missing_handler
            workflow:
              name: error_route_unknown
              entry: risky
            """,
        )

        with pytest.raises(ValueError, match=r"error_route.*missing_handler.*unknown block"):
            parse_workflow_yaml(workflow_path)

    @pytest.mark.parametrize(
        ("name", "raw_workflow", "pattern"),
        [
            (
                "routes_with_output_conditions",
                {
                    "workflow": {"name": "routes_conflict", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case": "approved",
                                    "when": {
                                        "conditions": [
                                            {
                                                "eval_key": "status",
                                                "operator": "equals",
                                                "value": "approved",
                                            }
                                        ]
                                    },
                                    "goto": "approve",
                                },
                                {"case": "rejected", "default": True, "goto": "reject"},
                            ],
                            "output_conditions": [
                                {
                                    "case_id": "legacy",
                                    "condition_group": {
                                        "conditions": [
                                            {
                                                "eval_key": "status",
                                                "operator": "equals",
                                                "value": "legacy",
                                            }
                                        ]
                                    },
                                },
                                {"case_id": "fallback", "default": True},
                            ],
                        },
                        "approve": {
                            "type": "code",
                            "code": "def main(data):\n    return {'result': 'approved'}",
                        },
                        "reject": {
                            "type": "code",
                            "code": "def main(data):\n    return {'result': 'rejected'}",
                        },
                    },
                },
                r"(routes and output_conditions cannot both be set|routes.*output_conditions)",
            ),
            (
                "routes_missing_default",
                {
                    "workflow": {"name": "routes_missing_default", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case": "approved",
                                    "when": {
                                        "conditions": [
                                            {
                                                "eval_key": "status",
                                                "operator": "equals",
                                                "value": "approved",
                                            }
                                        ]
                                    },
                                    "goto": "approve",
                                },
                                {
                                    "case": "rejected",
                                    "when": {
                                        "conditions": [
                                            {
                                                "eval_key": "status",
                                                "operator": "equals",
                                                "value": "rejected",
                                            }
                                        ]
                                    },
                                    "goto": "reject",
                                },
                            ],
                        },
                        "approve": {
                            "type": "code",
                            "code": "def main(data):\n    return {'result': 'approved'}",
                        },
                        "reject": {
                            "type": "code",
                            "code": "def main(data):\n    return {'result': 'rejected'}",
                        },
                    },
                },
                r"routes require exactly one default route",
            ),
            (
                "routes_duplicate_case_ids",
                {
                    "workflow": {"name": "routes_duplicate", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case": "approved",
                                    "when": {
                                        "conditions": [
                                            {
                                                "eval_key": "status",
                                                "operator": "equals",
                                                "value": "approved",
                                            }
                                        ]
                                    },
                                    "goto": "approve",
                                },
                                {"case": "approved", "default": True, "goto": "reject"},
                            ],
                        },
                        "approve": {
                            "type": "code",
                            "code": "def main(data):\n    return {'result': 'approved'}",
                        },
                        "reject": {
                            "type": "code",
                            "code": "def main(data):\n    return {'result': 'rejected'}",
                        },
                    },
                },
                r"(route case ids must be unique|duplicate case_id)",
            ),
        ],
    )
    def test_routes_validation_errors(self, name: str, raw_workflow: dict, pattern: str):
        with pytest.raises((ValidationError, ValueError), match=pattern):
            RunsightWorkflowFile.model_validate(raw_workflow)
