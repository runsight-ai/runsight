"""Smoke coverage for parse-time/runtime WorkflowBlock depth parity."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml as yaml_mod
from conftest import execute_block_for_test
from runsight_core import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import validate_workflow_call_contracts
from runsight_core.yaml.schema import RunsightWorkflowFile


def _make_workflow_file(yaml_text: str) -> RunsightWorkflowFile:
    data = yaml_mod.safe_load(dedent(yaml_text).strip())
    data.setdefault("id", "depth-parity-workflow")
    data.setdefault("kind", "workflow")
    return RunsightWorkflowFile.model_validate(data)


def _write_yaml_file(base: Path, rel_path: str, yaml_text: str) -> Path:
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dedent(yaml_text).strip() + "\n", encoding="utf-8")
    return target


class _RecordingWorkflow:
    def __init__(self, name: str) -> None:
        self.name = name
        self.received_kwargs: dict[str, object] | None = None

    async def run(self, state: WorkflowState, **kwargs: object) -> WorkflowState:
        self.received_kwargs = kwargs
        return WorkflowState(artifact_store=state.artifact_store)


@pytest.mark.asyncio
async def test_parse_time_and_runtime_allow_grandchild_at_max_depth_2(tmp_path: Path) -> None:
    child = _RecordingWorkflow("grandchild")
    block = WorkflowBlock(
        block_id="call_grandchild",
        child_workflow=child,
        inputs={},
        outputs={},
        max_depth=2,
    )

    await execute_block_for_test(
        block,
        WorkflowState(),
        inputs={"call_stack": ["parent"], "workflow_registry": None, "observer": None},
    )

    grandchild_file = _make_workflow_file(
        """
        version: "1.0"
        workflow:
          name: grandchild
          entry: finish
          transitions: []
        """
    )
    child_file = _make_workflow_file(
        """
        version: "1.0"
        blocks:
          call_grandchild:
            type: workflow
            workflow_ref: grandchild
        workflow:
          name: child
          entry: call_grandchild
          transitions:
            - from: call_grandchild
              to: null
        config:
          max_workflow_depth: 2
        """
    )
    parent_file = _make_workflow_file(
        """
        version: "1.0"
        blocks:
          call_child:
            type: workflow
            workflow_ref: child
            max_depth: 2
        workflow:
          name: parent
          entry: call_child
          transitions:
            - from: call_child
              to: null
        """
    )
    grandchild_path = _write_yaml_file(
        tmp_path,
        "custom/workflows/grandchild.yaml",
        """
        version: "1.0"
        id: grandchild
        kind: workflow
        workflow:
          name: grandchild
          entry: finish
          transitions: []
        """,
    ).resolve()
    child_path = _write_yaml_file(
        tmp_path,
        "custom/workflows/child.yaml",
        """
        version: "1.0"
        id: child
        kind: workflow
        blocks:
          call_grandchild:
            type: workflow
            workflow_ref: grandchild
        workflow:
          name: child
          entry: call_grandchild
          transitions:
            - from: call_grandchild
              to: null
        config:
          max_workflow_depth: 2
        """,
    ).resolve()
    validation_index = {
        "grandchild": (grandchild_path, grandchild_file),
        str(grandchild_path): (grandchild_path, grandchild_file),
        "child": (child_path, child_file),
        str(child_path): (child_path, child_file),
    }

    validate_workflow_call_contracts(
        parent_file,
        base_dir=str(tmp_path),
        validation_index=validation_index,
    )


@pytest.mark.asyncio
async def test_workflow_run_preserves_expected_call_stack_for_nested_workflows() -> None:
    workflow_c = _RecordingWorkflow(name="workflow_c")
    block_bc = WorkflowBlock(
        block_id="invoke_c",
        child_workflow=workflow_c,
        inputs={},
        outputs={},
        max_depth=3,
    )
    workflow_b = Workflow(name="workflow_b")
    workflow_b.add_block(block_bc)
    workflow_b.set_entry("invoke_c")
    workflow_b.add_transition("invoke_c", None)

    block_ab = WorkflowBlock(
        block_id="invoke_b",
        child_workflow=workflow_b,
        inputs={},
        outputs={},
        max_depth=3,
    )
    workflow_a = Workflow(name="workflow_a")
    workflow_a.add_block(block_ab)
    workflow_a.set_entry("invoke_b")
    workflow_a.add_transition("invoke_b", None)

    await workflow_a.run(WorkflowState())

    assert workflow_c.received_kwargs is not None
    assert workflow_c.received_kwargs["call_stack"] == [
        "workflow_a",
        "workflow_b",
        "workflow_c",
    ]
