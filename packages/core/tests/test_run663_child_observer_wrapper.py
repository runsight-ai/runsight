"""
RUN-663 — Failing tests for ChildObserverWrapper (SSE gap) and on_error parser wiring.

The parent's observer is currently passed raw to the child workflow. When
the child completes, ``on_workflow_complete`` fires on the parent's
``StreamingObserver``, emitting SSE_RUN_COMPLETED and closing the stream
prematurely.

Fix requires a ``ChildObserverWrapper`` that forwards non-terminal events
(on_block_start, on_block_complete, etc.) but intercepts
``on_workflow_complete`` and ``on_workflow_error`` so they never reach the
parent observer.

These tests MUST fail against the current implementation because:
  - ``ChildObserverWrapper`` does not exist yet (ImportError)
  - ``WorkflowBlock.execute()`` passes the raw observer to the child
  - The parser does not wire ``on_error`` from block_def to WorkflowBlock
"""

from __future__ import annotations

import pytest
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
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

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output="echo"),
                },
            }
        )


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
# 1a-d: ChildObserverWrapper unit tests
# ---------------------------------------------------------------------------


class TestChildObserverWrapper:
    """Tests for the ChildObserverWrapper that does not exist yet."""

    def test_child_observer_wrapper_forwards_on_block_start(self) -> None:
        """(a) Wrapper must forward on_block_start to the parent observer."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)

        wrapper.on_block_start("child_wf", "block1", "LLMBlock")

        assert any(name == "on_block_start" for name in parent_obs.method_names()), (
            "on_block_start must be forwarded to parent observer"
        )

    def test_child_observer_wrapper_forwards_on_block_complete(self) -> None:
        """(b) Wrapper must forward on_block_complete to the parent observer."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)
        state = WorkflowState()

        wrapper.on_block_complete("child_wf", "block1", "LLMBlock", 0.5, state)

        assert any(name == "on_block_complete" for name in parent_obs.method_names()), (
            "on_block_complete must be forwarded to parent observer"
        )

    def test_child_observer_wrapper_intercepts_on_workflow_complete(self) -> None:
        """(c) Wrapper must NOT forward on_workflow_complete to the parent."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)
        state = WorkflowState()

        wrapper.on_workflow_complete("child_wf", state, 1.0)

        assert "on_workflow_complete" not in parent_obs.method_names(), (
            "on_workflow_complete must be intercepted, not forwarded to parent"
        )

    def test_child_observer_wrapper_intercepts_on_workflow_error(self) -> None:
        """(d) Wrapper must NOT forward on_workflow_error to the parent."""
        from runsight_core.observer import ChildObserverWrapper

        parent_obs = RecordingObserver()
        wrapper = ChildObserverWrapper(parent_obs)

        wrapper.on_workflow_error("child_wf", RuntimeError("boom"), 1.0)

        assert "on_workflow_error" not in parent_obs.method_names(), (
            "on_workflow_error must be intercepted, not forwarded to parent"
        )


# ---------------------------------------------------------------------------
# 1e: WorkflowBlock.execute uses ChildObserverWrapper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWorkflowBlockUsesChildObserver:
    """Integration tests: WorkflowBlock must wrap the observer."""

    async def test_workflow_block_execute_uses_child_observer(self) -> None:
        """(e) After child completes, parent observer's on_workflow_complete
        must NOT have been called. The child workflow fires
        on_workflow_complete internally, but the wrapper intercepts it."""
        parent_obs = RecordingObserver()

        child_block = _EchoBlock("echo")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        parent_state = WorkflowState()
        await wb.execute(parent_state, observer=parent_obs)

        # The child workflow completes successfully — its observer fires
        # on_workflow_complete. But if a ChildObserverWrapper is used, the
        # parent observer should NOT see on_workflow_complete from the child.
        assert "on_workflow_complete" not in parent_obs.method_names(), (
            "WorkflowBlock.execute must wrap the observer so child's "
            "on_workflow_complete does not reach the parent observer"
        )

    async def test_nested_child_observers_compose(self) -> None:
        """(f) Parent -> child -> grandchild. Each level wraps the observer.
        Grandchild completion must not trigger parent's on_workflow_complete."""
        parent_obs = RecordingObserver()

        # grandchild workflow
        grandchild_block = _EchoBlock("gc_echo")
        grandchild_wf = _build_child_workflow("grandchild_wf", grandchild_block)

        # child workflow contains a WorkflowBlock that calls grandchild
        child_wb = WorkflowBlock(
            block_id="call_grandchild",
            child_workflow=grandchild_wf,
            inputs={},
            outputs={},
        )
        child_wf = Workflow(name="child_wf")
        child_wf.add_block(child_wb)
        child_wf.set_entry("call_grandchild")

        # parent workflow block calls child
        parent_wb = WorkflowBlock(
            block_id="call_child",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        parent_state = WorkflowState()
        await parent_wb.execute(parent_state, observer=parent_obs)

        # Parent observer must NOT have received on_workflow_complete from
        # either child or grandchild.
        complete_count = parent_obs.method_names().count("on_workflow_complete")
        assert complete_count == 0, (
            f"Expected 0 on_workflow_complete calls on parent observer, got {complete_count}. "
            "Each nesting level must wrap the observer to intercept terminal events."
        )


# ---------------------------------------------------------------------------
# 2g: on_error wired through parser
# ---------------------------------------------------------------------------


class TestParserOnErrorWiring:
    """Verify parse_workflow_yaml passes on_error to WorkflowBlock."""

    def test_parse_workflow_yaml_passes_on_error_to_workflow_block(self) -> None:
        """(g) Parse a YAML dict with on_error: catch on a workflow block.
        The resulting WorkflowBlock must have on_error == 'catch'."""
        from runsight_core.yaml.parser import parse_workflow_yaml
        from runsight_core.yaml.registry import WorkflowRegistry
        from runsight_core.yaml.schema import RunsightWorkflowFile

        # Build a minimal child workflow definition using a code block
        # (no soul_ref needed, avoids inline-soul validation)
        child_yaml = {
            "version": "1.0",
            "interface": {
                "inputs": [],
                "outputs": [],
            },
            "blocks": {
                "step1": {
                    "type": "code",
                    "code": "def main(data):\n    return 'done'",
                }
            },
            "workflow": {
                "name": "child_wf",
                "entry": "step1",
                "transitions": [],
            },
        }

        # Register child in a registry
        registry = WorkflowRegistry(allow_filesystem_fallback=False)
        child_file = RunsightWorkflowFile.model_validate(child_yaml)
        registry.register("child_wf", child_file)

        # Parent workflow that calls child with on_error: catch
        parent_yaml = {
            "version": "1.0",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_wf",
                    "on_error": "catch",
                }
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

        # The built WorkflowBlock must have on_error="catch"
        wb = parent_wf.blocks["invoke_child"]
        assert hasattr(wb, "on_error"), "WorkflowBlock built by parser must have on_error attribute"
        assert wb.on_error == "catch", (
            f"Expected on_error='catch', got '{wb.on_error}'. "
            "Parser must wire on_error from block_def to WorkflowBlock."
        )
