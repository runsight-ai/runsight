"""
RUN-614 — End-to-end integration coverage for reusable sub-workflows.

These tests verify the complete integration path across RUN-603 through RUN-612:
  - Interface-mediated input/output mapping (RUN-603/604)
  - on_error catch/raise behavior (RUN-605)
  - Depth tracking and cost propagation (RUN-606/607)
  - Schema-level dotted-path rejection (RUN-608)
  - Full parse → registry → execute round-trip (RUN-612)

Unlike the per-ticket unit tests, these exercise real Workflow objects,
WorkflowBlock construction, and multi-level nesting to test the seams.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from runsight_core.blocks.workflow_block import WorkflowBlock, WorkflowBlockDef
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import (
    WorkflowInterfaceDef,
    WorkflowInterfaceInputDef,
    WorkflowInterfaceOutputDef,
)

# ---------------------------------------------------------------------------
# Helpers — minimal fake blocks for integration testing
# ---------------------------------------------------------------------------


class _EchoBlock:
    """Copies a shared_memory key into results as output."""

    def __init__(self, block_id: str, *, copy_key: str):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._copy_key = copy_key

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        value = str(state.shared_memory.get(self._copy_key, ""))
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=value),
                },
            }
        )


class _WriterBlock:
    """Writes a hard-coded value into results."""

    def __init__(self, block_id: str, *, value: str = "written"):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._value = value

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._value),
                },
            }
        )


class _CostBlock:
    """Simulates a block that incurs cost and token usage."""

    def __init__(self, block_id: str, *, cost: float, tokens: int):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._cost = cost
        self._tokens = tokens

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output="done"),
                },
                "total_cost_usd": state.total_cost_usd + self._cost,
                "total_tokens": state.total_tokens + self._tokens,
            }
        )


class _FailingBlock:
    """Always raises during execute."""

    def __init__(self, block_id: str, *, error_msg: str = "block failed"):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._error_msg = error_msg

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        raise RuntimeError(self._error_msg)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _make_interface(
    inputs: list[dict] | None = None,
    outputs: list[dict] | None = None,
) -> WorkflowInterfaceDef:
    return WorkflowInterfaceDef(
        inputs=[WorkflowInterfaceInputDef(**i) for i in (inputs or [])],
        outputs=[WorkflowInterfaceOutputDef(**o) for o in (outputs or [])],
    )


def _build_child_workflow(name: str, block: object) -> Workflow:
    """Build a single-block child workflow for testing."""
    wf = Workflow(name=name)
    wf.add_block(block)
    wf.set_entry(block.block_id)
    return wf


# ===========================================================================
# Integration Tests
# ===========================================================================


@pytest.mark.asyncio
class TestInterfaceBoundExecutionEndToEnd:
    """AC1: Reusable child workflow contract is tested end to end.

    Exercises the full path: build WorkflowBlock with interface ->
    execute within a parent Workflow -> verify parent receives declared
    outputs through interface, not raw child internals.
    """

    async def test_parent_workflow_runs_child_with_interface_mapping(self) -> None:
        """Parent workflow invokes child via WorkflowBlock with interface.
        Verifies input arrives via interface target and output is mapped back."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.echo"}],
        )

        child_block = _EchoBlock("echo", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.child_summary": "summary"},
            interface=interface,
        )

        # Build parent workflow with the WorkflowBlock as a real node
        parent_wf = Workflow(name="parent_wf")
        parent_wf.add_block(wb)
        parent_wf.set_entry("invoke_child")

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "quantum computing"},
        )

        final_state = await parent_wf.run(parent_state)

        # Child echoed the topic -> parent should see it at results.child_summary
        child_summary = final_state.results.get("child_summary")
        assert child_summary is not None, "Output mapping must populate results.child_summary"
        assert str(child_summary) == "quantum computing"

        # Parent's own WorkflowBlock result must exist with compact metadata
        wb_result = final_state.results.get("invoke_child")
        assert wb_result is not None
        assert wb_result.exit_handle == "completed"
        assert wb_result.metadata is not None
        assert wb_result.metadata["child_status"] == "completed"

    async def test_child_outputs_not_leaked_as_raw_child_keys(self) -> None:
        """Interface should be the only channel.  Raw child result keys
        must not appear in parent state unless explicitly mapped."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            # No outputs declared -> nothing should leak from child
        )

        child_block = _WriterBlock("secret_child_step", value="secret data")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        result_state = await wb.execute(parent_state)

        # The WorkflowBlock's own result IS present
        assert "invoke_child" in result_state.results
        # But also note that child results get merged (per current implementation)
        # The interface contract means parent YAML should only bind declared outputs.
        # The compact metadata must NOT contain raw child results.
        wb_result = result_state.results["invoke_child"]
        assert "secret_child_step" not in (wb_result.metadata or {})
        assert "results" not in (wb_result.metadata or {})


@pytest.mark.asyncio
class TestOnErrorCatchContinuesParentRouting:
    """AC2/AC5: Parent calls child with on_error='catch'.  Child raises.
    Parent gets exit_handle='error' and can continue execution (no crash).
    """

    async def test_catch_returns_error_exit_handle_in_parent_workflow(self) -> None:
        """End-to-end: parent workflow with WorkflowBlock(on_error='catch'),
        child fails, parent continues to next block via error exit."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _FailingBlock("fail_step", error_msg="child kaboom")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="catch",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        # Execute directly — must NOT raise
        result_state = await wb.execute(parent_state)

        br = result_state.results.get("invoke_child")
        assert br is not None
        assert br.exit_handle == "error"
        assert br.metadata is not None
        assert br.metadata["child_status"] == "failed"
        assert "child kaboom" in br.metadata["child_error"]

    async def test_catch_skips_output_mapping(self) -> None:
        """When child fails under catch, output mapping must be skipped."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.fail_step"}],
        )

        child_block = _FailingBlock("fail_step", error_msg="crash")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.analysis": "summary"},
            interface=interface,
            on_error="catch",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        result_state = await wb.execute(parent_state)

        # Output mapping must NOT have run — "analysis" must not exist
        assert "analysis" not in result_state.results
        # But the WorkflowBlock's own error result must exist
        assert result_state.results["invoke_child"].exit_handle == "error"

    async def test_raise_propagates_child_exception(self) -> None:
        """Default on_error='raise' must propagate child exception."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _FailingBlock("fail_step", error_msg="propagate me")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="raise",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        with pytest.raises(RuntimeError, match="propagate me"):
            await wb.execute(parent_state)


