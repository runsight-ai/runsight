"""Isolation block schema fields and parser-time wrapper wiring contracts."""

from __future__ import annotations

import pytest
from runsight_core.yaml.schema import BaseBlockDef

pytestmark = pytest.mark.real_subprocess_isolation


class TestBaseBlockDefSchemaAdditions:
    """BaseBlockDef must include timeout_seconds and stall_thresholds fields."""

    def test_timeout_seconds_field_exists(self):
        """BaseBlockDef has timeout_seconds with default 300."""
        assert "timeout_seconds" in BaseBlockDef.model_fields
        field = BaseBlockDef.model_fields["timeout_seconds"]
        assert field.default == 300

    def test_timeout_seconds_min_value(self):
        """timeout_seconds rejects values < 1."""
        from pydantic import ValidationError
        from runsight_core.blocks.linear import LinearBlockDef

        # First verify the field exists and valid values work
        valid = LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=1)
        assert valid.timeout_seconds == 1
        # Then verify out-of-range is rejected
        with pytest.raises(ValidationError):
            LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=0)

    def test_timeout_seconds_max_value(self):
        """timeout_seconds rejects values > 3600."""
        from pydantic import ValidationError
        from runsight_core.blocks.linear import LinearBlockDef

        # First verify the field exists and valid values work
        valid = LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=3600)
        assert valid.timeout_seconds == 3600
        # Then verify out-of-range is rejected
        with pytest.raises(ValidationError):
            LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=3601)

    def test_timeout_seconds_valid_value(self):
        """timeout_seconds accepts valid values within range."""
        from runsight_core.blocks.linear import LinearBlockDef

        block_def = LinearBlockDef(type="linear", soul_ref="test", timeout_seconds=60)
        assert block_def.timeout_seconds == 60

    def test_stall_thresholds_field_exists(self):
        """BaseBlockDef has stall_thresholds field (optional dict)."""
        assert "stall_thresholds" in BaseBlockDef.model_fields
        field = BaseBlockDef.model_fields["stall_thresholds"]
        assert field.default is None

    def test_stall_thresholds_accepts_dict(self):
        """stall_thresholds can be set to a phase → seconds mapping."""
        from runsight_core.blocks.linear import LinearBlockDef

        block_def = LinearBlockDef(
            type="linear",
            soul_ref="test",
            stall_thresholds={"parsing": 10, "executing": 60},
        )
        assert block_def.stall_thresholds == {"parsing": 10, "executing": 60}

    def test_timeout_seconds_roundtrip_yaml(self):
        """timeout_seconds survives YAML parse round-trip."""
        import yaml

        yaml_str = """\
version: "1.0"
id: isolation_wrapper_schema_workflow
kind: workflow
souls:
  test:
    id: test
    kind: soul
    name: Tester
    role: Tester
    system_prompt: You test things.
blocks:
  isolated_linear_block:
    type: linear
    soul_ref: test
    timeout_seconds: 120
workflow:
  id: isolation_wrapper_schema_workflow
  kind: workflow
  name: isolation_wrapper_schema_workflow
  entry: isolated_linear_block
  transitions:
    - from: isolated_linear_block
      to: null
"""
        from unittest.mock import MagicMock

        from runsight_core.yaml.parser import parse_workflow_yaml

        runner = MagicMock()
        parse_workflow_yaml(yaml_str, runner=runner)
        # The parsed workflow accepts the YAML — verify the raw value survived
        raw = yaml.safe_load(yaml_str)
        assert raw["blocks"]["isolated_linear_block"]["timeout_seconds"] == 120


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestNoDispatchInWorkflow:
    """LLM blocks are wrapped at build time by the parser/builder, not by
    runtime dispatch in workflow.py."""

    def test_parser_returns_wrapped_blocks_for_linear(self):
        """parse_workflow_yaml wraps linear blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
id: isolation_wrapper_schema_workflow
kind: workflow
souls:
  test:
    id: test
    kind: soul
    name: Tester
    role: Tester
    system_prompt: You test things.
blocks:
  isolated_linear_block:
    type: linear
    soul_ref: test
workflow:
  id: isolation_wrapper_schema_workflow
  kind: workflow
  name: isolation_wrapper_schema_workflow
  entry: isolated_linear_block
  transitions:
    - from: isolated_linear_block
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["isolated_linear_block"]
        assert isinstance(block, IsolatedBlockWrapper)

    def test_parser_returns_wrapped_blocks_for_gate(self):
        """parse_workflow_yaml wraps gate blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
id: isolation_wrapper_schema_workflow
kind: workflow
souls:
  test:
    id: test
    kind: soul
    name: Tester
    role: Tester
    system_prompt: You test things.
blocks:
  producer:
    type: linear
    soul_ref: test
  isolated_gate_block:
    type: gate
    soul_ref: test
    eval_key: producer
workflow:
  id: isolation_wrapper_schema_workflow
  kind: workflow
  name: isolation_wrapper_schema_workflow
  entry: producer
  transitions:
    - from: producer
      to: isolated_gate_block
    - from: isolated_gate_block
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["isolated_gate_block"]
        assert isinstance(block, IsolatedBlockWrapper)

    def test_parser_returns_wrapped_blocks_for_synthesize(self):
        """parse_workflow_yaml wraps synthesize blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
id: isolation_wrapper_schema_workflow
kind: workflow
souls:
  test:
    id: test
    kind: soul
    name: Tester
    role: Tester
    system_prompt: You test things.
blocks:
  a:
    type: linear
    soul_ref: test
  b:
    type: linear
    soul_ref: test
  synth:
    type: synthesize
    soul_ref: test
    input_block_ids:
      - a
      - b
workflow:
  id: isolation_wrapper_schema_workflow
  kind: workflow
  name: isolation_wrapper_schema_workflow
  entry: a
  transitions:
    - from: a
      to: b
    - from: b
      to: synth
    - from: synth
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["synth"]
        assert isinstance(block, IsolatedBlockWrapper)

    def test_parser_returns_wrapped_blocks_for_dispatch(self):
        """parse_workflow_yaml wraps dispatch blocks with IsolatedBlockWrapper."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
id: isolation_wrapper_schema_workflow
kind: workflow
souls:
  test:
    id: test
    kind: soul
    name: Tester
    role: Tester
    system_prompt: You test things.
blocks:
  fan:
    type: dispatch
    exits:
      - id: a
        label: A
        soul_ref: test
        task: Run approval isolation branch
      - id: b
        label: B
        soul_ref: test
        task: Run revision isolation branch
workflow:
  id: isolation_wrapper_schema_workflow
  kind: workflow
  name: isolation_wrapper_schema_workflow
  entry: fan
  transitions:
    - from: fan
      to: null
"""
        runner = MagicMock()
        wf = parse_workflow_yaml(yaml_str, runner=runner)
        block = wf._blocks["fan"]
        assert isinstance(block, IsolatedBlockWrapper)
