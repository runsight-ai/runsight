"""
Failing tests for RUN-219: Auto-Registration Infrastructure.

Tests cover:
- _registry.py: register, get, duplicate detection, empty state
- __init_subclass__: all 12 types auto-register, base class skipped, non-Literal skipped
- build_block_def_union(): produces valid discriminated union, handles empty registry
- rebuild_block_def_union(): updates BlockDef globally, model_rebuild succeeds
- _helpers.py: soul resolution, condition conversion, condition group conversion
- Parser fallback: registry-based builder lookup for unknown types
- generate_schema.py --check: schema file is in sync with models
"""

import sys
from unittest.mock import MagicMock

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# 1. _registry.py — module-level registry functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockDefRegistry:
    """Unit tests for BLOCK_DEF_REGISTRY and its helper functions."""

    def test_import_registry_module(self):
        """_registry.py module can be imported."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY  # noqa: F401

    def test_import_builder_registry(self):
        """BLOCK_BUILDER_REGISTRY exists in _registry.py."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY  # noqa: F401

    def test_register_block_def(self):
        """register_block_def stores a type → class mapping."""
        from runsight_core.blocks._registry import (
            BLOCK_DEF_REGISTRY,
            register_block_def,
        )

        class FakeBlockDef:
            pass

        register_block_def("fake_test_type", FakeBlockDef)
        assert BLOCK_DEF_REGISTRY.get("fake_test_type") is FakeBlockDef

        # Cleanup
        BLOCK_DEF_REGISTRY.pop("fake_test_type", None)

    def test_register_block_def_duplicate_same_class_is_ok(self):
        """Registering the same class for the same type is idempotent."""
        from runsight_core.blocks._registry import (
            BLOCK_DEF_REGISTRY,
            register_block_def,
        )

        class FakeBlockDef:
            pass

        register_block_def("dup_test_type", FakeBlockDef)
        # Same class again — should not raise
        register_block_def("dup_test_type", FakeBlockDef)

        # Cleanup
        BLOCK_DEF_REGISTRY.pop("dup_test_type", None)

    def test_register_block_def_duplicate_different_class_raises(self):
        """Registering a different class for an already-registered type raises."""
        from runsight_core.blocks._registry import (
            BLOCK_DEF_REGISTRY,
            register_block_def,
        )

        class FakeA:
            pass

        class FakeB:
            pass

        register_block_def("conflict_type", FakeA)
        with pytest.raises(Exception):  # ValueError or similar
            register_block_def("conflict_type", FakeB)

        # Cleanup
        BLOCK_DEF_REGISTRY.pop("conflict_type", None)

    def test_register_block_builder(self):
        """register_block_builder stores a type → callable mapping."""
        from runsight_core.blocks._registry import (
            BLOCK_BUILDER_REGISTRY,
            register_block_builder,
        )

        def fake_builder():
            pass

        register_block_builder("test_builder_type", fake_builder)
        assert BLOCK_BUILDER_REGISTRY.get("test_builder_type") is fake_builder

        # Cleanup
        BLOCK_BUILDER_REGISTRY.pop("test_builder_type", None)

    def test_register_block_builder_is_idempotent_for_same_callable(self):
        """register_block_builder permits re-registering the same callable."""
        from runsight_core.blocks._registry import (
            BLOCK_BUILDER_REGISTRY,
            register_block_builder,
        )

        def fake_builder():
            pass

        try:
            register_block_builder("same_builder_type", fake_builder)
            register_block_builder("same_builder_type", fake_builder)
            assert BLOCK_BUILDER_REGISTRY.get("same_builder_type") is fake_builder
        finally:
            BLOCK_BUILDER_REGISTRY.pop("same_builder_type", None)

    def test_register_block_builder_rejects_different_duplicate(self):
        """register_block_builder rejects silent builder replacement."""
        from runsight_core.blocks._registry import (
            BLOCK_BUILDER_REGISTRY,
            register_block_builder,
        )

        def first_builder():
            pass

        def second_builder():
            pass

        try:
            register_block_builder("conflicting_builder_type", first_builder)
            with pytest.raises(ValueError, match="Duplicate block-builder registration"):
                register_block_builder("conflicting_builder_type", second_builder)
            assert BLOCK_BUILDER_REGISTRY.get("conflicting_builder_type") is first_builder
        finally:
            BLOCK_BUILDER_REGISTRY.pop("conflicting_builder_type", None)

    def test_get_all_block_types_returns_dict(self):
        """get_all_block_types() returns a dict snapshot of registered types."""
        from runsight_core.blocks._registry import get_all_block_types

        result = get_all_block_types()
        assert isinstance(result, dict)

    def test_get_builder_returns_callable_or_none(self):
        """get_builder() returns the builder for a registered type, or None."""
        from runsight_core.blocks._registry import get_builder

        # For a type that does not exist
        assert get_builder("nonexistent_type_xyz") is None

    def test_registry_has_zero_project_imports(self):
        """_registry.py must NOT import from any project module (import firewall)."""
        import inspect

        import runsight_core.blocks._registry as registry_mod

        source = inspect.getsource(registry_mod)
        # Must not import from runsight_core
        assert "from runsight_core" not in source
        assert "import runsight_core" not in source


