from __future__ import annotations

from types import SimpleNamespace

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

FIXTURE_MODEL = "fixture-dispatch-loop-model"


def patch_fixture_model_budget(monkeypatch):
    from runsight_core.memory import budget as budget_module

    original_get_model_info = budget_module.get_model_info

    def _get_model_info(model: str):
        if model == FIXTURE_MODEL:
            return {"max_input_tokens": 8192}
        return original_get_model_info(model)

    monkeypatch.setattr(budget_module, "get_model_info", _get_model_info)


class ScriptedRunner:
    """Deterministic runner for exercising parsed LLM-backed block behavior."""

    def __init__(self, behaviors=None):
        self.behaviors = behaviors or {}
        self.model_name = FIXTURE_MODEL
        self.calls: list[tuple[str, str, str | None]] = []
        self.attempts: dict[str, int] = {}

    async def execute(self, instruction: str, context, soul, messages=None, **kwargs):
        soul_id = soul.id
        attempt = self.attempts.get(soul_id, 0) + 1
        self.attempts[soul_id] = attempt
        self.calls.append((soul_id, instruction, context))

        behavior = self.behaviors.get(soul_id)
        if behavior is None:
            output = f"{soul_id}|{instruction}|{context or ''}"
        else:
            output = behavior(attempt, instruction, soul)

        if isinstance(output, BaseException):
            raise output

        return SimpleNamespace(output=str(output), cost_usd=0.0, total_tokens=0, exit_handle=None)


class RecordingObserver:
    """Observer that records block completion snapshots for loop assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, ...]] = []
        self.block_complete_states: list[tuple[str, str, WorkflowState]] = []

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.events.append(("workflow_start", workflow_name))

    def on_block_start(self, workflow_name: str, block_id: str, block_type: str, **kwargs) -> None:
        self.events.append(("block_start", workflow_name, block_id, block_type))

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        **kwargs,
    ) -> None:
        self.events.append(("block_complete", workflow_name, block_id, block_type))
        self.block_complete_states.append((workflow_name, block_id, state))

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self.events.append(("block_error", workflow_name, block_id, block_type, str(error)))

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self.events.append(("workflow_complete", workflow_name))

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.events.append(("workflow_error", workflow_name, str(error)))


def make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name="Tester",
        role="Tester",
        system_prompt="You are a test agent.",
        model_name=FIXTURE_MODEL,
    )


def make_state(**overrides) -> WorkflowState:
    defaults: dict = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


def make_workflow_with_loop(
    name: str,
    loop: LoopBlock,
    *inner_blocks: BaseBlock,
) -> Workflow:
    wf = Workflow(name)
    wf.add_block(loop)
    for block in inner_blocks:
        wf.add_block(block)
    wf.set_entry(loop.block_id)
    wf.add_transition(loop.block_id, None)
    return wf
