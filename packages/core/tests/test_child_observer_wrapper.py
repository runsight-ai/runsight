"""Child observer terminal-event isolation and WorkflowBlock on_error parser wiring."""

from __future__ import annotations

import pytest
from conftest import execute_block_for_test
from runsight_core.block_io import BlockOutput
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingObserver:
    """Minimal observer that records which methods were called."""

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    def on_workflow_start(self, workflow_name, state):
        self.calls.append(("on_workflow_start", (workflow_name,), {}))

    def on_block_start(self, workflow_name, block_id, block_type, **kwargs):
        self.calls.append(("on_block_start", (workflow_name, block_id, block_type), kwargs))

    def on_block_complete(self, workflow_name, block_id, block_type, duration_s, state, **kwargs):
        self.calls.append(
            ("on_block_complete", (workflow_name, block_id, block_type, duration_s), kwargs)
        )

    def on_block_error(self, workflow_name, block_id, block_type, duration_s, error):
        self.calls.append(
            ("on_block_error", (workflow_name, block_id, block_type, duration_s, error), {})
        )

    def on_workflow_complete(self, workflow_name, state, duration_s):
        self.calls.append(("on_workflow_complete", (workflow_name,), {}))

    def on_workflow_error(self, workflow_name, error, duration_s):
        self.calls.append(("on_workflow_error", (workflow_name,), {}))

    def on_block_heartbeat(self, workflow_name, block_id, phase, detail, timestamp):
        self.calls.append(("on_block_heartbeat", (workflow_name, block_id, phase), {}))

    def method_names(self) -> list[str]:
        return [name for name, _, _ in self.calls]


class _EchoBlock:
    """Minimal fake block that writes a result."""

    def __init__(self, block_id: str):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False

    async def execute(self, ctx):
        return BlockOutput(output="echo")


class _FailingBlock:
    """Fake block that always raises."""

    def __init__(self, block_id: str, *, error_msg: str = "child failed"):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._error_msg = error_msg

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        raise RuntimeError(self._error_msg)


def _build_child_workflow(name: str, block: object) -> Workflow:
    """Build a single-block child workflow."""
    wf = Workflow(name=name)
    wf.add_block(block)
    wf.set_entry(block.block_id)
    return wf


# ---------------------------------------------------------------------------
# ChildObserverWrapper forwarding and interception
# ---------------------------------------------------------------------------


class TestChildObserverWrapper:
    """ChildObserverWrapper forwards block events and intercepts workflow terminal events."""

    def test_child_observer_wrapper_forwards_on_block_start(self) -> None:
        """Wrapper must forward on_block_start to the parent observer."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)

        wrapper.on_block_start("analysis_child_workflow", "analysis_block", "LinearBlock")

        assert any(name == "on_block_start" for name in parent_obs.method_names()), (
            "on_block_start must be forwarded to parent observer"
        )

    def test_child_observer_wrapper_forwards_on_block_complete(self) -> None:
        """Wrapper must forward on_block_complete to the parent observer."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)
        state = WorkflowState()

        wrapper.on_block_complete(
            "analysis_child_workflow", "analysis_block", "LinearBlock", 0.5, state
        )

        assert any(name == "on_block_complete" for name in parent_obs.method_names()), (
            "on_block_complete must be forwarded to parent observer"
        )

    def test_child_observer_wrapper_intercepts_on_workflow_complete(self) -> None:
        """Wrapper must not forward on_workflow_complete to the parent."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)
        state = WorkflowState()

        wrapper.on_workflow_complete("analysis_child_workflow", state, 1.0)

        assert "on_workflow_complete" not in parent_obs.method_names(), (
            "on_workflow_complete must be intercepted, not forwarded to parent"
        )

    def test_child_observer_wrapper_intercepts_on_workflow_error(self) -> None:
        """Wrapper must not forward on_workflow_error to the parent."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)

        wrapper.on_workflow_error("analysis_child_workflow", RuntimeError("boom"), 1.0)

        assert "on_workflow_error" not in parent_obs.method_names(), (
            "on_workflow_error must be intercepted, not forwarded to parent"
        )