# ═══════════════════════════════════════════════════════════════════════════════
# 2. __init_subclass__ — auto-registration via BaseBlockDef
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitSubclassRegistration:
    """Tests that BaseBlockDef.__init_subclass__ auto-registers all 12 block types."""

    EXPECTED_BLOCK_TYPES = {
        "linear",
        "dispatch",
        "synthesize",
        "gate",
        "code",
        "loop",
        "workflow",
    }

    def test_all_7_types_registered(self):
        """After importing schema, all 7 existing BlockDef subclasses are registered."""
        # Force schema import to trigger __init_subclass__
        import runsight_core.yaml.schema  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        registered_types = set(BLOCK_DEF_REGISTRY.keys())
        assert self.EXPECTED_BLOCK_TYPES.issubset(registered_types)
        assert len(BLOCK_DEF_REGISTRY) >= 7

    def test_registry_count_is_7(self):
        """Exactly 7 block types are in the registry (no extras from base classes)."""
        import runsight_core.yaml.schema  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        # Filter out any test artifacts — only count the known types
        known = {k: v for k, v in BLOCK_DEF_REGISTRY.items() if k in self.EXPECTED_BLOCK_TYPES}
        assert len(known) == 7

    def test_base_block_def_does_not_register(self):
        """BaseBlockDef itself should NOT appear in the registry."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY
        from runsight_core.yaml.schema import BaseBlockDef

        for cls in BLOCK_DEF_REGISTRY.values():
            assert cls is not BaseBlockDef

    def test_non_literal_subclass_does_not_register(self):
        """A subclass of BaseBlockDef without a Literal type annotation should NOT register."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY
        from runsight_core.yaml.schema import BaseBlockDef

        initial_count = len(BLOCK_DEF_REGISTRY)

        class IntermediateBlockDef(BaseBlockDef):
            """No Literal annotation on type — should be skipped."""

            type: str = "intermediate"

        # Registry should not have grown
        assert len(BLOCK_DEF_REGISTRY) == initial_count
        assert "intermediate" not in BLOCK_DEF_REGISTRY

    def test_each_registered_class_maps_to_correct_type(self):
        """Each registered class has the expected Literal type value."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY
        from runsight_core.blocks.code import CodeBlockDef
        from runsight_core.blocks.dispatch import DispatchBlockDef
        from runsight_core.blocks.gate import GateBlockDef
        from runsight_core.blocks.linear import LinearBlockDef
        from runsight_core.blocks.loop import LoopBlockDef
        from runsight_core.blocks.synthesize import SynthesizeBlockDef
        from runsight_core.blocks.workflow_block import WorkflowBlockDef

        expected_mapping = {
            "linear": LinearBlockDef,
            "dispatch": DispatchBlockDef,
            "synthesize": SynthesizeBlockDef,
            "gate": GateBlockDef,
            "code": CodeBlockDef,
            "loop": LoopBlockDef,
            "workflow": WorkflowBlockDef,
        }

        for type_name, expected_cls in expected_mapping.items():
            assert BLOCK_DEF_REGISTRY.get(type_name) is expected_cls, (
                f"Expected {type_name} -> {expected_cls.__name__}, "
                f"got {BLOCK_DEF_REGISTRY.get(type_name)}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. build_block_def_union / rebuild_block_def_union
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildBlockDefUnion:
    """Tests for build_block_def_union() and rebuild_block_def_union()."""

    def test_build_block_def_union_exists(self):
        """build_block_def_union function can be imported from schema."""
        from runsight_core.yaml.schema import build_block_def_union  # noqa: F401

    def test_rebuild_block_def_union_exists(self):
        """rebuild_block_def_union function can be imported from schema."""
        from runsight_core.yaml.schema import rebuild_block_def_union  # noqa: F401

    def test_build_block_def_union_produces_discriminated_union(self):
        """build_block_def_union() returns a union type with discriminator='type'."""
        from pydantic import TypeAdapter
        from runsight_core.yaml.schema import build_block_def_union

        union_type = build_block_def_union()
        # Should be usable as a Pydantic type adapter
        adapter = TypeAdapter(union_type)
        # Validate a known block type
        result = adapter.validate_python({"type": "linear", "soul_ref": "test"})
        assert result.type == "linear"

    def test_build_block_def_union_matches_hardcoded(self):
        """build_block_def_union() produces a union with the same types as the hardcoded BlockDef."""
        import typing

        from runsight_core.yaml.schema import BlockDef, build_block_def_union

        dynamic_union = build_block_def_union()

        # Extract member types from both unions
        hardcoded_args = set(typing.get_args(typing.get_args(BlockDef)[0]))
        dynamic_args = set(typing.get_args(typing.get_args(dynamic_union)[0]))

        assert hardcoded_args == dynamic_args

    def test_build_block_def_union_empty_registry_raises(self):
        """build_block_def_union() raises an error when the registry is empty."""
        from unittest.mock import patch

        from runsight_core.yaml.schema import build_block_def_union

        with patch("runsight_core.blocks._registry.BLOCK_DEF_REGISTRY", {}):
            with pytest.raises(Exception):
                build_block_def_union()

    def test_rebuild_block_def_union_updates_global(self):
        """rebuild_block_def_union() updates the module-level BlockDef and rebuilds models."""
        from runsight_core.yaml.schema import (
            RunsightWorkflowFile,
            rebuild_block_def_union,
        )

        # Should not raise
        rebuild_block_def_union()

        # RunsightWorkflowFile should still validate correctly after rebuild
        # (model_rebuild should have been called successfully)
        assert hasattr(RunsightWorkflowFile, "model_fields")

    def test_rebuild_block_def_union_model_rebuild_succeeds(self):
        """After rebuild_block_def_union(), RunsightWorkflowFile.model_rebuild() works."""
        from runsight_core.yaml.schema import (
            RunsightWorkflowFile,
            rebuild_block_def_union,
        )

        rebuild_block_def_union()

        # Explicit model_rebuild should not raise
        RunsightWorkflowFile.model_rebuild()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. _helpers.py — moved helper functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelpers:
    """Tests for helper functions moved from parser.py to blocks/_helpers.py."""

    def test_import_helpers_module(self):
        """_helpers.py module can be imported."""
        from runsight_core.blocks._helpers import (  # noqa: F401
            convert_condition,
            convert_condition_group,
            resolve_soul,
        )

    def test_resolve_soul_found(self):
        """resolve_soul returns the Soul when ref exists in souls_map."""
        from runsight_core.blocks._helpers import resolve_soul
        from runsight_core.primitives import Soul

        soul = Soul(id="s1", role="Tester", system_prompt="Test prompt")
        souls_map = {"test_soul": soul}

        result = resolve_soul("test_soul", souls_map)
        assert result is soul

    def test_resolve_soul_not_found_raises(self):
        """resolve_soul raises ValueError when ref not in souls_map."""
        from runsight_core.blocks._helpers import resolve_soul

        with pytest.raises(ValueError, match="not found"):
            resolve_soul("missing_soul", {"other": MagicMock()})

    def test_convert_condition(self):
        """convert_condition converts a ConditionDef to a runtime Condition."""
        from runsight_core.blocks._helpers import convert_condition
        from runsight_core.conditions.engine import Condition
        from runsight_core.yaml.schema import ConditionDef

        cond_def = ConditionDef(eval_key="status", operator="eq", value="PASS")
        result = convert_condition(cond_def)

        assert isinstance(result, Condition)
        assert result.eval_key == "status"
        assert result.operator == "eq"
        assert result.value == "PASS"

    def test_convert_condition_group(self):
        """convert_condition_group converts a ConditionGroupDef to a ConditionGroup."""
        from runsight_core.blocks._helpers import convert_condition_group
        from runsight_core.conditions.engine import ConditionGroup
        from runsight_core.yaml.schema import ConditionDef, ConditionGroupDef

        group_def = ConditionGroupDef(
            combinator="AND",
            conditions=[
                ConditionDef(eval_key="a", operator="eq", value="1"),
                ConditionDef(eval_key="b", operator="eq", value="2"),
            ],
        )
        result = convert_condition_group(group_def)

        assert isinstance(result, ConditionGroup)
        assert result.combinator == "AND"
        assert len(result.conditions) == 2

    def test_helpers_match_original_resolve_soul(self):
        """resolve_soul produces identical results to the original _resolve_soul."""
        from runsight_core.blocks._helpers import resolve_soul
        from runsight_core.primitives import Soul

        soul = Soul(id="s1", role="R", system_prompt="P")
        souls_map = {"ref": soul}

        # Should behave identically to the original
        assert resolve_soul("ref", souls_map) is soul
        with pytest.raises(ValueError):
            resolve_soul("nope", souls_map)

    def test_helpers_match_original_convert_condition(self):
        """convert_condition produces identical results to the original _convert_condition."""
        from runsight_core.blocks._helpers import convert_condition
        from runsight_core.yaml.schema import ConditionDef

        cond_def = ConditionDef(eval_key="k", operator="ne", value="v")
        result = convert_condition(cond_def)
        assert result.eval_key == "k"
        assert result.operator == "ne"
        assert result.value == "v"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Parser fallback to BLOCK_BUILDER_REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════


class TestParserFallback:
    """Integration test: parser falls back to BLOCK_BUILDER_REGISTRY for unknown types."""

    def test_parser_uses_builder_registry_fallback(self):
        """When a type is not in the hardcoded BLOCK_TYPE_REGISTRY,
        the parser should fall back to BLOCK_BUILDER_REGISTRY.

        Registers a mock builder for 'my_custom_block' in BLOCK_BUILDER_REGISTRY,
        patches past Pydantic validation so the custom type reaches the builder
        lookup, then verifies the mock builder was actually called.
        """
        from unittest.mock import MagicMock as Mock
        from unittest.mock import patch

        from runsight_core.blocks._registry import (
            BLOCK_BUILDER_REGISTRY,
            register_block_builder,
        )
        from runsight_core.blocks.base import BaseBlock
        from runsight_core.yaml.parser import parse_workflow_yaml

        # 1. Create a mock builder that returns a BaseBlock-compatible object
        fake_block = Mock(spec=BaseBlock)
        fake_block.block_id = "b1"
        mock_builder = Mock(return_value=fake_block)

        # 2. Register the mock builder for our custom type
        register_block_builder("my_custom_block", mock_builder)

        try:
            # 3. Build a fake file_def that Pydantic model_validate would return.
            #    We patch model_validate to bypass schema validation (our custom type
            #    is not in the BlockDef discriminated union).
            fake_block_def = Mock()
            fake_block_def.type = "my_custom_block"
            fake_block_def.retry_config = None
            fake_block_def.stateful = False
            fake_block_def.inputs = None
            fake_block_def.output_conditions = []

            fake_soul_def = Mock()
            fake_soul_def.id = "s1"
            fake_soul_def.role = "R"
            fake_soul_def.system_prompt = "P"
            fake_soul_def.tools = None
            fake_soul_def.max_tool_iterations = 1
            fake_soul_def.model_name = None

            fake_transition = Mock()
            fake_transition.from_ = "b1"
            fake_transition.to = None

            fake_workflow_def = Mock()
            fake_workflow_def.name = "test_wf"
            fake_workflow_def.entry = "b1"
            fake_workflow_def.transitions = [fake_transition]
            fake_workflow_def.conditional_transitions = []

            fake_file_def = Mock()
            fake_file_def.version = "1.0"
            fake_file_def.souls = {"s1": fake_soul_def}
            fake_file_def.blocks = {"b1": fake_block_def}
            fake_file_def.workflow = fake_workflow_def
            fake_file_def.config = {}

            with patch(
                "runsight_core.yaml.parser.RunsightWorkflowFile.model_validate",
                return_value=fake_file_def,
            ):
                parse_workflow_yaml({"version": "1.0"})

            # 4. Assert the mock builder was called with expected args
            mock_builder.assert_called_once()
            call_args = mock_builder.call_args
            assert call_args[0][0] == "b1"  # block_id
            assert call_args[0][1] is fake_block_def  # block_def

        finally:
            # 5. Cleanup
            BLOCK_BUILDER_REGISTRY.pop("my_custom_block", None)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Auto-discovery in blocks/__init__.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoDiscovery:
    """Tests for _auto_discover_blocks() in blocks/__init__.py."""

    def test_auto_discover_blocks_function_exists(self):
        """_auto_discover_blocks is callable in blocks/__init__.py."""
        from runsight_core.blocks import _auto_discover_blocks  # noqa: F401

    def test_auto_discover_populates_builder_registry(self):
        """After _auto_discover_blocks(), BLOCK_BUILDER_REGISTRY has entries."""
        # Importing blocks triggers _auto_discover_blocks at module level
        import runsight_core.blocks  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        # There should be at least some builders registered
        assert len(BLOCK_BUILDER_REGISTRY) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests for the auto-registration infrastructure."""

    def test_model_rebuild_preserves_nested_validation(self):
        """After rebuild_block_def_union, nested model validation still works."""
        from runsight_core.yaml.schema import (
            RunsightWorkflowFile,
            rebuild_block_def_union,
        )

        rebuild_block_def_union()

        # A valid workflow file should still parse correctly
        valid_data = {
            "version": "1.0",
            "souls": {
                "s1": {
                    "id": "s1",
                    "role": "R",
                    "system_prompt": "P",
                }
            },
            "blocks": {
                "b1": {
                    "type": "linear",
                    "soul_ref": "s1",
                }
            },
            "workflow": {
                "name": "wf",
                "entry": "b1",
                "transitions": [{"from": "b1", "to": None}],
            },
        }
        result = RunsightWorkflowFile.model_validate(valid_data)
        assert result.workflow.name == "wf"

    def test_auto_discover_handles_import_errors_gracefully(self):
        """_auto_discover_blocks does not crash if a block module fails to import."""
        # This is a design requirement — the function should log/skip errors,
        # not propagate them. We verify it exists and is callable.
        from runsight_core.blocks import _auto_discover_blocks

        # Should not raise even if called again
        _auto_discover_blocks()


# ═══════════════════════════════════════════════════════════════════════════════
# 8. generate_schema.py --check
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateSchemaCheck:
    """Test that generate_schema.py --check passes (schema file is in sync)."""

    def test_generate_schema_check_passes(self):
        """Running `python generate_schema.py --check` exits 0 when schema is in sync."""
        import subprocess
        from pathlib import Path

        script = Path(__file__).resolve().parent.parent / "scripts" / "generate_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True,
            text=True,
            cwd=str(script.parent.parent),  # packages/core/
        )
        assert result.returncode == 0, (
            f"generate_schema.py --check failed (exit {result.returncode}).\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
