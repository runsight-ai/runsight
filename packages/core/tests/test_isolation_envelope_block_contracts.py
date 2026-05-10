"""Isolation envelope block contract behavior."""

from __future__ import annotations

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.isolation.workspace import WorkspaceRunRequest
from runsight_core.state import BlockResult, WorkflowState

pytestmark = pytest.mark.real_subprocess_isolation


class TestEnvelopeBlockContracts:
    """Wrapper emits full envelope config for supported block types."""

    async def _execute_and_capture_envelope(
        self,
        wrapper,
        *,
        state: WorkflowState | None = None,
    ) -> ContextEnvelope:
        captured: dict[str, ContextEnvelope] = {}

        async def _capture(request: WorkspaceRunRequest) -> ResultEnvelope:
            envelope = request.envelope
            captured["envelope"] = envelope
            return ResultEnvelope(
                block_id=wrapper.block_id,
                output="ok",
                exit_handle="done",
                cost_usd=0.0,
                total_tokens=0,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            )

        wrapper._run_in_subprocess = _capture
        await wrapper.execute(_make_ctx(wrapper, state or _make_state()))
        return captured["envelope"]

    @pytest.mark.asyncio
    async def test_gate_block_envelope_uses_lowercase_block_type_and_gate_config(self):
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        inner = GateBlock(
            "isolated_gate_block",
            _make_soul("gate_evaluator_soul"),
            "producer",
            MagicMock(),
            extract_field="answer",
        )
        wrapper = IsolatedBlockWrapper(block_id="isolated_gate_block", inner_block=inner)

        state = WorkflowState(results={"producer": BlockResult(output='{"answer": "ok"}')})
        envelope = await self._execute_and_capture_envelope(wrapper, state=state)

        assert envelope.block_type == "gate"
        assert envelope.block_config["eval_key"] == "producer"
        assert envelope.block_config["extract_field"] == "answer"
        assert "pass_condition" not in envelope.block_config

    @pytest.mark.asyncio
    async def test_synthesize_block_envelope_uses_lowercase_block_type_and_full_config(self):
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        synthesis_soul = _make_soul("synthesis_soul")
        inner = SynthesizeBlock(
            "isolated_synthesis_block", ["draft", "facts"], synthesis_soul, MagicMock()
        )
        wrapper = IsolatedBlockWrapper(block_id="isolated_synthesis_block", inner_block=inner)

        state = WorkflowState(
            results={
                "draft": BlockResult(output="draft text"),
                "facts": BlockResult(output="fact text"),
            }
        )
        envelope = await self._execute_and_capture_envelope(wrapper, state=state)

        assert envelope.block_type == "synthesize"
        assert envelope.block_config["input_block_ids"] == ["draft", "facts"]
        assert envelope.block_config["synthesizer_soul"] == {
            "id": synthesis_soul.id,
            "role": synthesis_soul.role,
            "system_prompt": synthesis_soul.system_prompt,
            "model_name": synthesis_soul.model_name,
            "provider": "",
            "temperature": None,
            "max_tokens": None,
            "required_tool_calls": [],
            "max_tool_iterations": 5,
        }
        assert "output_format" not in envelope.block_config

    @pytest.mark.asyncio
    async def test_dispatch_block_envelope_contains_full_per_branch_soul_fields(self):
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        reviewer = _make_soul("reviewer")
        fixer = _make_soul("fixer")
        inner = DispatchBlock(
            "isolated_dispatch_block",
            [
                DispatchBranch(
                    exit_id="approve",
                    label="Approve",
                    soul=reviewer,
                    task_instruction="Review draft.",
                ),
                DispatchBranch(
                    exit_id="revise",
                    label="Revise",
                    soul=fixer,
                    task_instruction="Revise draft.",
                ),
            ],
            MagicMock(),
        )
        wrapper = IsolatedBlockWrapper(block_id="isolated_dispatch_block", inner_block=inner)

        envelope = await self._execute_and_capture_envelope(wrapper)

        assert envelope.block_type == "dispatch"
        assert "branches" in envelope.block_config
        assert len(envelope.block_config["branches"]) == 2

        approve = envelope.block_config["branches"][0]
        revise = envelope.block_config["branches"][1]

        assert approve["exit_id"] == "approve"
        assert revise["exit_id"] == "revise"
        assert "soul_ref" not in approve
        assert "soul_ref" not in revise
        assert approve["soul"] == {
            "id": reviewer.id,
            "role": reviewer.role,
            "system_prompt": reviewer.system_prompt,
            "model_name": reviewer.model_name,
            "provider": "",
            "temperature": None,
            "max_tokens": None,
            "required_tool_calls": [],
            "max_tool_iterations": 5,
        }
        assert revise["soul"] == {
            "id": fixer.id,
            "role": fixer.role,
            "system_prompt": fixer.system_prompt,
            "model_name": fixer.model_name,
            "provider": "",
            "temperature": None,
            "max_tokens": None,
            "required_tool_calls": [],
            "max_tool_iterations": 5,
        }
