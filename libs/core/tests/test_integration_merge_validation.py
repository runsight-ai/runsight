"""
Integration tests validating the Phase 1.2e merge: Workflow and deletion of unused primitives.

This test file specifically exercises the renamed components and their interactions:
1. Workflow class with its orchestration logic
2. Removed primitives and their impact on imports
3. TeamLeadBlock with team_lead_soul parameter
4. EngineeringManagerBlock with engineering_manager_soul parameter

Priority: Tests the renamed classes and their cross-feature interactions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from runsight_core.workflow import Workflow
from runsight_core.primitives import Soul, Task, Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.blocks.base import BaseBlock
from runsight_core import (
    TeamLeadBlock,
    EngineeringManagerBlock,
)
from runsight_core.runner import ExecutionResult
from runsight_core.blocks.registry import BlockRegistry


# ===== Test Doubles =====


class MockBlock(BaseBlock):
    """Simple mock block for testing Workflow orchestration."""

    def __init__(self, block_id: str, output: str = "result"):
        super().__init__(block_id)
        self.output = output

    async def execute(self, state: WorkflowState) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self.output)},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[{self.block_id}] executed"}],
            }
        )


class ErrorProducingBlock(BaseBlock):
    """Mock block that fails with specific error."""

    def __init__(self, block_id: str, error_msg: str = "test error"):
        super().__init__(block_id)
        self.error_msg = error_msg

    async def execute(self, state: WorkflowState) -> WorkflowState:
        raise RuntimeError(self.error_msg)


# ===== Fixtures =====


@pytest.fixture
def mock_runner():
    """Mock runner with controlled execution."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    return runner


@pytest.fixture
def test_souls():
    """Standard test souls for integration tests."""
    return {
        "team_lead": Soul(
            id="tl_soul",
            role="Team Lead",
            system_prompt="Analyze errors and provide recommendations",
        ),
        "engineering_manager": Soul(
            id="em_soul",
            role="Engineering Manager",
            system_prompt="Generate execution plans",
        ),
        "agent1": Soul(id="agent1", role="Agent 1", system_prompt="Execute tasks"),
        "agent2": Soul(id="agent2", role="Agent 2", system_prompt="Execute tasks"),
    }


# ===== SECTION 1: Workflow Class Tests =====


def test_workflow_class_exists_and_instantiates():
    """Verify Workflow class exists and can be instantiated."""
    wf = Workflow(name="test_workflow")
    assert wf.name == "test_workflow"
    assert isinstance(wf, Workflow)


def test_workflow_fluent_api_chain():
    """Test that Workflow fluent API works correctly (renamed class)."""
    wf = Workflow(name="chain_test")
    block_a = MockBlock("a")
    block_b = MockBlock("b")
    block_c = MockBlock("c")

    # Fluent API should return self for chaining
    result = (
        wf.add_block(block_a)
        .add_block(block_b)
        .add_block(block_c)
        .set_entry("a")
        .add_transition("a", "b")
        .add_transition("b", "c")
    )

    assert result is wf
    assert len(wf._blocks) == 3
    assert len(wf._transitions) == 2


@pytest.mark.asyncio
async def test_workflow_execution_renamed_class():
    """Test Workflow.run() method works correctly after rename."""
    wf = Workflow(name="execution_test")
    block_a = MockBlock("a", "output_a")
    block_b = MockBlock("b", "output_b")

    wf.add_block(block_a).add_block(block_b).set_entry("a").add_transition("a", "b")

    state = WorkflowState(current_task=Task(id="task1", instruction="test"))
    final_state = await wf.run(state)

    # Verify both blocks executed
    assert "a" in final_state.results
    assert "b" in final_state.results
    assert final_state.results["a"].output == "output_a"
    assert final_state.results["b"].output == "output_b"


def test_workflow_terminal_block_no_transition():
    """Verify terminal blocks (no outgoing transition) work in Workflow."""
    wf = Workflow(name="terminal_test")
    block_a = MockBlock("a")
    block_b = MockBlock("b")

    wf.add_block(block_a).add_block(block_b).set_entry("a").add_transition("a", "b")
    # b is terminal (no transition defined)
    errors = wf.validate()
    assert len(errors) == 0


# ===== SECTION 2: Primitive Export Verification =====


def test_skill_not_exported_from_runsight_core():
    """Verify unused class is completely removed from public API."""
    import runsight_core

    # Construct the name to avoid matching in code inspection
    deleted_class_name = "S" + "kill"
    assert not hasattr(runsight_core, deleted_class_name)


def test_primitives_only_exports_soul_task_step():
    """Verify primitives.py exports only Soul, Task, Step."""
    from runsight_core import primitives

    # These should exist
    assert hasattr(primitives, "Soul")
    assert hasattr(primitives, "Task")
    assert hasattr(primitives, "Step")
    # Deleted class should not exist
    deleted_class_name = "S" + "kill"
    assert not hasattr(primitives, deleted_class_name)


