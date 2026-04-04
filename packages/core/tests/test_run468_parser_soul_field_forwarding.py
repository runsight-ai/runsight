"""Red tests for RUN-468: parse_workflow_yaml forwards all SoulDef fields to Soul.

NOTE: These tests depend on inline soul definitions which were removed in RUN-570.
They will be re-enabled once RUN-571 wires library soul discovery.
"""

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml

pytestmark = pytest.mark.xfail(
    reason="RUN-570 removed inline souls; RUN-571 will wire library discovery",
    strict=True,
)

WORKFLOW_WITH_EXTENDED_SOUL = """
version: "1.0"
workflow:
  name: parser-forwarding
  entry: step1
  transitions:
    - from: step1
      to: null
blocks:
  step1:
    type: linear
    soul_ref: researcher
souls:
  researcher:
    id: researcher_1
    role: Researcher
    system_prompt: Investigate thoroughly.
    provider: openai
    temperature: 0.5
    max_tokens: 4096
    avatar_color: "#3399ff"
config:
  model_name: gpt-4o
"""

WORKFLOW_WITH_MINIMAL_SOUL = """
version: "1.0"
workflow:
  name: parser-forwarding-minimal
  entry: step1
  transitions:
    - from: step1
      to: null
blocks:
  step1:
    type: linear
    soul_ref: reviewer
souls:
  reviewer:
    id: reviewer_1
    role: Reviewer
    system_prompt: Review carefully.
config:
  model_name: gpt-4o
"""


class TestParserSoulFieldForwarding:
    def test_parse_workflow_yaml_forwards_extended_soul_fields(self):
        workflow = parse_workflow_yaml(WORKFLOW_WITH_EXTENDED_SOUL)
        soul = workflow.blocks["step1"].soul

        assert soul.provider == "openai"
        assert soul.temperature == 0.5
        assert soul.max_tokens == 4096
        assert soul.avatar_color == "#3399ff"

    def test_parse_workflow_yaml_keeps_new_fields_optional(self):
        workflow = parse_workflow_yaml(WORKFLOW_WITH_MINIMAL_SOUL)
        soul = workflow.blocks["step1"].soul

        assert soul.provider is None
        assert soul.temperature is None
        assert soul.max_tokens is None
        assert soul.avatar_color is None