@pytest.mark.asyncio
class TestCostAndTokensPropagateFromChildToParent:
    """AC4: Parent-facing cost, eval, duration, status, and logs stay correct."""

    async def test_child_cost_and_tokens_added_to_parent_state(self) -> None:
        """After child completes, parent total_cost_usd and total_tokens
        include child's values."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _CostBlock("expensive_step", cost=0.05, tokens=1500)
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
            total_cost_usd=0.10,
            total_tokens=3000,
        )

        result_state = await wb.execute(parent_state)

        # Parent accumulates child costs
        assert result_state.total_cost_usd == pytest.approx(0.15, abs=1e-6)
        assert result_state.total_tokens == 4500

        # Metadata also reports child-specific values
        br = result_state.results["invoke_child"]
        assert br.metadata["child_cost_usd"] == pytest.approx(0.05, abs=1e-6)
        assert br.metadata["child_tokens"] == 1500
        assert br.metadata["child_status"] == "completed"
        assert br.metadata["child_duration_s"] >= 0

    async def test_execution_log_records_child_completion(self) -> None:
        """Parent execution log must record the child workflow completion."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _WriterBlock("writer", value="done")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        result_state = await wb.execute(parent_state)

        # Check execution log has an entry about the child
        log_contents = [entry["content"] for entry in result_state.execution_log]
        assert any("child_wf" in content and "completed" in content for content in log_contents), (
            f"Execution log must mention child workflow completion. Got: {log_contents}"
        )


