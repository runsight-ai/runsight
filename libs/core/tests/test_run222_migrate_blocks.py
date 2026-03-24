"""
Failing tests for RUN-222: Migrate Remaining 11 Block Types.

After this migration, every block type is self-contained: schema (BlockDef) +
runtime class + builder (build()) in one file, auto-registered via
__init_subclass__ and build() convention.

Tests verify:
1. Block file existence for all 11 blocks
2. Co-located BlockDef importable from each block file
3. Co-located build() function importable from each block file
4. Registry counts (12 entries each for BLOCK_DEF_REGISTRY and BLOCK_BUILDER_REGISTRY)
5. schema.py has zero per-type BlockDef classes
6. parser.py has zero _build_* functions and empty BLOCK_TYPE_REGISTRY
7. CarryContextConfig migrated with LoopBlockDef to blocks/loop.py
8. JSON schema stability (generate_schema.py --check)
9. End-to-end round-trip: parse_workflow_yaml still works for migrated block types

Expected failures (current state):
- Block files do not exist yet (only http_request.py exists)
- BlockDef classes are still in schema.py
- _build_* functions are still in parser.py
- BLOCK_TYPE_REGISTRY in parser.py still has 10 entries
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

BLOCKS_DIR = Path(__file__).resolve().parent.parent / "src" / "runsight_core" / "blocks"

# All 11 blocks to migrate (module_name, type_name, BlockDef class name)
BLOCKS_TO_MIGRATE = [
    ("code", "code", "CodeBlockDef"),
    ("linear", "linear", "LinearBlockDef"),
    ("gate", "gate", "GateBlockDef"),
    ("fanout", "fanout", "FanOutBlockDef"),
    ("synthesize", "synthesize", "SynthesizeBlockDef"),
    ("loop", "loop", "LoopBlockDef"),
    ("workflow_block", "workflow", "WorkflowBlockDef"),
]

# All 7 block types (after removing http_request, file_writer, team_lead, engineering_manager)
ALL_BLOCK_TYPES = {
    "code",
    "linear",
    "gate",
    "fanout",
    "synthesize",
    "loop",
    "workflow",
}

# Per-type BlockDef class names that must be removed from schema.py
PER_TYPE_BLOCK_DEF_NAMES = [
    "LinearBlockDef",
    "FanOutBlockDef",
    "SynthesizeBlockDef",
    "GateBlockDef",
    "CodeBlockDef",
    "LoopBlockDef",
    "WorkflowBlockDef",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Block file existence tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockFileExistence:
    """Verify that each of the 11 block files exists in blocks/."""

    @pytest.mark.parametrize(
        "module_name",
        [m for m, _, _ in BLOCKS_TO_MIGRATE],
        ids=[m for m, _, _ in BLOCKS_TO_MIGRATE],
    )
    def test_block_file_exists(self, module_name: str):
        """blocks/{module_name}.py must exist."""
        path = BLOCKS_DIR / f"{module_name}.py"
        assert path.exists(), (
            f"Block file {path} does not exist. Create it as part of the migration."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Co-located BlockDef importable from each block file
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockDefImportable:
    """Verify each BlockDef class is importable from its block file."""

    def test_code_block_def_importable(self):
        from runsight_core.blocks.code import CodeBlockDef

        assert CodeBlockDef.model_fields["type"].default == "code"

    def test_linear_block_def_importable(self):
        from runsight_core.blocks.linear import LinearBlockDef

        assert LinearBlockDef.model_fields["type"].default == "linear"

    def test_gate_block_def_importable(self):
        from runsight_core.blocks.gate import GateBlockDef

        assert GateBlockDef.model_fields["type"].default == "gate"

    def test_fanout_block_def_importable(self):
        from runsight_core.blocks.fanout import FanOutBlockDef

        assert FanOutBlockDef.model_fields["type"].default == "fanout"

    def test_synthesize_block_def_importable(self):
        from runsight_core.blocks.synthesize import SynthesizeBlockDef

        assert SynthesizeBlockDef.model_fields["type"].default == "synthesize"

    def test_loop_block_def_importable(self):
        from runsight_core.blocks.loop import LoopBlockDef

        assert LoopBlockDef.model_fields["type"].default == "loop"

    def test_workflow_block_def_importable(self):
        from runsight_core.blocks.workflow_block import WorkflowBlockDef

        assert WorkflowBlockDef.model_fields["type"].default == "workflow"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Co-located build() function importable from each block file
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildFunctionExists:
    """Verify each block file exports a callable build() function."""

    def test_code_build_function(self):
        from runsight_core.blocks.code import build

        assert callable(build)

    def test_linear_build_function(self):
        from runsight_core.blocks.linear import build

        assert callable(build)

    def test_gate_build_function(self):
        from runsight_core.blocks.gate import build

        assert callable(build)

    def test_fanout_build_function(self):
        from runsight_core.blocks.fanout import build

        assert callable(build)

    def test_synthesize_build_function(self):
        from runsight_core.blocks.synthesize import build

        assert callable(build)

    def test_loop_build_function(self):
        from runsight_core.blocks.loop import build

        assert callable(build)

    def test_workflow_block_build_function(self):
        from runsight_core.blocks.workflow_block import build

        assert callable(build)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Registry counts — all 12 types auto-registered
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryCounts:
    """After full migration, all 12 types are auto-registered (no hardcoded entries)."""

    def test_block_def_registry_has_7_entries(self):
        """BLOCK_DEF_REGISTRY must have exactly 7 entries from auto-discovery."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        # Trigger all imports
        import runsight_core.blocks  # noqa: F401

        known = {k: v for k, v in BLOCK_DEF_REGISTRY.items() if k in ALL_BLOCK_TYPES}
        assert len(known) == 7, (
            f"Expected 7 registered block-def types, got {len(known)}. "
            f"Missing: {ALL_BLOCK_TYPES - set(known.keys())}"
        )

    def test_block_builder_registry_has_7_entries(self):
        """BLOCK_BUILDER_REGISTRY must have exactly 7 entries from auto-discovery."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        # Trigger all imports
        import runsight_core.blocks  # noqa: F401

        known = {k: v for k, v in BLOCK_BUILDER_REGISTRY.items() if k in ALL_BLOCK_TYPES}
        assert len(known) == 7, (
            f"Expected 7 registered block builders, got {len(known)}. "
            f"Missing: {ALL_BLOCK_TYPES - set(known.keys())}"
        )

    def test_all_block_def_classes_from_blocks_package(self):
        """Every registered BlockDef class must originate from runsight_core.blocks.*, not schema.py."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        import runsight_core.blocks  # noqa: F401

        for block_type in ALL_BLOCK_TYPES:
            cls = BLOCK_DEF_REGISTRY.get(block_type)
            assert cls is not None, f"Block type '{block_type}' not in BLOCK_DEF_REGISTRY"
            assert cls.__module__.startswith("runsight_core.blocks."), (
                f"BlockDef for '{block_type}' is registered from {cls.__module__}, "
                f"expected runsight_core.blocks.*"
            )

    def test_all_block_builder_functions_from_blocks_package(self):
        """Every registered builder must originate from runsight_core.blocks.*, not parser.py."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        import runsight_core.blocks  # noqa: F401

        for block_type in ALL_BLOCK_TYPES:
            builder = BLOCK_BUILDER_REGISTRY.get(block_type)
            assert builder is not None, f"Block type '{block_type}' not in BLOCK_BUILDER_REGISTRY"
            assert builder.__module__.startswith("runsight_core.blocks."), (
                f"Builder for '{block_type}' is from {builder.__module__}, "
                f"expected runsight_core.blocks.*"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. schema.py cleanup — zero per-type BlockDef classes
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaCleanup:
    """Verify schema.py no longer has per-type BlockDef classes."""

    def test_schema_has_no_per_type_block_defs(self):
        """schema.py source must not define any per-type BlockDef classes."""
        import runsight_core.yaml.schema as schema_mod

        source = inspect.getsource(schema_mod)
        for name in PER_TYPE_BLOCK_DEF_NAMES:
            assert f"class {name}" not in source, (
                f"{name} class definition is still in schema.py — "
                f"it must be moved to its block file"
            )

    def test_schema_has_no_carry_context_config(self):
        """CarryContextConfig must be moved out of schema.py (to blocks/loop.py)."""
        import runsight_core.yaml.schema as schema_mod

        source = inspect.getsource(schema_mod)
        assert "class CarryContextConfig" not in source, (
            "CarryContextConfig class definition is still in schema.py — "
            "it must be moved to blocks/loop.py"
        )

    def test_hardcoded_block_def_union_removed(self):
        """The hardcoded BlockDef union listing per-type classes must be removed.

        After migration, BlockDef should be built dynamically from the registry.
        """
        import runsight_core.yaml.schema as schema_mod

        source = inspect.getsource(schema_mod)

        # The old hardcoded union had lines like:
        #   BlockDef = Annotated[
        #       Union[
        #           LinearBlockDef,
        #           FanOutBlockDef, ...
        # Extract just the BlockDef = Annotated[...] definition by tracking
        # bracket depth. The closing structure spans multiple lines:
        #     ],
        #     Field(discriminator="type"),
        # ]
        lines = source.split("\n")
        union_lines: list[str] = []
        depth = 0
        in_union = False
        for line in lines:
            if "BlockDef = Annotated[" in line:
                in_union = True
            if in_union:
                union_lines.append(line)
                depth += line.count("[") - line.count("]")
                if depth <= 0:
                    break

        union_text = "\n".join(union_lines)
        for name in PER_TYPE_BLOCK_DEF_NAMES:
            assert name not in union_text, (
                f"{name} is still in the hardcoded BlockDef union in schema.py — "
                f"the union should be built dynamically from the registry"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. parser.py cleanup — zero _build_* functions, empty BLOCK_TYPE_REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════


class TestParserCleanup:
    """Verify parser.py no longer has _build_* functions or hardcoded registry."""

    def test_parser_has_no_build_functions(self):
        """parser.py source must not define any _build_* functions."""
        import runsight_core.yaml.parser as parser_mod

        source = inspect.getsource(parser_mod)
        build_funcs = [
            line.strip() for line in source.split("\n") if line.strip().startswith("def _build_")
        ]
        assert build_funcs == [], f"parser.py still has _build_* functions: {build_funcs}"

    def test_parser_block_type_registry_empty_or_absent(self):
        """BLOCK_TYPE_REGISTRY in parser.py must be empty or removed."""
        import runsight_core.yaml.parser as parser_mod

        # If BLOCK_TYPE_REGISTRY is still present, it must be empty
        if hasattr(parser_mod, "BLOCK_TYPE_REGISTRY"):
            registry = parser_mod.BLOCK_TYPE_REGISTRY
            # It should only contain auto-discovered entries (from BLOCK_BUILDER_REGISTRY),
            # not hardcoded _build_* functions
            for key, val in registry.items():
                assert not val.__name__.startswith("_build_"), (
                    f"BLOCK_TYPE_REGISTRY['{key}'] still points to hardcoded "
                    f"function {val.__name__} — it should use auto-discovered builders"
                )

    def test_parser_no_block_runtime_imports(self):
        """parser.py must not import runtime block classes from implementations.py.

        After migration, the parser delegates to BLOCK_BUILDER_REGISTRY, so it
        no longer needs to import LinearBlock, FanOutBlock, etc.
        """
        import runsight_core.yaml.parser as parser_mod

        source = inspect.getsource(parser_mod)

        # The parser must not import from implementations at all
        assert "from runsight_core import" not in source, (
            "parser.py still imports from runsight_core.blocks.implementations — "
            "after migration, the parser should delegate to BLOCK_BUILDER_REGISTRY"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CarryContextConfig migration (moved with LoopBlockDef to blocks/loop.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCarryContextConfigMigration:
    """Verify CarryContextConfig is importable from blocks/loop.py."""

    def test_carry_context_config_in_loop_module(self):
        """CarryContextConfig must be importable from runsight_core.blocks.loop."""
        from runsight_core.blocks.loop import CarryContextConfig

        assert CarryContextConfig is not None

    def test_carry_context_config_has_expected_fields(self):
        """CarryContextConfig must have the same fields as the original."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig()
        assert config.enabled is True
        assert config.mode == "last"
        assert config.source_blocks is None
        assert config.inject_as == "previous_round_context"

    def test_carry_context_config_re_exported_from_schema(self):
        """schema.py should re-export CarryContextConfig for backward compatibility."""
        from runsight_core.blocks.loop import CarryContextConfig  # noqa: F401


