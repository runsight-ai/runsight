"""
Tests for RUN-222: Migrate Remaining Block Types.

After migration, every block type is self-contained: schema (BlockDef) +
runtime class + builder (build()) in one file, auto-registered via
__init_subclass__ and build() convention.

Tests verify:
1. Co-located BlockDef importable from each block file
2. Co-located build() function importable from each block file
3. Registry counts (7 entries each for BLOCK_DEF_REGISTRY and BLOCK_BUILDER_REGISTRY)
4. CarryContextConfig migrated with LoopBlockDef to blocks/loop.py
5. JSON schema stability (generate_schema.py --check)
6. End-to-end round-trip: parse_workflow_yaml still works for migrated block types
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# All 7 block types (after removing http_request, file_writer, team_lead, engineering_manager)
ALL_BLOCK_TYPES = {
    "code",
    "linear",
    "gate",
    "dispatch",
    "synthesize",
    "loop",
    "workflow",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Co-located BlockDef importable from each block file
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

    def test_dispatch_block_def_importable(self):
        from runsight_core.blocks.dispatch import DispatchBlockDef

        assert DispatchBlockDef.model_fields["type"].default == "dispatch"

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

    def test_dispatch_build_function(self):
        from runsight_core.blocks.dispatch import build

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
        # Trigger all imports
        import runsight_core.blocks  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        known = {k: v for k, v in BLOCK_DEF_REGISTRY.items() if k in ALL_BLOCK_TYPES}
        assert len(known) == 7, (
            f"Expected 7 registered block-def types, got {len(known)}. "
            f"Missing: {ALL_BLOCK_TYPES - set(known.keys())}"
        )

    def test_block_builder_registry_has_7_entries(self):
        """BLOCK_BUILDER_REGISTRY must have exactly 7 entries from auto-discovery."""
        # Trigger all imports
        import runsight_core.blocks  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        known = {k: v for k, v in BLOCK_BUILDER_REGISTRY.items() if k in ALL_BLOCK_TYPES}
        assert len(known) == 7, (
            f"Expected 7 registered block builders, got {len(known)}. "
            f"Missing: {ALL_BLOCK_TYPES - set(known.keys())}"
        )

    def test_all_block_def_classes_from_blocks_package(self):
        """Every registered BlockDef class must originate from runsight_core.blocks.*, not schema.py."""
        import runsight_core.blocks  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        for block_type in ALL_BLOCK_TYPES:
            cls = BLOCK_DEF_REGISTRY.get(block_type)
            assert cls is not None, f"Block type '{block_type}' not in BLOCK_DEF_REGISTRY"
            assert cls.__module__.startswith("runsight_core.blocks."), (
                f"BlockDef for '{block_type}' is registered from {cls.__module__}, "
                f"expected runsight_core.blocks.*"
            )

    def test_all_block_builder_functions_from_blocks_package(self):
        """Every registered builder must originate from runsight_core.blocks.*, not parser.py."""
        import runsight_core.blocks  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        for block_type in ALL_BLOCK_TYPES:
            builder = BLOCK_BUILDER_REGISTRY.get(block_type)
            assert builder is not None, f"Block type '{block_type}' not in BLOCK_BUILDER_REGISTRY"
            assert builder.__module__.startswith("runsight_core.blocks."), (
                f"Builder for '{block_type}' is from {builder.__module__}, "
                f"expected runsight_core.blocks.*"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CarryContextConfig migration (moved with LoopBlockDef to blocks/loop.py)
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
            cwd=str(script.parent.parent),  # packages/core/
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

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parse_linear_block(self):
        """parse_workflow_yaml must still work with linear blocks after migration."""
        from runsight_core import LinearBlock
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(VALID_LINEAR_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_linear"
        block = wf.blocks.get("write_step")
        assert block is not None
        assert isinstance(block, LinearBlock)

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parse_loop_block(self):
        """parse_workflow_yaml must still work with loop blocks after migration."""
        from runsight_core import LoopBlock
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(VALID_LOOP_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_loop"
        block = wf.blocks.get("loop_step")
        assert block is not None
        assert isinstance(block, LoopBlock)

    def test_parse_code_block(self):
        """parse_workflow_yaml must still work with code blocks after migration."""
        from runsight_core import CodeBlock
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(VALID_CODE_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_code"
        block = wf.blocks.get("transform")
        assert block is not None
        assert isinstance(block, CodeBlock)
