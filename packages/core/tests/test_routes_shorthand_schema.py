"""Tests for inline routes shorthand on BaseBlockDef."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError
from runsight_core.yaml.schema import RunsightWorkflowFile


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    workflow_file = base_dir / name
    content = dedent(yaml_content)
    lines = content.lstrip().splitlines()
    first_key = lines[0].split(":")[0].strip() if lines else ""
    if first_key != "id":
        content = "id: routes-shorthand-workflow\nkind: workflow\n" + content
    workflow_file.write_text(content, encoding="utf-8")
    return str(workflow_file)


class TestRoutesSchema:
    """Schema should accept and validate the new routes shorthand."""

    def test_model_validate_accepts_routes_definitions(self):
        file_def = RunsightWorkflowFile.model_validate(
            {
                "id": "routes-shorthand-workflow",
                "kind": "workflow",
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
