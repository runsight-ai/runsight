"""
Failing tests for RUN-223: Remove Legacy Hardcoded Maps.

After this cleanup, the codebase has a single source of truth for block type
metadata — all legacy backward-compatibility constants, aliases, and
re-export files have been removed.

Tests verify:
1. parser.py has no BLOCK_TYPE_REGISTRY constant
2. parser.py has no BlockBuilder type alias
3. parser.py has no _build_linear backward-compat alias
4. implementations.py is deleted entirely
5. No production code imports from implementations.py
6. schema.py has no _BLOCK_DEF_REEXPORTS lazy re-export map
7. schema.py has no __getattr__ function for lazy re-exports
8. __init__.py does not import from implementations.py

Expected failures (current state):
- parser.py still has BLOCK_TYPE_REGISTRY, BlockBuilder, _build_linear
- implementations.py still exists with 33 lines of re-exports
- Many source files still import from implementations.py
- schema.py still has _BLOCK_DEF_REEXPORTS and __getattr__
"""

from __future__ import annotations

import re
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

CORE_SRC = Path(__file__).resolve().parent.parent / "src" / "runsight_core"
BLOCKS_DIR = CORE_SRC / "blocks"
YAML_DIR = CORE_SRC / "yaml"
PARSER_PATH = YAML_DIR / "parser.py"
SCHEMA_PATH = YAML_DIR / "schema.py"
IMPLEMENTATIONS_PATH = BLOCKS_DIR / "implementations.py"
INIT_PATH = CORE_SRC / "__init__.py"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. parser.py — legacy constants and aliases removed
# ═══════════════════════════════════════════════════════════════════════════════