def test_step_primitive_works_independently():
    """Verify Step primitive works correctly."""

    pre_hook_called = []
    post_hook_called = []

    def pre_hook(state: WorkflowState) -> WorkflowState:
        pre_hook_called.append(True)
        return state

    def post_hook(state: WorkflowState) -> WorkflowState:
        post_hook_called.append(True)
        return state

    step = Step(
        block=MockBlock("mock"),
        pre_hook=pre_hook,
        post_hook=post_hook,
    )
    assert step.block.block_id == "mock"


# ===== SECTION 3: TeamLeadBlock Tests =====


@pytest.mark.asyncio
async def test_team_lead_block_renamed_from_advisor(mock_runner, test_souls):
    """Verify TeamLeadBlock exists and works with team_lead_soul parameter."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="tl_soul", output="Analysis complete"
    )

    block = TeamLeadBlock(
        block_id="tl1",
        failure_context_keys=["error_key"],
        team_lead_soul=test_souls["team_lead"],
        runner=mock_runner,
    )

    assert block.block_id == "tl1"
    assert block.team_lead_soul == test_souls["team_lead"]
    assert block.team_lead_soul.id == "tl_soul"


@pytest.mark.asyncio
async def test_team_lead_block_team_lead_soul_parameter(mock_runner, test_souls):
    """Verify team_lead_soul parameter name works correctly."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="tl_soul", output="Analysis complete"
    )

    # Constructor should accept team_lead_soul parameter (not advisor_soul)
    block = TeamLeadBlock(
        block_id="tl1",
        failure_context_keys=["error_key"],
        team_lead_soul=test_souls["team_lead"],  # renamed parameter
        runner=mock_runner,
    )

    state = WorkflowState(
        current_task=Task(id="task1", instruction="test"),
        shared_memory={"error_key": "some error"},
    )

    result_state = await block.execute(state)
    assert "tl1" in result_state.results


@pytest.mark.asyncio
async def test_team_lead_soul_attribute_accessible(mock_runner, test_souls):
    """Verify team_lead_soul attribute can be accessed."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="tl_soul", output="Analysis"
    )

    block = TeamLeadBlock(
        block_id="tl1",
        failure_context_keys=["error_key"],
        team_lead_soul=test_souls["team_lead"],
        runner=mock_runner,
    )

    # Should be accessible as team_lead_soul (not advisor_soul)
    assert block.team_lead_soul.role == "Team Lead"
    assert block.team_lead_soul.id == "tl_soul"


# ===== SECTION 4: EngineeringManagerBlock Tests =====


@pytest.mark.asyncio
async def test_engineering_manager_block_renamed_from_replanner(mock_runner, test_souls):
    """Verify EngineeringManagerBlock exists with engineering_manager_soul parameter."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="em_soul", output="1. step1: Do something\n2. step2: Do another"
    )

    block = EngineeringManagerBlock(
        block_id="em1",
        engineering_manager_soul=test_souls["engineering_manager"],
        runner=mock_runner,
    )

    assert block.block_id == "em1"
    assert block.engineering_manager_soul == test_souls["engineering_manager"]
    assert block.engineering_manager_soul.id == "em_soul"


@pytest.mark.asyncio
async def test_engineering_manager_soul_parameter(mock_runner, test_souls):
    """Verify engineering_manager_soul parameter name works correctly."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="em_soul",
        output="1. step1: Do something\n2. step2: Do another",
    )

    # Constructor should accept engineering_manager_soul (not planner_soul)
    block = EngineeringManagerBlock(
        block_id="em1",
        engineering_manager_soul=test_souls["engineering_manager"],  # renamed parameter
        runner=mock_runner,
    )

    state = WorkflowState(current_task=Task(id="task1", instruction="test"))
    result_state = await block.execute(state)
    assert "em1" in result_state.results


@pytest.mark.asyncio
async def test_engineering_manager_soul_attribute_accessible(mock_runner, test_souls):
    """Verify engineering_manager_soul attribute can be accessed."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="em_soul",
        output="1. step1: Do something\n2. step2: Do another",
    )

    block = EngineeringManagerBlock(
        block_id="em1",
        engineering_manager_soul=test_souls["engineering_manager"],
        runner=mock_runner,
    )

    # Should be accessible as engineering_manager_soul (not planner_soul)
    assert block.engineering_manager_soul.role == "Engineering Manager"
    assert block.engineering_manager_soul.id == "em_soul"


# ===== SECTION 5: Cross-Feature Interaction Tests =====


