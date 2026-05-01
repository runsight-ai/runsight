from __future__ import annotations

from runsight_core.block_io import BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow


class ResultBlock(BaseBlock):
    """Simple block that stores a fixed output string in results."""

    def __init__(self, block_id: str, output: str) -> None:
        super().__init__(block_id)
        self.output = output

    async def execute(self, ctx):
        return BlockOutput(output=self.output)


class FailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str, message: str = "intentional failure") -> None:
        super().__init__(block_id)
        self.message = message

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        raise RuntimeError(self.message)


class RecordingObserver:
    """Observer that records workflow and block lifecycle events."""

    def __init__(self) -> None:
        self.events: list[tuple[str, ...]] = []

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


def make_single_block_workflow(name: str, block: BaseBlock) -> Workflow:
    wf = Workflow(name)
    wf.add_block(block)
    wf.set_entry(block.block_id)
    wf.add_transition(block.block_id, None)
    return wf


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
