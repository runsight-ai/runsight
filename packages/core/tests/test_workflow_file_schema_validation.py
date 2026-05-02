"""
JSON schema publishing and validation behavior.

Tests exercise the Pydantic schema models from runsight_core.yaml.schema,
covering:
- Type discrimination (correct type -> correct model, wrong fields rejected)
- output_conditions validation (operators, case_id, empty lists)
- inputs validation (from path structure)
- extra="forbid" enforcement on every block type
- JSON schema generation script in --check mode
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.blocks.code import CodeBlockDef
from runsight_core.blocks.linear import LinearBlockDef
from runsight_core.yaml.schema import (
    BlockDef,
    RunsightWorkflowFile,
)

# Shared TypeAdapter for the discriminated union
block_adapter = TypeAdapter(BlockDef)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ===========================================================================
# 1. Type discrimination tests
# ===========================================================================


class TestRunsightWorkflowFile:
    """Root model validation coverage."""

    def test_minimal_valid_file(self):
        wf = RunsightWorkflowFile.model_validate(
            {
                "id": "schema_validation_workflow",
                "kind": "workflow",
                "workflow": {"name": "schema_validation_workflow", "entry": "b1"},
                "blocks": {"b1": {"type": "linear", "soul_ref": "s1"}},
            }
        )
        assert wf.workflow.name == "schema_validation_workflow"
        assert "b1" in wf.blocks
        assert isinstance(wf.blocks["b1"], LinearBlockDef)

    def test_missing_workflow_key(self):
        """workflow is required at root level."""
        with pytest.raises(ValidationError, match="workflow"):
            RunsightWorkflowFile.model_validate({"blocks": {}})

    def test_block_discrimination_in_file(self):
        """Blocks inside the file should be discriminated correctly."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "id": "schema_validation_workflow",
                "kind": "workflow",
                "workflow": {"name": "schema_validation_workflow", "entry": "b1"},
                "blocks": {
                    "b1": {"type": "linear", "soul_ref": "s1"},
                    "b2": {"type": "code", "code": "x = 1"},
                },
            }
        )
        assert isinstance(wf.blocks["b1"], LinearBlockDef)
        assert isinstance(wf.blocks["b2"], CodeBlockDef)

    def test_tools_whitelist_accepts_canonical_tool_ids(self):
        """Root files accept workflow tool IDs, not typed tool definitions."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "id": "schema_validation_workflow",
                "kind": "workflow",
                "workflow": {"name": "schema_validation_workflow", "entry": "b1"},
                "blocks": {"b1": {"type": "linear", "soul_ref": "s1"}},
                "tools": ["http", "delegate", "lookup_profile"],
            }
        )

        assert wf.tools == ["http", "delegate", "lookup_profile"]

    def test_root_file_rejects_legacy_tool_map_authoring(self):
        """Legacy workflow tool maps fail instead of being normalized."""
        with pytest.raises(ValidationError, match="list"):
            RunsightWorkflowFile.model_validate(
                {
                    "id": "schema_validation_workflow",
                    "kind": "workflow",
                    "workflow": {"name": "schema_validation_workflow", "entry": "b1"},
                    "blocks": {"b1": {"type": "linear", "soul_ref": "s1"}},
                    "tools": {
                        "http": {"type": "builtin", "source": "runsight/http"},
                    },
                }
            )

    def test_root_file_rejects_inline_http_tool_authoring(self):
        """Inline HTTP definitions are not valid workflow authoring."""
        with pytest.raises(ValidationError, match="list"):
            RunsightWorkflowFile.model_validate(
                {
                    "id": "schema_validation_workflow",
                    "kind": "workflow",
                    "workflow": {"name": "schema_validation_workflow", "entry": "b1"},
                    "blocks": {"b1": {"type": "linear", "soul_ref": "s1"}},
                    "tools": {
                        "http": {
                            "type": "http",
                            "method": "GET",
                            "url": "https://fixture.test",
                        }
                    },
                }
            )


# ===========================================================================
# 6. Schema generation script tests
# ===========================================================================
