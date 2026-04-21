"""Red tests for RUN-953: workflow-engine collaborator contracts.

These tests intentionally avoid line-count and AST-shape assertions. Instead
they require reusable seams for the workflow engine's major responsibilities
and verify that the public runtime path delegates through those seams.

To keep the contract flexible, each seam may be exposed either as:
- a module-level function, or
- a collaborator class with a method.

Any valid decomposition may satisfy either form.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import pytest
import runsight_core.workflow as workflow_module
from runsight_core.block_io import BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, Workflow, execute_block


class ResultBlock(BaseBlock):
    """Block double that writes a fixed output."""

    def __init__(self, block_id: str, output: str) -> None:
        super().__init__(block_id)
        self.output = output
        self.calls = 0

    async def execute(self, ctx) -> BlockOutput:
        self.calls += 1
        return BlockOutput(output=self.output)


class ExplodingBlock(BaseBlock):
    """Block double that fails if the old centralized path still executes it."""

    def __init__(self, block_id: str, message: str) -> None:
        super().__init__(block_id)
        self.message = message
        self.calls = 0

    async def execute(self, ctx) -> BlockOutput:
        self.calls += 1
        raise AssertionError(self.message)


def _make_ctx(*, workflow_name: str = "parent_workflow") -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name=workflow_name,
        blocks={},
        call_stack=["root_workflow"],
        workflow_registry=None,
        observer=None,
    )


def _contains_identity(args: tuple[Any, ...], kwargs: dict[str, Any], needle: Any) -> bool:
    return any(arg is needle for arg in args) or any(value is needle for value in kwargs.values())


def _find_block_id(
    args: tuple[Any, ...], kwargs: dict[str, Any], candidates: set[str]
) -> str | None:
    for value in list(args) + list(kwargs.values()):
        if isinstance(value, str) and value in candidates:
            return value
    return None


def _find_instance(
    args: tuple[Any, ...], kwargs: dict[str, Any], instance_type: type[Any]
) -> Any | None:
    for value in list(args) + list(kwargs.values()):
        if isinstance(value, instance_type):
            return value
    return None


def _require_seam(
    *,
    function_name: str,
    class_name: str,
    method_name: str,
    responsibility: str,
) -> dict[str, Any]:
    function = getattr(workflow_module, function_name, None)
    if callable(function):
        return {"kind": "function", "target": function_name}

    collaborator_cls = getattr(workflow_module, class_name, None)
    collaborator_method = getattr(collaborator_cls, method_name, None)
    if callable(collaborator_method):
        return {
            "kind": "method",
            "target": collaborator_cls,
            "method_name": method_name,
        }

    pytest.fail(
        "RUN-953 requires a reusable collaborator seam for "
        f"{responsibility}. Expected either runsight_core.workflow.{function_name}(...) "
        f"or runsight_core.workflow.{class_name}.{method_name}(...)."
    )


def _patch_seam(monkeypatch: pytest.MonkeyPatch, seam: dict[str, Any], replacement) -> None:
    if seam["kind"] == "function":
        monkeypatch.setattr(workflow_module, seam["target"], replacement)
        return

    monkeypatch.setattr(seam["target"], seam["method_name"], replacement)


def test_workflow_validate_uses_graph_validation_collaborator(monkeypatch: pytest.MonkeyPatch):
    seam = _require_seam(
        function_name="validate_workflow_graph",
        class_name="WorkflowGraphValidator",
        method_name="validate",
        responsibility="graph validation and transition integrity",
    )
    seen: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_validate(*args, **kwargs):
        seen.append((args, kwargs))
        return ["delegated validation result"]

    _patch_seam(monkeypatch, seam, fake_validate)

    workflow = Workflow("validation_facade")
    errors = workflow.validate()

    assert errors == ["delegated validation result"]
    assert seen, "Workflow.validate() must call the graph-validation collaborator"
    assert _contains_identity(seen[0][0], seen[0][1], workflow)


@pytest.mark.asyncio
async def test_workflow_run_uses_next_step_resolver_collaborator(
    monkeypatch: pytest.MonkeyPatch,
):
    seam = _require_seam(
        function_name="resolve_next_block",
        class_name="NextStepResolver",
        method_name="resolve",
        responsibility="next-step resolution and output-condition routing",
    )
    seen: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_resolve(*args, **kwargs):
        seen.append((args, kwargs))
        block_id = _find_block_id(args, kwargs, {"entry", "chosen", "fallback"})
        if block_id == "entry":
            return "chosen"
        return None

    _patch_seam(monkeypatch, seam, fake_resolve)

    entry = ResultBlock("entry", "entry output")
    chosen = ResultBlock("chosen", "chosen output")
    fallback = ResultBlock("fallback", "fallback output")

    workflow = Workflow("routing_facade")
    workflow.add_block(entry)
    workflow.add_block(chosen)
    workflow.add_block(fallback)
    workflow.set_entry("entry")
    workflow.add_transition("entry", "fallback")
    workflow.add_transition("chosen", None)
    workflow.add_transition("fallback", None)

    final_state = await workflow.run(WorkflowState())

    assert seen, "Workflow.run() must delegate routing decisions to the resolver seam"
    assert entry.calls == 1
    assert chosen.calls == 1
    assert fallback.calls == 0
    assert final_state.results["chosen"].output == "chosen output"


@pytest.mark.asyncio
async def test_execute_block_uses_block_dispatch_collaborator(monkeypatch: pytest.MonkeyPatch):
    seam = _require_seam(
        function_name="dispatch_block",
        class_name="BlockDispatcher",
        method_name="execute",
        responsibility="block dispatch and block-type-specific execution behavior",
    )
    block = ExplodingBlock(
        "dispatch_target",
        "execute_block() should delegate through the block-dispatch collaborator",
    )
    state = WorkflowState()
    ctx = _make_ctx()

    async def fake_dispatch(*args, **kwargs):
        assert _contains_identity(args, kwargs, block)
        assert _contains_identity(args, kwargs, state)
        assert _contains_identity(args, kwargs, ctx)
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    block.block_id: BlockResult(output="delegated dispatch result"),
                }
            }
        )

    _patch_seam(monkeypatch, seam, fake_dispatch)

    result = await execute_block(block, state, ctx)

    assert result.results[block.block_id].output == "delegated dispatch result"
    assert block.calls == 0


@pytest.mark.asyncio
async def test_workflow_run_uses_runtime_loop_collaborator(monkeypatch: pytest.MonkeyPatch):
    seam = _require_seam(
        function_name="run_workflow_loop",
        class_name="WorkflowRuntime",
        method_name="run_loop",
        responsibility="error-route handling, dynamic step injection, and workflow runtime control",
    )
    entry = ExplodingBlock(
        "entry",
        "Workflow.run() should delegate queue/error/injection flow to a runtime collaborator",
    )

    workflow = Workflow("runtime_facade_workflow")
    workflow.add_block(entry)
    workflow.set_entry("entry")
    workflow.add_transition("entry", None)

    async def fake_run_loop(*args, **kwargs):
        queue = _find_instance(args, kwargs, deque)
        ctx = _find_instance(args, kwargs, BlockExecutionContext)
        state = _find_instance(args, kwargs, WorkflowState)

        assert queue is not None, "runtime collaborator should receive the pending queue"
        assert list(queue)[0][0] == "entry"
        assert ctx is not None, "runtime collaborator should receive BlockExecutionContext"
        assert ctx.workflow_name == "runtime_facade_workflow"
        assert state is not None, "runtime collaborator should receive the evolving WorkflowState"

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    "runtime_seam": BlockResult(output="delegated runtime result"),
                }
            }
        )

    _patch_seam(monkeypatch, seam, fake_run_loop)

    final_state = await workflow.run(WorkflowState())

    assert final_state.results["runtime_seam"].output == "delegated runtime result"
    assert entry.calls == 0
