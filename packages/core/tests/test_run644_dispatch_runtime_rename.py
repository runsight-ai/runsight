"""
Failing tests for RUN-644: rename runtime branching block from fanout to dispatch.

These tests enforce the runtime-only rename contract:
- canonical branching runtime surface is `dispatch`
- no compatibility path for `fanout`
- runtime registries and wrapper constants use `dispatch`
"""

import inspect
from importlib import import_module
from unittest.mock import MagicMock, patch

import pytest
from runsight_core.primitives import Soul
from runsight_core.yaml.parser import parse_workflow_yaml


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


class TestDispatchRuntimeTextSurfaces:
    """Runtime-owned docs/comments must not describe router as a workflow block."""

    def test_schema_conditional_transition_docstring_has_no_router_block_language(self):
        from runsight_core.yaml.schema import ConditionalTransitionDef

        doc = inspect.getdoc(ConditionalTransitionDef) or ""
        assert "router_block" not in doc
        assert "type: router" not in doc


class TestDispatchParserIntegration:
    """Workflow parsing/building entry path must canonicalize on dispatch."""

    @staticmethod
    def _souls_map():
        return {
            "agent_a": Soul(id="agent_a_id", role="Agent A", system_prompt="A"),
            "agent_b": Soul(id="agent_b_id", role="Agent B", system_prompt="B"),
        }

    def test_parse_workflow_yaml_accepts_dispatch_block_type(self):
        yaml_content = """
version: "1.0"
blocks:
  branch:
    type: dispatch
    exits:
      - id: a
        label: Branch A
        soul_ref: agent_a
        task: Do A
      - id: b
        label: Branch B
        soul_ref: agent_b
        task: Do B
workflow:
  name: dispatch_parse_test
  entry: branch
  transitions:
    - from: branch
      to: null
"""
        with patch(
            "runsight_core.yaml.parser._discovery_module._discover_souls",
            return_value=self._souls_map(),
        ):
            workflow = parse_workflow_yaml(yaml_content, runner=MagicMock())

        assert workflow.name == "dispatch_parse_test"
        assert "branch" in workflow.blocks

    def test_parse_workflow_yaml_rejects_legacy_fanout_block_type(self):
        yaml_content = """
version: "1.0"
blocks:
  branch:
    type: fanout
    exits:
      - id: a
        label: Branch A
        soul_ref: agent_a
        task: Do A
      - id: b
        label: Branch B
        soul_ref: agent_b
        task: Do B
workflow:
  name: fanout_parse_test
  entry: branch
  transitions:
    - from: branch
      to: null
"""
        with patch(
            "runsight_core.yaml.parser._discovery_module._discover_souls",
            return_value=self._souls_map(),
        ):
            with pytest.raises(Exception, match="fanout|Unknown block type|validation"):
                parse_workflow_yaml(yaml_content, runner=MagicMock())
