"""
Tests for YAML schema models.
"""

from runsight_core.blocks.linear import LinearBlockDef
from runsight_core.yaml.schema import (
    RunsightWorkflowFile,
    SoulDef,
    TransitionDef,
    WorkflowDef,
)


class TestSchemaModels:
    """Verify that existing schema models still work after TaskDef addition."""

    def test_souldef_unchanged(self):
        """SoulDef should work as before."""
        soul = SoulDef(
            id="soul1",
            role="Researcher",
            system_prompt="You are a researcher",
        )
        assert soul.id == "soul1"
        assert soul.role == "Researcher"

    def test_blockdef_unchanged(self):
        """BlockDef discriminated union resolves to per-type model."""
        block = LinearBlockDef(soul_ref="soul1")
        assert block.type == "linear"
        assert block.soul_ref == "soul1"

    def test_transitiondef_unchanged(self):
        """TransitionDef should work as before."""
        transition = TransitionDef(**{"from": "block1", "to": "block2"})
        assert transition.from_ == "block1"
        assert transition.to == "block2"

    def test_workflowdef_unchanged(self):
        """WorkflowDef should work as before."""
        workflow = WorkflowDef(name="test", entry="block1")
        assert workflow.name == "test"
        assert workflow.entry == "block1"

    def test_runsightworkflowfile_unchanged(self):
        """RunsightWorkflowFile should work as before."""
        workflow_def = WorkflowDef(name="test", entry="block1")
        pwf = RunsightWorkflowFile(workflow=workflow_def)
        assert pwf.workflow.name == "test"
        assert pwf.version == "1.0"
