"""
RUN-663 — Parser round-trip integration test for on_error=catch.

Build a YAML with parent calling child where child raises, parse through
``parse_workflow_yaml`` with a real registry, execute with ``Workflow.run()``.
Assert parent gets ``exit_handle="error"`` and does not crash.

This test MUST fail because:
  - The parser does not currently wire ``on_error`` from WorkflowBlockDef to
    the WorkflowBlock constructor
  - Even if it did, the child exception would propagate (on_error defaults
    to "raise") and the parent workflow would crash
"""

from __future__ import annotations

import pytest
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


@pytest.mark.asyncio
class TestParserRoundTripOnErrorCatch:
    """End-to-end: parse parent+child YAML, run, assert on_error=catch works."""

    async def test_parser_round_trip_on_error_catch_works_end_to_end(self) -> None:
        """(l) Build a YAML with parent calling child with on_error: catch.
        Child raises. Parse through parse_workflow_yaml with real registry.
        Execute with Workflow.run(). Assert parent gets exit_handle='error'
        and doesn't crash.

        The child uses a code block that deliberately raises so we get a
        predictable failure without needing an LLM or soul definitions.
        """

        # Child workflow: a code block that always raises
        child_yaml = {
            "version": "1.0",
            "interface": {
                "inputs": [],
                "outputs": [],
            },
            "blocks": {
                "step1": {
                    "type": "code",
                    "code": "def main(data):\n    raise RuntimeError('child code block failed')",
                }
            },
            "workflow": {
                "name": "child_wf",
                "entry": "step1",
                "transitions": [],
            },
        }

        # Register child workflow
        registry = WorkflowRegistry(allow_filesystem_fallback=False)
        child_file = RunsightWorkflowFile.model_validate(child_yaml)
        registry.register("child_wf", child_file)

        # Parent workflow: calls child with on_error: catch
        parent_yaml = {
            "version": "1.0",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_wf",
                    "on_error": "catch",
                },
            },
            "workflow": {
                "name": "parent_wf",
                "entry": "invoke_child",
                "transitions": [],
            },
        }

        parent_wf = parse_workflow_yaml(
            parent_yaml,
            workflow_registry=registry,
        )

        # Execute — should NOT raise because on_error=catch
        initial_state = WorkflowState()
        final_state = await parent_wf.run(
            initial_state,
            workflow_registry=registry,
        )

        # Verify the WorkflowBlock produced an error BlockResult
        br = final_state.results.get("invoke_child")
        assert br is not None, "WorkflowBlock must produce a BlockResult even when on_error=catch"
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "error", (
            f"exit_handle must be 'error' for caught child failure, got '{br.exit_handle}'"
        )
        assert br.metadata is not None
        assert br.metadata.get("child_status") == "failed", (
            f"child_status must be 'failed', got '{br.metadata.get('child_status')}'"
        )
