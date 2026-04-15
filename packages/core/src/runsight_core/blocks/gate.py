"""
GateBlock — quality gate that evaluates content.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Optional

from pydantic import ConfigDict, Field, model_validator

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner


class GateBlock(BaseBlock):
    """
    Quality gate that evaluates content and either passes or fails the workflow.

    On PASS: returns BlockResult(exit_handle="pass").
    On FAIL: returns BlockResult(exit_handle="fail") and feedback as output.
    """

    def __init__(
        self,
        block_id: str,
        gate_soul: Soul,
        eval_key: str,
        runner: RunsightTeamRunner,
        extract_field: Optional[str] = None,
    ):
        super().__init__(block_id)
        self.gate_soul = gate_soul
        self.soul = gate_soul
        self.eval_key = eval_key
        self.runner = runner
        self.extract_field = extract_field

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        """Execute block with BlockContext, return BlockOutput."""
        soul = ctx.soul or self.gate_soul
        content = ctx.context or ""

        result = await self.runner.execute(ctx.instruction, content, soul)
        decision_line = result.output.strip().split("\n")[0]
        is_pass = decision_line.upper().startswith("PASS")

        if is_pass:
            output_value: Any = decision_line
            if self.extract_field:
                try:
                    data = json.loads(content)
                    if isinstance(data, list) and data:
                        output_value = data[-1].get(self.extract_field, decision_line)
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    output_value = decision_line

            return BlockOutput(
                output=str(output_value),
                exit_handle="pass",
                cost_usd=result.cost_usd,
                total_tokens=result.total_tokens,
                log_entries=[{"role": "system", "content": f"[Block {self.block_id}] Gate: PASS"}],
            )
        else:
            feedback = decision_line[5:].strip() if ":" in decision_line else decision_line
            return BlockOutput(
                output=feedback,
                exit_handle="fail",
                cost_usd=result.cost_usd,
                total_tokens=result.total_tokens,
                log_entries=[
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] Gate: FAIL — {feedback}",
                    }
                ],
            )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class GateBlockDef(BaseBlockDef):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["gate"] = "gate"
    soul_ref: str
    eval_key: str
    extract_field: Optional[str] = None
    pass_: Optional[str] = Field(None, alias="pass")
    fail_: Optional[str] = Field(None, alias="fail")

    @model_validator(mode="after")
    def _validate_pass_fail_shortcuts(self) -> "GateBlockDef":
        has_pass = self.pass_ is not None
        has_fail = self.fail_ is not None
        if has_pass != has_fail:
            raise ValueError("gate shorthand requires both pass and fail, or neither")
        return self


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402

_register_block_def("gate", GateBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
    **_: Any,
) -> GateBlock:
    """Build a GateBlock from a block definition."""
    if block_def.soul_ref is None:
        raise ValueError(f"GateBlock '{block_id}': soul_ref is required")
    if block_def.eval_key is None:
        raise ValueError(f"GateBlock '{block_id}': eval_key is required")

    # Auto-inject pass/fail exits when not explicitly defined
    if block_def.exits is None:
        from runsight_core.yaml.schema import ExitDef

        block_def.exits = [
            ExitDef(id="pass", label="Pass"),
            ExitDef(id="fail", label="Fail"),
        ]

    soul = resolve_soul(block_def.soul_ref, souls_map)
    return GateBlock(
        block_id, soul, block_def.eval_key, runner, extract_field=block_def.extract_field
    )


_register_builder("gate", build)