# ---------------------------------------------------------------------------
# WorkflowBlock.execute uses ChildObserverWrapper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWorkflowBlockUsesChildObserver:
    """Integration tests: WorkflowBlock must wrap the observer."""

    async def test_workflow_block_execute_uses_child_observer(self) -> None:
        """After child completes, parent observer's on_workflow_complete
        must NOT have been called. The child workflow fires
        on_workflow_complete internally, but the wrapper intercepts it."""
        parent_obs = RecordingObserver()

        child_block = _EchoBlock("echo")
        analysis_child_workflow = _build_child_workflow("analysis_child_workflow", child_block)

        wb = WorkflowBlock(
            block_id="analysis_child_invocation_block",
            child_workflow=analysis_child_workflow,
            inputs={},
            outputs={},
        )

        parent_state = WorkflowState()
        await execute_block_for_test(
            wb,
            parent_state,
            inputs={"call_stack": [], "workflow_registry": None, "observer": parent_obs},
        )

        # The child workflow completes successfully — its observer fires
        # on_workflow_complete. But if a ChildObserverWrapper is used, the
        # parent observer should NOT see on_workflow_complete from the child.
        assert "on_workflow_complete" not in parent_obs.method_names(), (
            "WorkflowBlock.execute must wrap the observer so child's "
            "on_workflow_complete does not reach the parent observer"
        )

    async def test_nested_child_observers_compose(self) -> None:
        """Parent -> child -> grandchild. Each level wraps the observer.
        Grandchild completion must not trigger parent's on_workflow_complete."""
        parent_obs = RecordingObserver()

        grandchild_block = _EchoBlock("gc_echo")
        review_grandchild_workflow = _build_child_workflow(
            "review_grandchild_workflow", grandchild_block
        )

        child_wb = WorkflowBlock(
            block_id="review_grandchild_invocation_block",
            child_workflow=review_grandchild_workflow,
            inputs={},
            outputs={},
        )
        analysis_child_workflow = Workflow(name="analysis_child_workflow")
        analysis_child_workflow.add_block(child_wb)
        analysis_child_workflow.set_entry("review_grandchild_invocation_block")

        parent_wb = WorkflowBlock(
            block_id="analysis_child_invocation_block",
            child_workflow=analysis_child_workflow,
            inputs={},
            outputs={},
        )

        parent_state = WorkflowState()
        await execute_block_for_test(
            parent_wb,
            parent_state,
            inputs={"call_stack": [], "workflow_registry": None, "observer": parent_obs},
        )

        # Parent observer must NOT have received on_workflow_complete from
        # either child or grandchild.
        complete_count = parent_obs.method_names().count("on_workflow_complete")
        assert complete_count == 0, (
            f"Expected 0 on_workflow_complete calls on parent observer, got {complete_count}. "
            "Each nesting level must wrap the observer to intercept terminal events."
        )


# ---------------------------------------------------------------------------
# on_error wired through parser
# ---------------------------------------------------------------------------


class TestParserOnErrorWiring:
    """Verify parse_workflow_yaml passes on_error to WorkflowBlock."""

    def test_parse_workflow_yaml_passes_on_error_to_workflow_block(self) -> None:
        """Parse a YAML dict with on_error: catch on a workflow block.
        The resulting WorkflowBlock must have on_error == 'catch'."""
        from runsight_core.yaml.parser import parse_workflow_yaml
        from runsight_core.yaml.registry import WorkflowRegistry
        from runsight_core.yaml.schema import RunsightWorkflowFile

        child_yaml = {
            "id": "on-error-child-workflow",
            "kind": "workflow",
            "version": "1.0",
            "blocks": {
                "child_code_step": {
                    "type": "code",
                    "code": "def main(data):\n    return 'done'",
                }
            },
            "workflow": {
                "name": "on_error_child_workflow",
                "entry": "child_code_step",
                "transitions": [],
            },
        }

        registry = WorkflowRegistry()
        child_file = RunsightWorkflowFile.model_validate(child_yaml)
        registry.register("on_error_child_workflow", child_file)

        parent_yaml = {
            "id": "on-error-parent-workflow",
            "kind": "workflow",
            "version": "1.0",
            "blocks": {
                "on_error_child_invocation_block": {
                    "type": "workflow",
                    "workflow_ref": "on_error_child_workflow",
                    "on_error": "catch",
                }
            },
            "workflow": {
                "name": "on_error_parent_workflow",
                "entry": "on_error_child_invocation_block",
                "transitions": [],
            },
        }

        on_error_parent_workflow = parse_workflow_yaml(
            parent_yaml,
            workflow_registry=registry,
        )

        wb = on_error_parent_workflow.blocks["on_error_child_invocation_block"]
        assert hasattr(wb, "on_error"), "WorkflowBlock built by parser must have on_error attribute"
        assert wb.on_error == "catch", (
            f"Expected on_error='catch', got '{wb.on_error}'. "
            "Parser must wire on_error from block_def to WorkflowBlock."
        )
