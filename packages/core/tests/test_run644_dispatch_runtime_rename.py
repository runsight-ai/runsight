"""
Runtime surface tests for the canonical dispatch branching block.

These tests keep the current runtime contract focused on the dispatch surface:
- dispatch exports remain available from the runtime module
- runtime registries and wrapper constants expose dispatch
- parser/build entry path accepts dispatch workflow definitions
"""

from importlib import import_module
from unittest.mock import MagicMock, patch

from runsight_core.primitives import Soul
from runsight_core.yaml.parser import parse_workflow_yaml


class TestDispatchRuntimeSurface:
    """Runtime module/class naming remains centered on dispatch."""

    def test_dispatch_module_exports_dispatch_symbols(self):
        module = import_module("runsight_core.blocks.dispatch")
        assert hasattr(module, "DispatchBranch")
        assert hasattr(module, "DispatchBlock")
        assert hasattr(module, "DispatchBlockDef")
        assert hasattr(module, "build")


class TestDispatchRuntimeRegistration:
    """Runtime registries expose dispatch for branching workflows."""

    def test_block_def_and_builder_registries_use_dispatch_only(self):
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY, BLOCK_DEF_REGISTRY

        assert "dispatch" in BLOCK_DEF_REGISTRY
        assert "dispatch" in BLOCK_BUILDER_REGISTRY

    def test_dispatch_block_def_default_type_is_dispatch(self):
        from runsight_core.blocks.dispatch import DispatchBlockDef

        assert DispatchBlockDef.model_fields["type"].default == "dispatch"


class TestDispatchRuntimeConstants:
    """Runtime constants and public exports include dispatch."""

    def test_llm_block_types_include_dispatch_not_fanout(self):
        from runsight_core.isolation.wrapper import LLM_BLOCK_TYPES

        assert "dispatch" in LLM_BLOCK_TYPES

    def test_public_core_exports_include_dispatch(self):
        import runsight_core

        assert hasattr(runsight_core, "DispatchBlock")


class TestDispatchParserIntegration:
    """Workflow parsing/building entry path accepts dispatch."""

    @staticmethod
    def _souls_map():
        return {
            "agent_a": Soul(
                id="agent_a_id", kind="soul", name="Agent A", role="Agent A", system_prompt="A"
            ),
            "agent_b": Soul(
                id="agent_b_id", kind="soul", name="Agent B", role="Agent B", system_prompt="B"
            ),
        }

    def test_parse_workflow_yaml_accepts_dispatch_block_type(self):
        yaml_content = """
id: test-workflow
kind: workflow
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
        with patch("runsight_core.yaml.parser.SoulScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value.ids.return_value = self._souls_map()
            workflow = parse_workflow_yaml(yaml_content, runner=MagicMock())

        assert workflow.name == "dispatch_parse_test"
        assert "branch" in workflow.blocks
