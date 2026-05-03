"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

import pytest
from parser_yaml_helpers import (
    RESEARCHER_SOUL_DICT,
    researcher_soul_yaml,
)
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


class TestVersionValidation:
    """Tests for YAML schema version validation."""

    # -- Minimal valid workflow YAML used as a base for version tests --------
    _BASE_YAML_TEMPLATE = f"""
version: "{{version}}"
id: version_test
kind: workflow
{researcher_soul_yaml()}
blocks:
  version_entry_block:
    type: linear
    soul_ref: researcher
workflow:
  id: version_test
  kind: workflow
  name: version_test
  entry: version_entry_block
  transitions:
    - from: version_entry_block
      to: null
"""

    _BASE_DICT_NO_VERSION = {
        "id": "version_test",
        "kind": "workflow",
        "souls": {"researcher": RESEARCHER_SOUL_DICT},
        "blocks": {"version_entry_block": {"type": "linear", "soul_ref": "researcher"}},
        "workflow": {
            "id": "version_test",
            "kind": "workflow",
            "name": "version_test",
            "entry": "version_entry_block",
            "transitions": [{"from": "version_entry_block", "to": None}],
        },
    }

    def test_version_1_0_accepted_without_warning(self):
        """Version '1.0' is the current version and parses without error."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="1.0")
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "version_test"

    def test_unknown_version_raises_value_error(self):
        """Unknown version raises ValueError."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="2.0")
        with pytest.raises(ValueError, match="version"):
            parse_workflow_yaml(yaml_content)

    def test_unknown_version_999_raises_value_error(self):
        """Another unknown version also raises ValueError."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="999.0")
        with pytest.raises(ValueError, match="version"):
            parse_workflow_yaml(yaml_content)

    def test_missing_version_defaults_to_1_0(self):
        """Missing version field works and defaults to '1.0'."""
        workflow = parse_workflow_yaml(dict(self._BASE_DICT_NO_VERSION))
        assert isinstance(workflow, Workflow)
        assert workflow.name == "version_test"

    def test_unknown_version_error_message_includes_supported_versions(self):
        """Error message for unknown version includes supported versions."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="3.0")
        with pytest.raises(ValueError, match="1.0"):
            parse_workflow_yaml(yaml_content)

    def test_unknown_version_error_message_includes_provided_version(self):
        """Error message for unknown version includes the provided version."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="42.0")
        with pytest.raises(ValueError, match="42.0"):
            parse_workflow_yaml(yaml_content)
