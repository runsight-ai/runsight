"""Isolated block wrapper harness delegation behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.block_io import BlockOutput, build_block_context
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState


class TestWrapperHarnessDelegationPreventsDirectExecution:
    """Wrapper delegates to SubprocessHarness.run(), not direct block.execute()."""

    def test_wrapper_execute_returns_block_output(self):
        """Wrapper.execute() returns a BlockOutput (via subprocess)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        # The wrapper should invoke SubprocessHarness, not inner.execute() directly
        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
            output="test output",
            exit_handle="done",
            cost_usd=0.001,
            total_tokens=42,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            result_output = asyncio.get_event_loop().run_until_complete(
                wrapper.execute(_make_ctx(wrapper, state))
            )
        assert isinstance(result_output, BlockOutput)
        assert result_output.output == "test output"

    def test_inner_block_execute_not_called_directly(self):
        """The wrapper must NOT call inner_block.execute() in the engine process."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        inner.execute = AsyncMock()

        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
            block_id="isolated_linear_block",
            output="done",
            exit_handle="done",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            asyncio.get_event_loop().run_until_complete(wrapper.execute(_make_ctx(wrapper, state)))

        inner.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrapper_serializes_declared_workflow_mapped_results(self):
        """Declared workflow-mapped string/dict results must not crash envelope building."""
        import json
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.state import BlockResult

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)
        wrapper.declared_inputs = {
            "real_output": "real_block.output",
            "workflow_string": "workflow_mapped_string.output",
            "workflow_phase": "workflow_mapped_dict.phase",
            "workflow_status": "workflow_mapped_dict.status",
        }

        captured = {}

        async def _capture(envelope: ContextEnvelope) -> ResultEnvelope:
            captured["envelope"] = envelope
            return ResultEnvelope(
                block_id="isolated_linear_block",
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
        state = _make_state().model_copy(
            update={
                "results": {
                    "real_block": BlockResult(output="wrapped"),
                    "workflow_mapped_string": "plain string output",
                    "workflow_mapped_dict": {"phase": "primary_pass", "status": "ok"},
                }
            }
        )

        result_output = await wrapper.execute(_make_ctx(wrapper, state))

        envelope = captured["envelope"]
        assert envelope.inputs == {
            "real_output": "wrapped",
            "workflow_string": "plain string output",
            "workflow_phase": "primary_pass",
            "workflow_status": "ok",
        }
        assert set(envelope.scoped_results) == {
            "real_block",
            "workflow_mapped_string",
            "workflow_mapped_dict",
        }
        assert envelope.scoped_results["real_block"]["output"] == "wrapped"
        assert envelope.scoped_results["workflow_mapped_string"]["output"] == "plain string output"
        assert json.loads(envelope.scoped_results["workflow_mapped_dict"]["output"]) == {
            "phase": "primary_pass",
            "status": "ok",
        }
        assert result_output.output == "ok"

    @pytest.mark.asyncio
    async def test_wrapper_envelope_preserves_step_declared_inputs(self):
        """Step-resolved inputs must cross the isolation boundary."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)
        captured = {}

        async def _capture(envelope: ContextEnvelope) -> ResultEnvelope:
            captured["envelope"] = envelope
            return ResultEnvelope(
                block_id="isolated_linear_block",
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
        state = WorkflowState(results={"source": BlockResult(output="declared value")})
        step = Step(block=wrapper, declared_inputs={"data": "source"})
        ctx = build_block_context(wrapper, state, step=step)

        assert ctx.inputs == {"data": "declared value"}

        await wrapper.execute(ctx)

        assert captured["envelope"].inputs == {"data": "declared value"}


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestWrapperHarnessWiringContract:
    """wrapper must delegate to SubprocessHarness with no direct-execute bypass."""

    @staticmethod
    def _write_external_soul(base_dir: Path) -> None:
        souls_dir = base_dir / "custom" / "souls"
        souls_dir.mkdir(parents=True, exist_ok=True)
        (souls_dir / "writer.yaml").write_text(
            "\n".join(
                [
                    "id: writer",
                    "kind: soul",
                    "name: Writer",
                    "role: Writer",
                    "system_prompt: Write clearly.",
                    "model_name: fixture-isolation-model",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_linear_workflow(base_dir: Path) -> Path:
        workflow_path = base_dir / "workflow.yaml"
        workflow_path.write_text(
            "\n".join(
                [
                    "id: wrapper-harness-wiring",
                    "kind: workflow",
                    'version: "1.0"',
                    "config:",
                    "  model_name: fixture-isolation-model",
                    "blocks:",
                    "  draft:",
                    "    type: linear",
                    "    soul_ref: writer",
                    "workflow:",
                    "  name: wrapper_harness_wiring",
                    "  entry: draft",
                    "  transitions:",
                    "    - from: draft",
                    "      to: null",
                ]
            ),
            encoding="utf-8",
        )
        return workflow_path

    @pytest.mark.asyncio
    async def test_execute_delegates_to_harness_run_and_never_calls_inner_execute(self):
        from unittest.mock import AsyncMock, MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        inner = LinearBlock("isolated_linear_block", soul, MagicMock())
        inner.execute = AsyncMock()

        result = ResultEnvelope(
            block_id="isolated_linear_block",
            output="subprocess output",
            exit_handle="done",
            cost_usd=0.25,
            total_tokens=123,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

        class _FakeHarness:
            def __init__(self, result_envelope: ResultEnvelope):
                self.result_envelope = result_envelope
                self.calls: list[ContextEnvelope] = []

            async def run(self, envelope: ContextEnvelope) -> ResultEnvelope:
                self.calls.append(envelope)
                return self.result_envelope

        harness = _FakeHarness(result)
        wrapper = IsolatedBlockWrapper(
            block_id="isolated_linear_block", inner_block=inner, harness=harness
        )
        wrapper.declared_inputs = {"instruction": "shared_memory._resolved_inputs.instruction"}

        state = _make_state()
        state = state.model_copy(
            update={"shared_memory": {"_resolved_inputs": {"instruction": "Summarize this"}}}
        )
        block_output = await wrapper.execute(_make_ctx(wrapper, state))

        assert len(harness.calls) == 1
        assert harness.calls[0].block_id == "isolated_linear_block"
        # The instruction is conveyed via scoped_shared_memory["_resolved_inputs"]
        assert (
            harness.calls[0].scoped_shared_memory.get("_resolved_inputs", {}).get("instruction")
            == "Summarize this"
        )
        inner.execute.assert_not_called()
        assert block_output.output == "subprocess output"
        assert block_output.cost_usd == pytest.approx(0.25)
        assert block_output.total_tokens == 123

    @pytest.mark.asyncio
    async def test_not_implemented_from_subprocess_path_is_not_swallowed_by_direct_fallback(self):
        from unittest.mock import AsyncMock, MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        inner = LinearBlock("isolated_linear_block", soul, MagicMock())
        inner.execute = AsyncMock()
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        async def _not_implemented(_: ContextEnvelope) -> ResultEnvelope:
            raise NotImplementedError("subprocess wiring missing")

        wrapper._run_in_subprocess = _not_implemented

        with pytest.raises(NotImplementedError):
            await wrapper.execute(_make_ctx(wrapper, _make_state()))

        inner.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_in_subprocess_delegates_to_harness_with_exact_envelope(self):
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.isolation.envelope import PromptEnvelope, SoulEnvelope

        expected = ResultEnvelope(
            block_id="isolated_linear_block",
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

        class _FakeHarness:
            def __init__(self):
                self.calls: list[ContextEnvelope] = []

            async def run(self, envelope: ContextEnvelope) -> ResultEnvelope:
                self.calls.append(envelope)
                return expected

        harness = _FakeHarness()
        wrapper = IsolatedBlockWrapper(
            block_id="isolated_linear_block",
            inner_block=LinearBlock("isolated_linear_block", _make_soul(), MagicMock()),
            harness=harness,
        )
        envelope = ContextEnvelope(
            block_id="isolated_linear_block",
            block_type="linear",
            block_config={},
            soul=SoulEnvelope(
                id="writer",
                role="Writer",
                system_prompt="Write clearly.",
                model_name="fixture-isolation-model",
                provider="fixture-provider",
                temperature=0.0,
                max_tokens=256,
            ),
            tools=[],
            prompt=PromptEnvelope(id="isolation-prompt", instruction="Do the thing", context={}),
            scoped_results={},
            scoped_shared_memory={},
            conversation_history=[],
            timeout_seconds=30,
            max_output_bytes=1_000_000,
        )

        actual = await wrapper._run_in_subprocess(envelope)

        assert actual == expected
        assert harness.calls == [envelope]

    def test_parse_workflow_yaml_wires_subprocess_harness_into_wrapped_llm_block(
        self, tmp_path: Path
    ):
        from unittest.mock import MagicMock

        from runsight_core.isolation import SubprocessHarness
        from runsight_core.yaml.parser import parse_workflow_yaml

        self._write_external_soul(tmp_path)
        workflow_path = self._write_linear_workflow(tmp_path)

        workflow = parse_workflow_yaml(
            str(workflow_path),
            runner=MagicMock(),
            api_keys={"fixture-provider": "dummy-engine-key"},
        )
        wrapped_block = workflow.blocks["draft"]

        harness = getattr(wrapped_block, "harness", None)
        assert harness is not None
        assert isinstance(harness, SubprocessHarness)
