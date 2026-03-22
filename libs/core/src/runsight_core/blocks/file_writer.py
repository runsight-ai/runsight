"""
FileWriterBlock — write content from workflow state to a file.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Literal

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState


class FileWriterBlock(BaseBlock):
    """
    Write content from workflow state to a file on disk.

    Reads state.results[content_key] and writes it to output_path.
    Creates parent directories if they don't exist.
    No LLM calls — pure I/O operation.
    """

    def __init__(self, block_id: str, output_path: str, content_key: str):
        super().__init__(block_id)
        self.output_path = output_path
        self.content_key = content_key

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        if self.content_key not in state.results:
            raise ValueError(
                f"FileWriterBlock '{self.block_id}': content_key '{self.content_key}' "
                f"not found in state.results. Available keys: {sorted(state.results.keys())}"
            )

        _raw = state.results[self.content_key]
        content = _raw.output if hasattr(_raw, "output") else str(_raw)
        output = Path(self.output_path)
        await asyncio.to_thread(output.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(output.write_text, content, encoding="utf-8")

        char_count = len(content)
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f"Written {char_count} chars to {self.output_path}"
                    ),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] FileWriter: wrote {char_count} chars to {self.output_path}",
                    }
                ],
            }
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class FileWriterBlockDef(BaseBlockDef):
    type: Literal["file_writer"] = "file_writer"
    output_path: str
    content_key: str


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("file_writer", FileWriterBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> FileWriterBlock:
    """Build a FileWriterBlock from a block definition."""
    if block_def.output_path is None:
        raise ValueError(f"FileWriterBlock '{block_id}': output_path is required")
    if block_def.content_key is None:
        raise ValueError(f"FileWriterBlock '{block_id}': content_key is required")
    return FileWriterBlock(block_id, block_def.output_path, block_def.content_key)


_register_builder("file_writer", build)
