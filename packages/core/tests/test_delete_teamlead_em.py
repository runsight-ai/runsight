"""
Failing tests for RUN-284: Delete TeamLeadBlock and EngineeringManagerBlock.

Both specialized agent blocks are being removed — they are expressible as
LinearBlock with the right soul/prompt.  The built-in soul
``engineering_manager`` in parser.py BUILT_IN_SOULS is also removed.

Tests verify:
1. Block source files deleted from disk
2. Imports of deleted classes raise ImportError
3. Deleted classes absent from runsight_core.__all__
4. Block registry has no team_lead / engineering_manager entries
5. YAML with type: team_lead or type: engineering_manager raises validation error
6. engineering_manager removed from BUILT_IN_SOULS
7. test_advanced_blocks.py deleted (only tested TeamLead/EM)
8. Block registry count drops to 7 (from 9)
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

BLOCKS_DIR = Path(__file__).resolve().parent.parent / "src" / "runsight_core" / "blocks"
TESTS_DIR = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Block source files deleted from disk
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockFilesDeleted:
    """Verify that team_lead.py and engineering_manager.py no longer exist."""

    def test_team_lead_file_does_not_exist(self):
        """blocks/team_lead.py must be deleted."""
        path = BLOCKS_DIR / "team_lead.py"
        assert not path.exists(), f"{path} still exists on disk — it must be deleted"

    def test_engineering_manager_file_does_not_exist(self):
        """blocks/engineering_manager.py must be deleted."""
        path = BLOCKS_DIR / "engineering_manager.py"
        assert not path.exists(), f"{path} still exists on disk — it must be deleted"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Imports of deleted classes raise ImportError
# ═══════════════════════════════════════════════════════════════════════════════


class TestImportsRaiseError:
    """Importing the deleted block classes must raise ImportError."""

    def test_import_team_lead_block_raises(self):
        """``from runsight_core import TeamLeadBlock`` must raise ImportError."""
        with pytest.raises(ImportError):
            from runsight_core.blocks.team_lead import TeamLeadBlock  # noqa: F401

    def test_import_engineering_manager_block_raises(self):
        """``from runsight_core.blocks.engineering_manager import EngineeringManagerBlock``
        must raise ImportError."""
        with pytest.raises(ImportError):
            from runsight_core.blocks.engineering_manager import (
                EngineeringManagerBlock,  # noqa: F401
            )

    def test_import_team_lead_block_def_raises(self):
        """``from runsight_core.blocks.team_lead import TeamLeadBlockDef``
        must raise ImportError."""
        with pytest.raises(ImportError):
            from runsight_core.blocks.team_lead import TeamLeadBlockDef  # noqa: F401

    def test_import_engineering_manager_block_def_raises(self):
        """``from runsight_core.blocks.engineering_manager import EngineeringManagerBlockDef``
        must raise ImportError."""
        with pytest.raises(ImportError):
            from runsight_core.blocks.engineering_manager import (
                EngineeringManagerBlockDef,  # noqa: F401
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Deleted classes absent from runsight_core.__all__
# ═══════════════════════════════════════════════════════════════════════════════


class TestAllExports:
    """runsight_core.__all__ must not mention the deleted classes."""

    def test_team_lead_block_not_in_all(self):
        """'TeamLeadBlock' must not appear in runsight_core.__all__."""
        import runsight_core

        assert "TeamLeadBlock" not in runsight_core.__all__

    def test_engineering_manager_block_not_in_all(self):
        """'EngineeringManagerBlock' must not appear in runsight_core.__all__."""
        import runsight_core

        assert "EngineeringManagerBlock" not in runsight_core.__all__


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Block registry has no team_lead / engineering_manager entries
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryCleanup:
    """The block-def and block-builder registries must not contain the deleted types."""

    def test_team_lead_not_in_block_def_registry(self):
        """'team_lead' must not be in BLOCK_DEF_REGISTRY."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        assert "team_lead" not in BLOCK_DEF_REGISTRY, (
            "'team_lead' is still registered in BLOCK_DEF_REGISTRY"
        )

    def test_engineering_manager_not_in_block_def_registry(self):
        """'engineering_manager' must not be in BLOCK_DEF_REGISTRY."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        assert "engineering_manager" not in BLOCK_DEF_REGISTRY, (
            "'engineering_manager' is still registered in BLOCK_DEF_REGISTRY"
        )

    def test_team_lead_not_in_block_builder_registry(self):
        """'team_lead' must not be in BLOCK_BUILDER_REGISTRY."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        assert "team_lead" not in BLOCK_BUILDER_REGISTRY, (
            "'team_lead' is still registered in BLOCK_BUILDER_REGISTRY"
        )

    def test_engineering_manager_not_in_block_builder_registry(self):
        """'engineering_manager' must not be in BLOCK_BUILDER_REGISTRY."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        assert "engineering_manager" not in BLOCK_BUILDER_REGISTRY, (
            "'engineering_manager' is still registered in BLOCK_BUILDER_REGISTRY"
        )

    def test_block_def_registry_has_7_known_types(self):
        """After deletion, the block-def registry should have exactly 7 known types."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        expected_types = {
            "linear",
            "fanout",
            "synthesize",
            "gate",
            "code",
            "loop",
            "workflow",
        }
        known = {k for k in BLOCK_DEF_REGISTRY if k in expected_types}
        assert len(known) == 7, (
            f"Expected 7 known block-def types, got {len(known)}. Missing: {expected_types - known}"
        )
        # Also verify neither deleted type is present
        assert "team_lead" not in BLOCK_DEF_REGISTRY
        assert "engineering_manager" not in BLOCK_DEF_REGISTRY

    def test_block_builder_registry_has_7_known_types(self):
        """After deletion, the block-builder registry should have exactly 7 known types
        (no team_lead, no engineering_manager)."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        all_known = {
            "linear",
            "fanout",
            "synthesize",
            "gate",
            "code",
            "loop",
            "workflow",
            "team_lead",
            "engineering_manager",
        }
        known = {k for k in BLOCK_BUILDER_REGISTRY if k in all_known}
        assert len(known) == 7, (
            f"Expected exactly 7 block-builder types (without team_lead/engineering_manager), "
            f"got {len(known)}: {sorted(known)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. YAML with deleted block types raises validation error
# ═══════════════════════════════════════════════════════════════════════════════

TEAM_LEAD_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst_1
    role: Analyst
    system_prompt: "You analyze failures."
blocks:
  analyze:
    type: team_lead
    soul_ref: analyst
    failure_context_keys:
      - error_log
workflow:
  name: test_team_lead
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

ENGINEERING_MANAGER_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  planner:
    id: planner_1
    role: Planner
    system_prompt: "You plan things."
blocks:
  plan:
    type: engineering_manager
    soul_ref: planner
workflow:
  name: test_em
  entry: plan
  transitions:
    - from: plan
      to: null
"""


