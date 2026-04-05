"""Integration tests for YAML DX sugar parsing on the completed branch."""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    workflow_file = base_dir / name
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _write_soul_file(
    base_dir: Path,
    name: str,
    *,
    soul_id: str,
    role: str,
    prompt: str,
    model_name: str | None = None,
) -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    model_line = f"\nmodel_name: {model_name}" if model_name else ""
    (souls_dir / f"{name}.yaml").write_text(
        dedent(
            f"""\
            id: {soul_id}
            role: {role}
            system_prompt: {prompt}{model_line}
            """
        ),
        encoding="utf-8",
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


class TestYamlDxSugarPositiveFlows:
    """DX sugar should compile into existing workflow internals."""

    def test_inline_souls_standalone_parse_wires_runtime_blocks(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "inline_souls.yaml",
            """\
            version: "1.0"
            souls:
              writer:
                id: writer
                role: Inline Writer
                system_prompt: Draft carefully.
                model_name: gpt-4.1-mini
            blocks:
              draft:
                type: linear
                soul_ref: writer
            workflow:
              name: inline_souls
              entry: draft
              transitions:
                - from: draft
                  to: null
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        draft_block = _unwrap_runtime_block(workflow.blocks["draft"])
        assert draft_block.soul.id == "writer"
        assert draft_block.soul.role == "Inline Writer"
        assert draft_block.soul.system_prompt == "Draft carefully."
        assert draft_block.soul.model_name == "gpt-4.1-mini"

    def test_inline_souls_override_external_with_warning(self, tmp_path: Path, caplog):
        _write_soul_file(
            tmp_path,
            "writer",
            soul_id="writer_external",
            role="External Writer",
            prompt="Use the external prompt.",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            "inline_override.yaml",
            """\
            version: "1.0"
            souls:
              writer:
                id: writer
                role: Inline Writer
                system_prompt: Use the inline prompt.
            blocks:
              draft:
                type: linear
                soul_ref: writer
            workflow:
              name: inline_override
              entry: draft
              transitions:
                - from: draft
                  to: null
            """,
        )

        with caplog.at_level(logging.WARNING, logger="runsight_core.yaml.parser"):
            workflow = parse_workflow_yaml(workflow_path)

        draft_block = _unwrap_runtime_block(workflow.blocks["draft"])
        assert draft_block.soul.id == "writer"
        assert draft_block.soul.role == "Inline Writer"
        assert "Inline soul 'writer' overrides external soul file" in caplog.text

    def test_depends_compiles_single_and_multiple_dependency_edges(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "depends.yaml",
            """\
            version: "1.0"
            souls:
              writer:
                id: writer
                role: Inline Writer
                system_prompt: Draft carefully.
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
                depends: fetch
              summarize:
                type: linear
                soul_ref: writer
                depends:
                  - analyze
                  - branch
              branch:
                type: linear
                soul_ref: writer
            workflow:
              name: depends_edges
              entry: fetch
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        assert workflow._transitions["fetch"] == "analyze"
        assert workflow._transitions["analyze"] == "summarize"
        assert workflow._transitions["branch"] == "summarize"

    def test_gate_routes_and_error_route_compile_to_existing_workflow_internals(
        self, tmp_path: Path
    ):
        workflow_path = _write_workflow_file(
            tmp_path,
            "compiled_sugars.yaml",
            """\
            version: "1.0"
            souls:
              writer:
                id: writer
                role: Writer
                system_prompt: Draft carefully.
              evaluator:
                id: evaluator
                role: Evaluator
                system_prompt: Evaluate carefully.
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
                depends: fetch
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
                      return {"status": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"status": "rejected"}
              risky:
                type: code
                code: |
                  def main(data):
                      return {"status": "risky"}
                error_route: handler
              handler:
                type: code
                code: |
                  def main(data):
                      return {"status": "handled"}
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
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
                      return {"done": "published"}
              archive:
                type: code
                code: |
                  def main(data):
                      return {"done": "archived"}
            workflow:
              name: compiled_sugars
              entry: fetch
              transitions:
                - from: approve
                  to: review
                - from: reject
                  to: risky
                - from: risky
                  to: review
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        assert workflow._transitions == {
            "fetch": "analyze",
            "approve": "review",
            "reject": "risky",
            "risky": "review",
        }
        assert workflow._conditional_transitions["quality_gate"] == {
            "pass": "approve",
            "fail": "reject",
            "default": "reject",
        }
        assert workflow._conditional_transitions["review"] == {
            "publish": "publish",
            "archive": "archive",
            "default": "archive",
        }
        assert workflow._error_routes == {"risky": "handler"}
        assert _output_conditions_snapshot(workflow)["review"] == {
            "default": "archive",
            "cases": [
                {
                    "case_id": "publish",
                    "combinator": "and",
                    "conditions": [
                        {
                            "eval_key": "status",
                            "operator": "equals",
                            "value": "approved",
                        }
                    ],
                }
            ],
        }

    def test_sugar_yaml_compiles_to_same_internal_graph_as_explicit_legacy_forms(
        self, tmp_path: Path
    ):
        sugar_path = _write_workflow_file(
            tmp_path,
            "sugar.yaml",
            """\
            version: "1.0"
            souls:
              writer:
                id: writer
                role: Writer
                system_prompt: Draft carefully.
              evaluator:
                id: evaluator
                role: Evaluator
                system_prompt: Evaluate carefully.
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
                depends: fetch
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
                      return {"status": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"status": "rejected"}
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
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
                      return {"done": "published"}
              archive:
                type: code
                code: |
                  def main(data):
                      return {"done": "archived"}
            workflow:
              name: sugar
              entry: fetch
              transitions:
                - from: approve
                  to: review
            """,
        )
        explicit_path = _write_workflow_file(
            tmp_path,
            "explicit.yaml",
            """\
            version: "1.0"
            souls:
              writer:
                id: writer
                role: Writer
                system_prompt: Draft carefully.
              evaluator:
                id: evaluator
                role: Evaluator
                system_prompt: Evaluate carefully.
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
              quality_gate:
                type: gate
                soul_ref: evaluator
                eval_key: analyze
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
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
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
                      return {"done": "published"}
              archive:
                type: code
                code: |
                  def main(data):
                      return {"done": "archived"}
            workflow:
              name: explicit
              entry: fetch
              transitions:
                - from: fetch
                  to: analyze
                - from: approve
                  to: review
              conditional_transitions:
                - from: quality_gate
                  pass: approve
                  fail: reject
                  default: reject
                - from: review
                  publish: publish
                  archive: archive
                  default: archive
            """,
        )

        sugar_workflow = parse_workflow_yaml(sugar_path)
        explicit_workflow = parse_workflow_yaml(explicit_path)

        assert _workflow_snapshot(sugar_workflow) == _workflow_snapshot(explicit_workflow)

    def test_existing_yaml_without_new_sugar_parses_identically_to_expected_internals(
        self, tmp_path: Path
    ):
        _write_soul_file(
            tmp_path,
            "writer",
            soul_id="writer_external",
            role="External Writer",
            prompt="Use the library prompt.",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            "legacy.yaml",
            """\
            version: "1.0"
            blocks:
              draft:
                type: linear
                soul_ref: writer
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
                output_conditions:
                  - case_id: approved
                    condition_group:
                      conditions:
                        - eval_key: status
                          operator: equals
                          value: approved
                  - case_id: rejected
                    default: true
              approve:
                type: code
                code: |
                  def main(data):
                      return {"done": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"done": "rejected"}
            workflow:
              name: legacy
              entry: draft
              transitions:
                - from: draft
                  to: review
              conditional_transitions:
                - from: review
                  approved: approve
                  rejected: reject
                  default: reject
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)
        draft_block = _unwrap_runtime_block(workflow.blocks["draft"])

        assert draft_block.soul.id == "writer_external"
        assert _workflow_snapshot(workflow) == {
            "transitions": {"draft": "review"},
            "conditional_transitions": {
                "review": {
                    "approved": "approve",
                    "rejected": "reject",
                    "default": "reject",
                }
            },
            "error_routes": {},
            "output_conditions": {
                "review": {
                    "default": "rejected",
                    "cases": [
                        {
                            "case_id": "approved",
                            "combinator": "and",
                            "conditions": [
                                {
                                    "eval_key": "status",
                                    "operator": "equals",
                                    "value": "approved",
                                }
                            ],
                        }
                    ],
                }
            },
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
                    "workflow": {"name": "bad_inline_soul", "entry": "draft"},
                    "souls": {
                        "writer": {
                            "id": "reviewer",
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
            souls:
              writer:
                id: writer
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
            souls:
              evaluator:
                id: evaluator
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
