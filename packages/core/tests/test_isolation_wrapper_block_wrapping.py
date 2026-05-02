"""Isolated block wrapper wrapping behavior."""

from __future__ import annotations

from isolation_wrapper_helpers import make_soul as _make_soul
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.synthesize import SynthesizeBlock


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
