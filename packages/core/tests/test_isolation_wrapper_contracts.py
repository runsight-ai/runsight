"""Isolation wrapper construction, envelope, and harness delegation contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.block_io import BlockOutput, build_block_context
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.observer import compute_prompt_hash, compute_soul_version
from runsight_core.primitives import Soul, Step
from runsight_core.state import BlockResult, WorkflowState


class TestIsolatedBlockWrapperWrapsBlocks:
    """IsolatedBlockWrapper can wrap each LLM block type."""

    def test_import_isolated_block_wrapper(self):
        """IsolatedBlockWrapper is importable from runsight_core.isolation."""
        from runsight_core.isolation import IsolatedBlockWrapper

        assert IsolatedBlockWrapper is not None

    def test_wrapper_is_base_block_subclass(self):
        """IsolatedBlockWrapper must be a BaseBlock subclass."""
        from runsight_core.isolation import IsolatedBlockWrapper

        assert issubclass(IsolatedBlockWrapper, BaseBlock)

    def test_wraps_linear_block(self):
        """IsolatedBlockWrapper can wrap a LinearBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)
        assert wrapper.block_id == "isolated_linear_block"

    def test_wraps_gate_block(self):
        """IsolatedBlockWrapper can wrap a GateBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = GateBlock("isolated_gate_block", soul, "evaluation_source_block", runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_gate_block", inner_block=inner)
        assert wrapper.block_id == "isolated_gate_block"

    def test_wraps_synthesize_block(self):
        """IsolatedBlockWrapper can wrap a SynthesizeBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = SynthesizeBlock("isolated_synthesis_block", ["a", "b"], soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_synthesis_block", inner_block=inner)
        assert wrapper.block_id == "isolated_synthesis_block"

    def test_wraps_dispatch_block(self):
        """IsolatedBlockWrapper can wrap a DispatchBlock."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        branches = [
            DispatchBranch(exit_id="a", label="A", soul=soul, task_instruction="do A"),
        ]
        inner = DispatchBlock("isolated_dispatch_block", branches, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_dispatch_block", inner_block=inner)
        assert wrapper.block_id == "isolated_dispatch_block"


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestWrapperExposesSoul:
    """The wrapper must expose self.soul from the inner block for telemetry."""

    def test_wrapper_soul_attribute_from_linear_block(self):
        """Wrapper.soul returns the inner LinearBlock's soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)
        assert wrapper.soul is soul

    def test_wrapper_soul_attribute_from_gate_block(self):
        """Wrapper.soul returns the inner GateBlock's gate_evaluator_soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = GateBlock("isolated_gate_block", soul, "evaluation_source_block", runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_gate_block", inner_block=inner)
        # The wrapper must expose a soul (however it maps the inner block's attribute)
        assert wrapper.soul is not None
        assert compute_prompt_hash(wrapper.soul) == compute_prompt_hash(soul)

    def test_prompt_hash_computable_from_wrapper_soul(self):
        """Observer can compute prompt_hash from wrapper.soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)
        assert compute_prompt_hash(wrapper.soul) is not None

    def test_wrapper_soul_version_computable_from_wrapper_soul(self):
        """Observer can compute soul_version from wrapper.soul."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)
        assert compute_soul_version(wrapper.soul) is not None

    @pytest.mark.asyncio
    async def test_wrapper_envelope_preserves_extended_soul_runtime_fields(self):
        """Subprocess envelope keeps provider/runtime tool-contract fields intact."""
        from unittest.mock import MagicMock

        from runsight_core.isolation import IsolatedBlockWrapper

        soul = Soul(
            id="tool_enabled_soul",
            kind="soul",
            name="Tester",
            role="Tester",
            system_prompt="Use tools carefully.",
            model_name="fixture-isolation-model",
            provider="fixture-provider",
            temperature=0.0,
            max_tokens=256,
            required_tool_calls=["http_request", "notification_delivery_hook"],
        )
        inner = LinearBlock("isolated_linear_block", soul, MagicMock())
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
        state = _make_state()
        await wrapper.execute(_make_ctx(wrapper, state))

        envelope = captured["envelope"]
        assert envelope.soul.provider == "fixture-provider"
        assert envelope.soul.temperature == 0.0
        assert envelope.soul.max_tokens == 256
        assert envelope.soul.required_tool_calls == ["http_request", "notification_delivery_hook"]


# ==============================================================================
# Behavior coverage
# ==============================================================================


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


class TestBudgetFittingInsideSubprocess:
    """The wrapper must NOT call fit_to_budget on the engine side.
    Budget fitting happens inside the subprocess worker."""

    def test_wrapper_does_not_import_fit_to_budget(self):
        """IsolatedBlockWrapper.execute() does not call fit_to_budget."""
        from unittest.mock import AsyncMock, MagicMock, patch

        import runsight_core.memory.budget as budget_module
        from runsight_core.isolation import IsolatedBlockWrapper

        soul = _make_soul()
        runner = MagicMock()
        inner = LinearBlock("isolated_linear_block", soul, runner)
        inner.stateful = True
        wrapper = IsolatedBlockWrapper(block_id="isolated_linear_block", inner_block=inner)

        mock_result = ResultEnvelope(
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

        state = _make_state()
        with patch.object(
            wrapper, "_run_in_subprocess", new_callable=AsyncMock, return_value=mock_result
        ):
            with patch.object(
                budget_module, "fit_to_budget", wraps=budget_module.fit_to_budget
            ) as spy:
                asyncio.get_event_loop().run_until_complete(
                    wrapper.execute(_make_ctx(wrapper, state))
                )
                # fit_to_budget must NOT be called on the engine side
                spy.assert_not_called()


# ==============================================================================
# Behavior coverage
# ==============================================================================


class TestEnvelopeBlockContracts:
    """Wrapper emits full envelope config for supported block types."""

    async def _execute_and_capture_envelope(
        self,
        wrapper,
        *,
        state: WorkflowState | None = None,
    ) -> ContextEnvelope:
        captured: dict[str, ContextEnvelope] = {}

        async def _capture(envelope: ContextEnvelope) -> ResultEnvelope:
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