class TestYamlValidationErrors:
    """Parsing YAML with deleted block types must raise a validation error."""

    def test_team_lead_yaml_raises_validation_error(self):
        """YAML with ``type: team_lead`` must raise an error during parsing."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        with pytest.raises(Exception) as exc_info:
            parse_workflow_yaml(TEAM_LEAD_YAML)

        error_msg = str(exc_info.value)
        assert "team_lead" in error_msg

    def test_engineering_manager_yaml_raises_validation_error(self):
        """YAML with ``type: engineering_manager`` must raise an error during parsing."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        with pytest.raises(Exception) as exc_info:
            parse_workflow_yaml(ENGINEERING_MANAGER_YAML)

        error_msg = str(exc_info.value)
        assert "engineering_manager" in error_msg


# ═══════════════════════════════════════════════════════════════════════════════
# 6. engineering_manager removed from BUILT_IN_SOULS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuiltInSoulsCleanup:
    """The engineering_manager entry must be removed from BUILT_IN_SOULS in parser.py."""

    def test_engineering_manager_not_in_built_in_souls(self):
        """'engineering_manager' must not be a key in BUILT_IN_SOULS."""
        from runsight_core.yaml.parser import BUILT_IN_SOULS

        assert "engineering_manager" not in BUILT_IN_SOULS, (
            "'engineering_manager' is still in BUILT_IN_SOULS — it must be removed"
        )

    def test_built_in_souls_still_has_other_entries(self):
        """Other BUILT_IN_SOULS entries (researcher, reviewer, etc.) must remain."""
        from runsight_core.yaml.parser import BUILT_IN_SOULS

        expected_remaining = {
            "researcher",
            "reviewer",
            "coder",
            "architect",
            "synthesizer",
            "generalist",
        }
        for soul_key in expected_remaining:
            assert soul_key in BUILT_IN_SOULS, (
                f"'{soul_key}' was accidentally removed from BUILT_IN_SOULS"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. test_advanced_blocks.py deleted
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdvancedBlocksTestFileDeleted:
    """test_advanced_blocks.py must be deleted (it only tested TeamLead/EM)."""

    def test_advanced_blocks_test_file_does_not_exist(self):
        """tests/test_advanced_blocks.py must be deleted."""
        path = TESTS_DIR / "test_advanced_blocks.py"
        assert not path.exists(), f"{path} still exists on disk — it must be deleted"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. No imports of deleted classes in __init__.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitPyCleanup:
    """runsight_core/__init__.py must not import the deleted block classes."""

    def test_no_team_lead_import_in_init(self):
        """__init__.py must not contain an import of TeamLeadBlock."""
        init_path = BLOCKS_DIR.parent / "__init__.py"
        source = init_path.read_text()
        assert "TeamLeadBlock" not in source, (
            "TeamLeadBlock is still referenced in runsight_core/__init__.py"
        )

    def test_no_engineering_manager_import_in_init(self):
        """__init__.py must not contain an import of EngineeringManagerBlock."""
        init_path = BLOCKS_DIR.parent / "__init__.py"
        source = init_path.read_text()
        assert "EngineeringManagerBlock" not in source, (
            "EngineeringManagerBlock is still referenced in runsight_core/__init__.py"
        )

    def test_no_team_lead_module_import_in_init(self):
        """__init__.py must not import from blocks.team_lead."""
        init_path = BLOCKS_DIR.parent / "__init__.py"
        source = init_path.read_text()
        assert "blocks.team_lead" not in source, (
            "blocks.team_lead is still imported in runsight_core/__init__.py"
        )

    def test_no_engineering_manager_module_import_in_init(self):
        """__init__.py must not import from blocks.engineering_manager."""
        init_path = BLOCKS_DIR.parent / "__init__.py"
        source = init_path.read_text()
        assert "blocks.engineering_manager" not in source, (
            "blocks.engineering_manager is still imported in runsight_core/__init__.py"
        )