# ═══════════════════════════════════════════════════════════════════════════════
# 8. JSON schema stability (generate_schema.py --check)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateSchemaCheck:
    """Verify generate_schema.py --check passes after migration."""

    def test_generate_schema_check_passes(self):
        """Running `python generate_schema.py --check` must exit 0 after migration."""
        import subprocess

        script = Path(__file__).resolve().parent.parent / "scripts" / "generate_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True,
            text=True,
            cwd=str(script.parent.parent),  # libs/core/
        )
        assert result.returncode == 0, (
            f"generate_schema.py --check failed (exit {result.returncode}).\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. End-to-end round-trip: parse_workflow_yaml still works
# ═══════════════════════════════════════════════════════════════════════════════

VALID_LINEAR_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  writer:
    id: writer_1
    role: Writer
    system_prompt: "You are a writer."
blocks:
  write_step:
    type: linear
    soul_ref: writer
workflow:
  name: test_linear
  entry: write_step
  transitions:
    - from: write_step
      to: null
"""

VALID_LOOP_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  worker:
    id: worker_1
    role: Worker
    system_prompt: "You are a worker."
blocks:
  task_step:
    type: linear
    soul_ref: worker
  loop_step:
    type: loop
    inner_block_refs:
      - task_step
    max_rounds: 3
workflow:
  name: test_loop
  entry: loop_step
  transitions:
    - from: loop_step
      to: null
"""

VALID_CODE_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  transform:
    type: code
    code: |
      def main(input_data):
          return {"result": input_data.get("value", 0) * 2}
    timeout_seconds: 10
workflow:
  name: test_code
  entry: transform
  transitions:
    - from: transform
      to: null
"""


class TestEndToEndRoundTrip:
    """Integration: parse YAML with migrated block types, verify correct runtime blocks."""

    def test_parse_linear_block(self):
        """parse_workflow_yaml must still work with linear blocks after migration."""
        from runsight_core import LinearBlock
        from runsight_core.yaml.parser import parse_workflow_yaml
        from runsight_core.workflow import Workflow

        wf = parse_workflow_yaml(VALID_LINEAR_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_linear"
        block = wf.blocks.get("write_step")
        assert block is not None
        assert isinstance(block, LinearBlock)

    def test_parse_loop_block(self):
        """parse_workflow_yaml must still work with loop blocks after migration."""
        from runsight_core import LoopBlock
        from runsight_core.yaml.parser import parse_workflow_yaml
        from runsight_core.workflow import Workflow

        wf = parse_workflow_yaml(VALID_LOOP_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_loop"
        block = wf.blocks.get("loop_step")
        assert block is not None
        assert isinstance(block, LoopBlock)

    def test_parse_code_block(self):
        """parse_workflow_yaml must still work with code blocks after migration."""
        from runsight_core import CodeBlock
        from runsight_core.yaml.parser import parse_workflow_yaml
        from runsight_core.workflow import Workflow

        wf = parse_workflow_yaml(VALID_CODE_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_code"
        block = wf.blocks.get("transform")
        assert block is not None
        assert isinstance(block, CodeBlock)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Backward-compatible re-exports from schema.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaReExports:
    """After RUN-223 cleanup, schema.py no longer re-exports BlockDef classes.
    Classes are importable directly from their own block modules."""

    @pytest.mark.parametrize(
        "module_name,type_name,class_name",
        BLOCKS_TO_MIGRATE,
        ids=[m for m, _, _ in BLOCKS_TO_MIGRATE],
    )
    def test_block_def_re_exported_from_schema(
        self, module_name: str, type_name: str, class_name: str
    ):
        """BlockDef classes must be importable from their own block modules."""
        import importlib

        blocks_mod = importlib.import_module(f"runsight_core.blocks.{module_name}")
        cls = getattr(blocks_mod, class_name, None)
        assert cls is not None, (
            f"{class_name} is not accessible from runsight_core.blocks.{module_name}"
        )

    @pytest.mark.parametrize(
        "module_name,type_name,class_name",
        BLOCKS_TO_MIGRATE,
        ids=[m for m, _, _ in BLOCKS_TO_MIGRATE],
    )
    def test_re_exported_class_is_same_as_blocks_class(
        self, module_name: str, type_name: str, class_name: str
    ):
        """The class from the block module should be a proper BaseBlockDef subclass."""
        import importlib
        from runsight_core.yaml.schema import BaseBlockDef

        blocks_mod = importlib.import_module(f"runsight_core.blocks.{module_name}")
        blocks_cls = getattr(blocks_mod, class_name)

        assert issubclass(blocks_cls, BaseBlockDef), (
            f"{class_name} from blocks/{module_name}.py is not a BaseBlockDef subclass"
        )
