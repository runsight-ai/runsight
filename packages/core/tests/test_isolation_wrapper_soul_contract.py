"""Isolated block wrapper soul contract behavior."""

from __future__ import annotations

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.observer import compute_prompt_hash, compute_soul_version
from runsight_core.primitives import Soul


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
