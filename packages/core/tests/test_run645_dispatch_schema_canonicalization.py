"""
RED tests for RUN-645: canonicalize workflow schema and generated artifacts to dispatch.

These tests assert schema-source and generated-artifact contracts:
- checked-in schema artifact must match generated schema source of truth
- branching block in schema artifacts must be `dispatch` only (no `fanout` alias path)
- workflow-semantic router wording must not appear in schema descriptions/examples
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = REPO_ROOT / "packages" / "core"
SCHEMA_PATH = CORE_ROOT / "runsight-workflow-schema.json"


def _load_checked_in_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _generate_schema_from_source_of_truth() -> dict:
    import runsight_core.blocks  # noqa: F401  # trigger block auto-discovery
    from runsight_core.yaml.schema import RunsightWorkflowFile

    return RunsightWorkflowFile.model_json_schema()


class TestSchemaArtifactSync:
    """Checked-in schema artifact should be regenerated from current schema source."""

    def test_checked_in_schema_matches_generated_schema(self):
        checked_in = _load_checked_in_schema()
        generated = _generate_schema_from_source_of_truth()
        assert checked_in == generated


class TestDispatchCanonicalBranchingSchema:
    """Schema artifact should model the branching block as dispatch only."""

    def test_branching_discriminator_mapping_is_dispatch_only(self):
        checked_in = _load_checked_in_schema()
        mapping = checked_in["properties"]["blocks"]["additionalProperties"]["discriminator"][
            "mapping"
        ]

        assert "dispatch" in mapping
        assert mapping["dispatch"] == "#/$defs/DispatchBlockDef"
        assert "fanout" not in mapping

    def test_dispatch_block_definition_exists_without_fanout_definition(self):
        checked_in = _load_checked_in_schema()
        defs = checked_in["$defs"]

        assert "DispatchBlockDef" in defs
        assert "FanOutBlockDef" not in defs

        dispatch_type_props = defs["DispatchBlockDef"]["properties"]["type"]
        assert dispatch_type_props["const"] == "dispatch"
        assert dispatch_type_props["default"] == "dispatch"


class TestDispatchExitDefinitionRename:
    """Dispatch exits should use DispatchExitDef with no FanOutExitDef alias."""

    def test_dispatch_exit_def_is_publicly_exported(self):
        from runsight_core.yaml import schema as schema_module

        assert hasattr(schema_module, "DispatchExitDef")
        assert not hasattr(schema_module, "FanOutExitDef")

    def test_dispatch_block_exits_reference_dispatch_exit_def(self):
        checked_in = _load_checked_in_schema()
        exits_items = checked_in["$defs"]["DispatchBlockDef"]["properties"]["exits"]["items"]

        assert exits_items["$ref"] == "#/$defs/DispatchExitDef"
        assert "FanOutExitDef" not in checked_in["$defs"]

    def test_checked_in_schema_definitions_include_dispatch_exit_def(self):
        checked_in = _load_checked_in_schema()
        defs = checked_in["$defs"]

        assert "DispatchExitDef" in defs
        assert "FanOutExitDef" not in defs


class TestSchemaTextSemantics:
    """Schema descriptions/examples must avoid workflow-block router semantics."""

    def test_conditional_transition_description_has_no_router_block_example(self):
        checked_in = _load_checked_in_schema()
        description = checked_in["$defs"]["ConditionalTransitionDef"]["description"]

        assert "router_block" not in description
        assert "type: router" not in description
