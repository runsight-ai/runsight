"""Failing tests for RUN-671: inline routes shorthand on BaseBlockDef."""

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


class TestRoutesSchema:
    """Schema should accept and validate the new routes shorthand."""

    def test_model_validate_accepts_routes_definitions(self):
        file_def = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "routes_schema", "entry": "review"},
                "blocks": {
                    "review": {
                        "type": "code",
                        "code": "def main(data):\n    return {'status': 'approved'}",
                        "routes": [
                            {
                                "case_id": "approved",
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
                                "case_id": "rejected",
                                "default": True,
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
            }
        )

        routes = file_def.blocks["review"].routes
        assert routes is not None
        assert [route.case_id for route in routes] == ["approved", "rejected"]
        assert routes[0].goto == "approve"
        assert routes[1].default is True

    def test_model_validate_rejects_routes_with_output_conditions(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(routes.*output_conditions|output_conditions.*routes)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "routes_conflict", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case_id": "approved",
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
                                    "case_id": "rejected",
                                    "default": True,
                                    "goto": "reject",
                                },
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
                }
            )

    def test_model_validate_rejects_routes_without_exactly_one_default(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(exactly one.*default|default route)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "routes_missing_default", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case_id": "approved",
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
                                    "case_id": "rejected",
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
                }
            )

    def test_model_validate_rejects_routes_with_multiple_defaults(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(exactly one.*default|default route)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "routes_multiple_defaults", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case_id": "approved",
                                    "default": True,
                                    "goto": "approve",
                                },
                                {
                                    "case_id": "rejected",
                                    "default": True,
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
                }
            )

    def test_model_validate_rejects_duplicate_route_case_ids(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(duplicate.*case_id|case ids.*unique)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "routes_duplicate_case", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case_id": "approved",
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
                                    "case_id": "approved",
                                    "default": True,
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
                }
            )

    def test_model_validate_rejects_null_route_goto(self):
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(goto|valid string|string_type)",
        ):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "routes_null_goto", "entry": "review"},
                    "blocks": {
                        "review": {
                            "type": "code",
                            "code": "def main(data):\n    return {'status': 'approved'}",
                            "routes": [
                                {
                                    "case_id": "approved",
                                    "when": {
                                        "conditions": [
                                            {
                                                "eval_key": "status",
                                                "operator": "equals",
                                                "value": "approved",
                                            }
                                        ]
                                    },
                                    "goto": None,
                                },
                                {
                                    "case_id": "rejected",
                                    "default": True,
                                    "goto": "reject",
                                },
                            ],
                        },
                        "reject": {
                            "type": "code",
                            "code": "def main(data):\n    return {'result': 'rejected'}",
                        },
                    },
                }
            )


class TestRoutesParser:
    """Parser should expand routes shorthand into workflow routing primitives."""

    def test_routes_expand_to_output_conditions_and_conditional_transitions(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "routes_expand.yaml",
            """\
            version: "1.0"
            blocks:
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
                routes:
                  - case_id: approved
                    when:
                      conditions:
                        - eval_key: status
                          operator: equals
                          value: approved
                    goto: approve
                  - case_id: rejected
                    default: true
                    goto: reject
              approve:
                type: code
                code: |
                  def main(data):
                      return {"result": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"result": "rejected"}
            workflow:
              name: routes_expand
              entry: review
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._conditional_transitions["review"] == {
            "approved": "approve",
            "rejected": "reject",
            "default": "reject",
        }
        stored_cases, stored_default = wf._output_conditions["review"]
        assert [case.case_id for case in stored_cases] == ["approved"]
        assert stored_default == "rejected"
        assert stored_cases[0].condition_group.conditions[0].eval_key == "status"

    def test_routes_conflict_with_explicit_conditional_transitions(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "routes_conflict.yaml",
            """\
            version: "1.0"
            blocks:
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
                routes:
                  - case_id: approved
                    when:
                      conditions:
                        - eval_key: status
                          operator: equals
                          value: approved
                    goto: approve
                  - case_id: rejected
                    default: true
                    goto: reject
              approve:
                type: code
                code: |
                  def main(data):
                      return {"result": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"result": "rejected"}
            workflow:
              name: routes_conflict
              entry: review
              conditional_transitions:
                - from: review
                  approved: approve
                  rejected: reject
                  default: reject
            """,
        )

        with pytest.raises(ValueError, match=r"already has a conditional transition"):
            parse_workflow_yaml(workflow_path)

    def test_block_without_routes_remains_backward_compatible(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            "routes_omitted.yaml",
            """\
            version: "1.0"
            blocks:
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
                      return {"result": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"result": "rejected"}
            workflow:
              name: routes_legacy
              entry: review
              conditional_transitions:
                - from: review
                  approved: approve
                  rejected: reject
                  default: reject
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._conditional_transitions["review"] == {
            "approved": "approve",
            "rejected": "reject",
            "default": "reject",
        }
        stored_cases, stored_default = wf._output_conditions["review"]
        assert [case.case_id for case in stored_cases] == ["approved"]
        assert stored_default == "rejected"

    def test_empty_routes_list_is_a_noop(self, tmp_path: Path):
        empty_routes_path = _write_workflow_file(
            tmp_path,
            "routes_empty.yaml",
            """\
            version: "1.0"
            blocks:
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
                routes: []
              finish:
                type: code
                code: |
                  def main(data):
                      return {"result": "done"}
            workflow:
              name: routes_empty
              entry: review
              transitions:
                - from: review
                  to: finish
            """,
        )
        omitted_routes_path = _write_workflow_file(
            tmp_path,
            "routes_omitted_simple.yaml",
            """\
            version: "1.0"
            blocks:
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
              finish:
                type: code
                code: |
                  def main(data):
                      return {"result": "done"}
            workflow:
              name: routes_omitted_simple
              entry: review
              transitions:
                - from: review
                  to: finish
            """,
        )

        wf_with_empty_routes = parse_workflow_yaml(empty_routes_path)
        wf_without_routes = parse_workflow_yaml(omitted_routes_path)

        assert wf_with_empty_routes._transitions == wf_without_routes._transitions
        assert "review" not in wf_with_empty_routes._conditional_transitions
        assert "review" not in wf_with_empty_routes._output_conditions

    def test_default_route_with_when_logs_warning_and_ignores_when(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ):
        workflow_path = _write_workflow_file(
            tmp_path,
            "routes_default_when_warning.yaml",
            """\
            version: "1.0"
            blocks:
              review:
                type: code
                code: |
                  def main(data):
                      return {"status": "approved"}
                routes:
                  - case_id: approved
                    when:
                      conditions:
                        - eval_key: status
                          operator: equals
                          value: approved
                    goto: approve
                  - case_id: rejected
                    default: true
                    when:
                      conditions:
                        - eval_key: status
                          operator: equals
                          value: rejected
                    goto: reject
              approve:
                type: code
                code: |
                  def main(data):
                      return {"result": "approved"}
              reject:
                type: code
                code: |
                  def main(data):
                      return {"result": "rejected"}
            workflow:
              name: routes_default_when_warning
              entry: review
            """,
        )

        with caplog.at_level(logging.WARNING, logger="runsight_core.yaml.parser"):
            wf = parse_workflow_yaml(workflow_path)

        assert "default" in caplog.text
        assert "when" in caplog.text
        stored_cases, stored_default = wf._output_conditions["review"]
        assert [case.case_id for case in stored_cases] == ["approved"]
        assert stored_default == "rejected"