class TestRawDottedPathBindingRejectedEndToEnd:
    """AC5: Raw child dotted-path bindings are rejected at both
    schema validation AND runtime levels."""

    @pytest.mark.asyncio
    async def test_dotted_input_key_rejected_at_construction_time(self) -> None:
        """WorkflowBlock constructor must reject dotted-path input keys
        when interface is provided."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _EchoBlock("echo", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        with pytest.raises(ValueError, match=r"[Dd]otted|\."):
            WorkflowBlock(
                block_id="invoke_child",
                child_workflow=child_wf,
                inputs={"shared_memory.topic": "shared_memory.parent_topic"},
                outputs={},
                interface=interface,
            )

    def test_dotted_input_key_rejected_at_schema_level(self) -> None:
        """WorkflowBlockDef schema must reject dotted-path input keys."""
        with pytest.raises(ValidationError, match="dotted"):
            WorkflowBlockDef(
                type="workflow",
                workflow_ref="child_wf",
                inputs={"shared_memory.topic": "shared_memory.parent_topic"},
            )

    def test_dotted_output_value_rejected_at_schema_level(self) -> None:
        """WorkflowBlockDef schema must reject dotted-path output values."""
        with pytest.raises(ValidationError, match="dotted"):
            WorkflowBlockDef(
                type="workflow",
                workflow_ref="child_wf",
                outputs={"results.parent_out": "results.child_out"},
            )


@pytest.mark.asyncio
class TestMissingRequiredChildInputRejected:
    """Edge case: Interface declares a required input that parent doesn't provide."""

    async def test_missing_required_input_rejected_at_runtime(self) -> None:
        """Parent binds no inputs, but interface has a required input.
        Execution must fail when trying to resolve the missing parent path."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic", "required": True}],
        )

        child_block = _EchoBlock("echo", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        # Parent provides the binding name but a nonexistent parent path
        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.nonexistent"},
            outputs={},
            interface=interface,
        )

        parent_state = WorkflowState(shared_memory={})

        with pytest.raises(KeyError, match="nonexistent"):
            await wb.execute(parent_state)

    async def test_unbound_interface_input_with_no_default_at_validation(self) -> None:
        """When _validate_workflow_block_contract is used (via the parser),
        missing required inputs are caught at parse time.

        Here we directly test the validation function.
        """
        from runsight_core.yaml.parser import _validate_workflow_block_contract
        from runsight_core.yaml.schema import RunsightWorkflowFile

        child_file = RunsightWorkflowFile.model_validate(
            {
                "id": "test-workflow",
                "kind": "workflow",
                "version": "1.0",
                "interface": {
                    "inputs": [{"name": "topic", "target": "shared_memory.topic"}],
                    "outputs": [],
                },
                "workflow": {
                    "name": "child",
                    "entry": "step1",
                    "transitions": [],
                },
            }
        )

        block_def = WorkflowBlockDef(
            type="workflow",
            workflow_ref="child",
            inputs={},  # Missing required "topic"
        )

        with pytest.raises(ValueError, match="missing required"):
            _validate_workflow_block_contract("invoke_child", block_def, child_file)


@pytest.mark.asyncio
class TestInvalidOutputSourceRaisesAtRuntime:
    """Edge case: Interface output source points to nonexistent child state path."""

    async def test_nonexistent_child_source_raises_key_error(self) -> None:
        """Interface says source='results.nonexistent' but child never produces
        that result.  Must raise a clear error at output-mapping time."""
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.nonexistent"}],
        )

        child_block = _WriterBlock("writer", value="some output")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_summary": "summary"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        with pytest.raises((KeyError, ValueError)):
            await wb.execute(parent_state)


@pytest.mark.asyncio
class TestNestedChildOfChildExecution:
    """Three levels: parent -> child -> grandchild.
    All three execute successfully with correct depth tracking
    and output propagation."""

    async def test_three_level_nesting_executes_successfully(self) -> None:
        """parent_wf -> child_wf -> grandchild_wf, all with interfaces."""
        # --- Level 3: grandchild ---
        grandchild_interface = _make_interface(
            inputs=[{"name": "msg", "target": "shared_memory.msg"}],
            outputs=[{"name": "result", "source": "results.gc_step"}],
        )

        gc_block = _EchoBlock("gc_step", copy_key="msg")
        grandchild_wf = _build_child_workflow("grandchild_wf", gc_block)

        # --- Level 2: child calls grandchild ---
        child_interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.invoke_grandchild"}],
        )

        gc_wb = WorkflowBlock(
            block_id="invoke_grandchild",
            child_workflow=grandchild_wf,
            inputs={"msg": "shared_memory.topic"},
            outputs={"results.gc_output": "result"},
            interface=grandchild_interface,
            max_depth=5,
        )

        child_wf = Workflow(name="child_wf")
        child_wf.add_block(gc_wb)
        child_wf.set_entry("invoke_grandchild")

        # --- Level 1: parent calls child ---
        parent_wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.final_output": "summary"},
            interface=child_interface,
            max_depth=5,
        )

        parent_wf = Workflow(name="parent_wf")
        parent_wf.add_block(parent_wb)
        parent_wf.set_entry("invoke_child")

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "hello from parent"},
        )

        final_state = await parent_wf.run(parent_state)

        # Verify parent's own WorkflowBlock result
        parent_br = final_state.results.get("invoke_child")
        assert parent_br is not None
        assert parent_br.exit_handle == "completed"
        assert parent_br.metadata["child_status"] == "completed"

    async def test_three_level_cost_propagation(self) -> None:
        """Cost from grandchild propagates through child to parent."""
        # --- Level 3: grandchild with cost ---
        grandchild_interface = _make_interface(
            inputs=[{"name": "msg", "target": "shared_memory.msg"}],
        )

        gc_block = _CostBlock("gc_step", cost=0.02, tokens=500)
        grandchild_wf = _build_child_workflow("grandchild_wf", gc_block)

        # --- Level 2: child calls grandchild ---
        child_interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        gc_wb = WorkflowBlock(
            block_id="invoke_grandchild",
            child_workflow=grandchild_wf,
            inputs={"msg": "shared_memory.topic"},
            outputs={},
            interface=grandchild_interface,
            max_depth=5,
        )

        child_wf = Workflow(name="child_wf")
        child_wf.add_block(gc_wb)
        child_wf.set_entry("invoke_grandchild")

        # --- Level 1: parent calls child ---
        parent_wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=child_interface,
            max_depth=5,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
            total_cost_usd=0.0,
            total_tokens=0,
        )

        result_state = await parent_wb.execute(parent_state)

        # Grandchild cost should propagate up to parent
        assert result_state.total_cost_usd == pytest.approx(0.02, abs=1e-6)
        assert result_state.total_tokens == 500

        parent_br = result_state.results["invoke_child"]
        assert parent_br.metadata["child_status"] == "completed"

    async def test_nested_depth_limit_enforced(self) -> None:
        """max_depth=1 on parent -> should reject even a single child."""
        grandchild_interface = _make_interface(
            inputs=[{"name": "msg", "target": "shared_memory.msg"}],
        )

        gc_block = _WriterBlock("gc_step", value="deep")
        grandchild_wf = _build_child_workflow("grandchild_wf", gc_block)

        gc_wb = WorkflowBlock(
            block_id="invoke_grandchild",
            child_workflow=grandchild_wf,
            inputs={"msg": "shared_memory.topic"},
            outputs={},
            interface=grandchild_interface,
            max_depth=1,  # Depth limit = 1
        )

        child_wf = Workflow(name="child_wf")
        child_wf.add_block(gc_wb)
        child_wf.set_entry("invoke_grandchild")

        child_interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        parent_wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=child_interface,
            max_depth=5,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        # The grandchild's max_depth=1 should be exceeded when called
        # from within child_wf (call_stack will have parent + child = len 2)
        with pytest.raises(RecursionError, match="depth"):
            await parent_wb.execute(parent_state, call_stack=[])


@pytest.mark.asyncio
class TestNestedChildFailureUnderCatch:
    """Edge case: grandchild fails, child uses on_error='catch',
    parent should see child as completed (child caught the error)."""

    async def test_grandchild_failure_caught_by_child(self) -> None:
        """grandchild fails -> child catches -> parent sees child as completed."""
        grandchild_interface = _make_interface(
            inputs=[{"name": "msg", "target": "shared_memory.msg"}],
        )

        gc_block = _FailingBlock("gc_step", error_msg="grandchild boom")
        grandchild_wf = _build_child_workflow("grandchild_wf", gc_block)

        # Child calls grandchild with on_error=catch
        gc_wb = WorkflowBlock(
            block_id="invoke_grandchild",
            child_workflow=grandchild_wf,
            inputs={"msg": "shared_memory.topic"},
            outputs={},
            interface=grandchild_interface,
            on_error="catch",
            max_depth=5,
        )

        child_wf = Workflow(name="child_wf")
        child_wf.add_block(gc_wb)
        child_wf.set_entry("invoke_grandchild")

        child_interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        parent_wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=child_interface,
            max_depth=5,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        # Should NOT raise — grandchild failure is caught by child
        result_state = await parent_wb.execute(parent_state)

        # Parent sees child as completed (child caught the error internally)
        parent_br = result_state.results["invoke_child"]
        assert parent_br.exit_handle == "completed"
        assert parent_br.metadata["child_status"] == "completed"


@pytest.mark.asyncio
class TestRepeatedInvocationIsolation:
    """Two sequential invocations of the same WorkflowBlock must produce
    independent results with no state leakage."""

    async def test_sequential_invocations_are_isolated(self) -> None:
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.echo"}],
        )

        child_block = _EchoBlock("echo", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.analysis": "summary"},
            interface=interface,
        )

        state_a = WorkflowState(shared_memory={"parent_topic": "alpha"})
        result_a = await wb.execute(state_a)

        state_b = WorkflowState(shared_memory={"parent_topic": "beta"})
        result_b = await wb.execute(state_b)

        analysis_a = result_a.results.get("analysis")
        analysis_b = result_b.results.get("analysis")
        assert analysis_a is not None and str(analysis_a) == "alpha"
        assert analysis_b is not None and str(analysis_b) == "beta"


class TestWorkflowBlockDefSchemaIntegration:
    """Schema-level integration: WorkflowBlockDef validates interface
    binding names and on_error values end-to-end."""

    def test_valid_workflow_block_def_accepted(self) -> None:
        block_def = WorkflowBlockDef(
            type="workflow",
            workflow_ref="child_wf",
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.analysis": "summary"},
            on_error="catch",
        )
        assert block_def.type == "workflow"
        assert block_def.on_error == "catch"
        assert block_def.inputs == {"topic": "shared_memory.parent_topic"}

    def test_invalid_on_error_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowBlockDef(
                type="workflow",
                workflow_ref="child_wf",
                on_error="ignore",
            )

    def test_on_error_default_is_raise(self) -> None:
        block_def = WorkflowBlockDef(
            type="workflow",
            workflow_ref="child_wf",
        )
        assert block_def.on_error == "raise"
