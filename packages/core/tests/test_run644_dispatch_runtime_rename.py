"""
Failing tests for RUN-644: rename runtime branching block from fanout to dispatch.

These tests enforce the runtime-only rename contract:
- canonical branching runtime surface is `dispatch`
- no compatibility path for `fanout`
- runtime registries and wrapper constants use `dispatch`
"""

from importlib import import_module

import pytest


class TestDispatchRuntimeSurface:
    """Runtime module/class naming must be dispatch-only."""

    def test_dispatch_module_exports_dispatch_symbols(self):
        module = import_module("runsight_core.blocks.dispatch")
        assert hasattr(module, "DispatchBranch")
        assert hasattr(module, "DispatchBlock")
        assert hasattr(module, "DispatchBlockDef")
        assert hasattr(module, "build")

    def test_fanout_module_is_removed_without_alias(self):
        with pytest.raises(ModuleNotFoundError):
            import_module("runsight_core.blocks.fanout")


class TestDispatchRuntimeRegistration:
    """Runtime registries must canonicalize on dispatch only."""

    def test_block_def_and_builder_registries_use_dispatch_only(self):
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY, BLOCK_DEF_REGISTRY

        assert "dispatch" in BLOCK_DEF_REGISTRY
        assert "dispatch" in BLOCK_BUILDER_REGISTRY
        assert "fanout" not in BLOCK_DEF_REGISTRY
        assert "fanout" not in BLOCK_BUILDER_REGISTRY

    def test_dispatch_block_def_default_type_is_dispatch(self):
        from runsight_core.blocks.dispatch import DispatchBlockDef

        assert DispatchBlockDef.model_fields["type"].default == "dispatch"


class TestDispatchRuntimeConstants:
    """Runtime constants and public exports must no longer mention fanout."""

    def test_llm_block_types_include_dispatch_not_fanout(self):
        from runsight_core.isolation.wrapper import LLM_BLOCK_TYPES

        assert "dispatch" in LLM_BLOCK_TYPES
        assert "fanout" not in LLM_BLOCK_TYPES

    def test_public_core_exports_include_dispatch_not_fanout(self):
        import runsight_core

        assert hasattr(runsight_core, "DispatchBlock")
        assert not hasattr(runsight_core, "FanOutBlock")
