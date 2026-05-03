"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

from parser_yaml_helpers import (
    RESEARCHER_SOUL_DICT,
)
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


class TestParseFromDict:
    """Tests for parsing from dict input."""

    def test_parse_from_dict_valid(self):
        """parse_workflow_yaml accepts dict input."""
        workflow_dict = {
            "version": "1.0",
            "id": "dict_input_workflow",
            "kind": "workflow",
            "souls": {"researcher": RESEARCHER_SOUL_DICT},
            "blocks": {
                "linear_block": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "id": "dict_input_workflow",
                "kind": "workflow",
                "name": "dict_input_workflow",
                "entry": "linear_block",
                "transitions": [{"from": "linear_block", "to": None}],
            },
        }
        workflow = parse_workflow_yaml(workflow_dict)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "dict_input_workflow"
