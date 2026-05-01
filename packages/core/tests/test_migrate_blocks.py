"""Block schema, builder registry, and parser round-trip contracts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from workflow_fixture_helpers import workflow_fixture_text

_SAFE_SUBPROCESS_ENV_KEYS = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PYTHONIOENCODING",
    "TMP",
    "TMPDIR",
    "TEMP",
    "VIRTUAL_ENV",
)


def _schema_check_env(repo_root: Path) -> dict[str, str]:
    """Build a schema-check subprocess env without inheriting real credentials."""
    env = {key: os.environ[key] for key in _SAFE_SUBPROCESS_ENV_KEYS if key in os.environ}
    pythonpath = [
        str(repo_root / "packages" / "core" / "src"),
        str(repo_root / "apps" / "api" / "src"),
    ]
    if os.environ.get("PYTHONPATH"):
        pythonpath.append(os.environ["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return env


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
# Co-located BlockDef imports
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
# Co-located build() functions
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
# Registry counts for migrated block types
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryCounts:
    """Migrated block types are auto-registered without hardcoded parser entries."""

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
# CarryContextConfig loop-module ownership
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
        """schema.py should preserve the legacy CarryContextConfig import path."""
        from runsight_core.blocks.loop import CarryContextConfig  # noqa: F401


# ═══════════════════════════════════════════════════════════════════════════════
# JSON schema stability (generate_schema.py --check)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateSchemaCheck:
    """Verify generate_schema.py --check passes for migrated block schemas."""

    def test_generate_schema_check_passes(self):
        """Running `python generate_schema.py --check` must exit 0."""
        import subprocess

        script = Path(__file__).resolve().parent.parent / "scripts" / "generate_schema.py"
        # Build an absolute PYTHONPATH so the subprocess resolves the same
        # source tree even when CWD differs from the test-runner root.
        repo_root = script.resolve().parent.parent.parent.parent
        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True,
            text=True,
            cwd=str(script.parent.parent),  # packages/core/
            env=_schema_check_env(repo_root),
        )
        assert result.returncode == 0, (
            f"generate_schema.py --check failed (exit {result.returncode}).\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Parser round-trips for migrated block types
# ═══════════════════════════════════════════════════════════════════════════════


class TestMigratedBlockRoundTripIntegration:
    """Integration: parse YAML with migrated block types, verify correct runtime blocks."""

    def test_parse_linear_block(self):
        """parse_workflow_yaml must work with linear blocks."""
        from runsight_core import LinearBlock
        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(workflow_fixture_text("migrated-linear-block-roundtrip.yaml"))
        assert isinstance(wf, Workflow)
        assert wf.name == "linear_roundtrip_workflow"
        block = wf.blocks.get("write_step")
        assert block is not None
        assert isinstance(block, IsolatedBlockWrapper)
        assert isinstance(block.inner_block, LinearBlock)

    def test_parse_loop_block(self):
        """parse_workflow_yaml must work with loop blocks."""
        from runsight_core import LoopBlock
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(workflow_fixture_text("migrated-loop-block-roundtrip.yaml"))
        assert isinstance(wf, Workflow)
        assert wf.name == "loop_roundtrip_workflow"
        block = wf.blocks.get("loop_step")
        assert block is not None
        assert isinstance(block, LoopBlock)

    def test_parse_code_block(self):
        """parse_workflow_yaml must work with code blocks."""
        from runsight_core import CodeBlock
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(workflow_fixture_text("migrated-code-block-roundtrip.yaml"))
        assert isinstance(wf, Workflow)
        assert wf.name == "code_roundtrip_workflow"
        block = wf.blocks.get("transform")
        assert block is not None
        assert isinstance(block, CodeBlock)