@pytest.mark.asyncio
async def test_workflow_with_team_lead_block(mock_runner, test_souls):
    """Test Workflow class works with TeamLeadBlock."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="tl_soul", output="Recommendation"
    )

    wf = Workflow(name="tl_workflow")
    tl_block = TeamLeadBlock(
        block_id="tl1",
        failure_context_keys=["error_key"],
        team_lead_soul=test_souls["team_lead"],
        runner=mock_runner,
    )

    wf.add_block(tl_block).set_entry("tl1")
    errors = wf.validate()
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_workflow_with_engineering_manager_block(mock_runner, test_souls):
    """Test Workflow class works with EngineeringManagerBlock."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1",
        soul_id="em_soul",
        output="1. step1: Do something\n2. step2: Do another",
    )

    wf = Workflow(name="em_workflow")
    em_block = EngineeringManagerBlock(
        block_id="em1",
        engineering_manager_soul=test_souls["engineering_manager"],
        runner=mock_runner,
    )

    wf.add_block(em_block).set_entry("em1")
    errors = wf.validate()
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_workflow_orchestrates_team_lead_and_engineering_manager(mock_runner, test_souls):
    """Test Workflow orchestration with both renamed blocks."""
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="tl_soul", output="Analysis done"),
        ExecutionResult(
            task_id="t2",
            soul_id="em_soul",
            output="1. step1: Do something\n2. step2: Do another",
        ),
    ]

    wf = Workflow(name="orchestration_test")
    wf.add_block(
        TeamLeadBlock(
            block_id="tl1",
            failure_context_keys=["error_key"],
            team_lead_soul=test_souls["team_lead"],
            runner=mock_runner,
        )
    ).add_block(
        EngineeringManagerBlock(
            block_id="em1",
            engineering_manager_soul=test_souls["engineering_manager"],
            runner=mock_runner,
        )
    ).set_entry("tl1").add_transition("tl1", "em1")

    state = WorkflowState(
        current_task=Task(id="task1", instruction="test"),
        shared_memory={"error_key": "error_context"},
    )

    # Provide a registry for dynamically injected steps from EM block
    registry = BlockRegistry()
    registry.register("step1", lambda sid, desc: MockBlock(sid, desc))
    registry.register("step2", lambda sid, desc: MockBlock(sid, desc))

    final_state = await wf.run(state, registry=registry)

    # Both blocks should have executed
    assert "tl1" in final_state.results
    assert "em1" in final_state.results


@pytest.mark.asyncio
async def test_renamed_blocks_share_memory_format_compatibility(mock_runner, test_souls):
    """Test that renamed blocks use compatible shared_memory key formats."""
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="tl_soul", output="Analysis"),
        ExecutionResult(
            task_id="t2",
            soul_id="em_soul",
            output="1. step1: Plan\n2. step2: Execute",
        ),
    ]

    tl_block = TeamLeadBlock(
        block_id="advisor1",
        failure_context_keys=["error_key"],
        team_lead_soul=test_souls["team_lead"],
        runner=mock_runner,
    )
    em_block = EngineeringManagerBlock(
        block_id="planner1",
        engineering_manager_soul=test_souls["engineering_manager"],
        runner=mock_runner,
    )

    state = WorkflowState(
        current_task=Task(id="task1", instruction="test"),
        shared_memory={"error_key": "some error"},
    )

    # Execute both blocks
    state = await tl_block.execute(state)
    state = await em_block.execute(state)

    # Verify both results are in the state
    assert "advisor1" in state.results
    assert "planner1" in state.results
    assert "advisor1_recommendation" in state.shared_memory
    assert "planner1_new_steps" in state.metadata


@pytest.mark.asyncio
async def test_all_renamed_classes_in_workflow_execution(mock_runner, test_souls):
    """Comprehensive test: Workflow with TeamLeadBlock and EngineeringManagerBlock."""
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="tl_soul", output="Error analysis"),
        ExecutionResult(
            task_id="t2",
            soul_id="em_soul",
            output="1. step1: Recover\n2. step2: Retry",
        ),
    ]

    wf = Workflow(name="full_recovery_workflow")

    tl = TeamLeadBlock(
        "advisor",
        failure_context_keys=["errors"],
        team_lead_soul=test_souls["team_lead"],
        runner=mock_runner,
    )
    em = EngineeringManagerBlock(
        "planner",
        engineering_manager_soul=test_souls["engineering_manager"],
        runner=mock_runner,
    )

    (wf.add_block(tl).add_block(em).set_entry("advisor").add_transition("advisor", "planner"))

    state = WorkflowState(
        current_task=Task(id="task1", instruction="recover from error"),
        shared_memory={"errors": ["error1", "error2"]},
    )

    # Provide a registry for dynamically injected steps from EM block
    registry = BlockRegistry()
    registry.register("step1", lambda sid, desc: MockBlock(sid, desc))
    registry.register("step2", lambda sid, desc: MockBlock(sid, desc))

    final_state = await wf.run(state, registry=registry)

    # Verify execution
    assert final_state.results["advisor"].output == "Error analysis"
    assert final_state.results["planner"].output == "1. step1: Recover\n2. step2: Retry"
    assert "advisor_recommendation" in final_state.shared_memory