class TestParserCleanup:
    """parser.py should have no backward-compat constants or aliases."""

    def test_no_block_type_registry_constant(self):
        """parser.py should not define or export BLOCK_TYPE_REGISTRY."""
        import runsight_core.yaml.parser as parser_mod

        assert not hasattr(parser_mod, "BLOCK_TYPE_REGISTRY"), (
            "BLOCK_TYPE_REGISTRY still exists on parser module — "
            "should be removed (callers use BLOCK_BUILDER_REGISTRY directly)"
        )

    def test_no_block_type_registry_in_source(self):
        """parser.py source should not contain 'BLOCK_TYPE_REGISTRY'."""
        source = PARSER_PATH.read_text()
        assert "BLOCK_TYPE_REGISTRY" not in source, (
            "parser.py still references BLOCK_TYPE_REGISTRY in source code"
        )

    def test_no_block_builder_type_alias(self):
        """parser.py should not define the BlockBuilder type alias."""
        source = PARSER_PATH.read_text()
        # Match 'BlockBuilder =' at module level (a type alias definition)
        assert not re.search(r"^BlockBuilder\s*=", source, re.MULTILINE), (
            "parser.py still defines BlockBuilder type alias — "
            "this is unused legacy and should be removed"
        )

    def test_no_block_builder_attribute(self):
        """parser module should not export BlockBuilder."""
        import runsight_core.yaml.parser as parser_mod

        assert not hasattr(parser_mod, "BlockBuilder"), "BlockBuilder still exists on parser module"

    def test_no_build_linear_alias(self):
        """parser.py should not import _build_linear backward-compat alias."""
        source = PARSER_PATH.read_text()
        assert "_build_linear" not in source, (
            "parser.py still references _build_linear — "
            "this backward-compat alias should be removed"
        )

    def test_no_build_linear_attribute(self):
        """parser module should not export _build_linear."""
        import runsight_core.yaml.parser as parser_mod

        assert not hasattr(parser_mod, "_build_linear"), (
            "_build_linear still exists on parser module"
        )

    def test_no_backward_compat_bbr_import(self):
        """parser.py should not import BLOCK_BUILDER_REGISTRY as _bbr for
        building the legacy BLOCK_TYPE_REGISTRY."""
        source = PARSER_PATH.read_text()
        assert "_bbr" not in source, (
            "parser.py still imports BLOCK_BUILDER_REGISTRY as _bbr "
            "for backward-compat BLOCK_TYPE_REGISTRY construction"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. implementations.py — file deleted entirely
# ═══════════════════════════════════════════════════════════════════════════════


class TestImplementationsFileDeleted:
    """implementations.py should be deleted — all blocks live in their own modules."""

    def test_implementations_file_does_not_exist(self):
        """blocks/implementations.py should be deleted."""
        assert not IMPLEMENTATIONS_PATH.exists(), (
            f"implementations.py still exists at {IMPLEMENTATIONS_PATH} — "
            "it should be deleted (all blocks live in their own modules)"
        )

    def test_no_implementations_import_in_init(self):
        """__init__.py should not import from implementations.py."""
        source = INIT_PATH.read_text()
        assert "implementations" not in source, (
            "__init__.py still imports from .blocks.implementations — "
            "should import directly from individual block modules"
        )

    def test_no_implementations_import_in_production_code(self):
        """No production source code (non-test) should import from implementations.py.

        Test files are excluded — they will be updated separately or
        the re-export file will be replaced by direct imports.
        """
        # Scan all .py files under src/ (production code only)
        production_files = list(CORE_SRC.rglob("*.py"))
        violations = []
        for py_file in production_files:
            source = py_file.read_text()
            if "implementations" in source:
                # Check for actual import patterns
                if (
                    re.search(
                        r"from\s+runsight_core\.blocks\.implementations\s+import",
                        source,
                    )
                    or re.search(
                        r"import\s+runsight_core\.blocks\.implementations",
                        source,
                    )
                    or re.search(
                        r"from\s+\.blocks\.implementations\s+import",
                        source,
                    )
                    or re.search(
                        r"from\s+\.implementations\s+import",
                        source,
                    )
                ):
                    violations.append(str(py_file.relative_to(CORE_SRC)))

        assert not violations, (
            "Production code still imports from implementations.py:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. schema.py — lazy re-export map removed
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaCleanup:
    """schema.py should not have the _BLOCK_DEF_REEXPORTS lazy import map."""

    def test_no_block_def_reexports_constant(self):
        """schema.py should not define _BLOCK_DEF_REEXPORTS."""
        source = SCHEMA_PATH.read_text()
        assert "_BLOCK_DEF_REEXPORTS" not in source, (
            "schema.py still contains _BLOCK_DEF_REEXPORTS — "
            "callers should import BlockDef subclasses directly from block modules"
        )

    def test_no_getattr_function(self):
        """schema.py should not define a module-level __getattr__ for lazy re-exports."""
        source = SCHEMA_PATH.read_text()
        assert not re.search(r"^def __getattr__\(", source, re.MULTILINE), (
            "schema.py still defines __getattr__ — lazy re-exports should be removed"
        )

    def test_dynamic_union_still_works(self):
        """The dynamic BlockDef union (build_block_def_union) should still exist
        and be the ONLY way to get BlockDef."""
        from runsight_core.yaml.schema import build_block_def_union, rebuild_block_def_union

        # These should still be importable
        assert callable(build_block_def_union)
        assert callable(rebuild_block_def_union)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Functional verification — everything still works after cleanup
# ═══════════════════════════════════════════════════════════════════════════════


class TestFunctionalAfterCleanup:
    """Core functionality should be unaffected by the cleanup."""

    def test_parse_workflow_still_works(self):
        """parse_workflow_yaml still works after removing legacy artifacts."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """
version: "1.0"
souls:
  analyst:
    id: analyst_1
    role: Analyst
    system_prompt: "You analyze data."
blocks:
  step1:
    type: linear
    soul_ref: analyst
workflow:
  name: test
  entry: step1
  transitions: []
"""
        wf = parse_workflow_yaml(yaml_str)
        assert wf.name == "test"

    def test_block_classes_importable_from_own_modules(self):
        """All block classes should be importable directly from their own modules."""
        from runsight_core.blocks.code import CodeBlock
        from runsight_core.blocks.fanout import FanOutBlock
        from runsight_core.blocks.gate import GateBlock
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.blocks.loop import LoopBlock
        from runsight_core.blocks.synthesize import SynthesizeBlock
        from runsight_core.blocks.workflow_block import WorkflowBlock

        # Verify they are actual classes
        assert callable(LinearBlock)
        assert callable(FanOutBlock)
        assert callable(SynthesizeBlock)
        assert callable(LoopBlock)
        assert callable(GateBlock)
        assert callable(CodeBlock)
        assert callable(WorkflowBlock)

    def test_block_classes_importable_from_package_init(self):
        """All block classes should be importable from runsight_core top-level
        (but NOT via implementations.py)."""
        import runsight_core

        # These should all be accessible
        assert hasattr(runsight_core, "LinearBlock")
        assert hasattr(runsight_core, "FanOutBlock")
        assert hasattr(runsight_core, "SynthesizeBlock")
        assert hasattr(runsight_core, "LoopBlock")
        assert hasattr(runsight_core, "GateBlock")
        assert hasattr(runsight_core, "CodeBlock")
        assert hasattr(runsight_core, "WorkflowBlock")

    def test_registry_still_has_all_block_types(self):
        """The auto-registration path should still discover all block types."""
        import runsight_core.blocks  # trigger auto-discovery  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY, get_all_block_types

        block_types = get_all_block_types()
        expected_types = {
            "linear",
            "fanout",
            "synthesize",
            "loop",
            "gate",
            "code",
            "workflow",
        }

        for t in expected_types:
            assert t in block_types, f"Block type '{t}' missing from BLOCK_DEF_REGISTRY"
            assert t in BLOCK_BUILDER_REGISTRY, (
                f"Block type '{t}' missing from BLOCK_BUILDER_REGISTRY"
            )
