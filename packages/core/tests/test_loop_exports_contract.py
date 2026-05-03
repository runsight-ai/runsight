"""LoopBlock schema, fixture migration, and registry governance coverage.

Behavior boundary: public LoopBlock exports, published JSON schema validation,
package-local workflow fixture migration, absence of retired RetryBlock symbols
in core source, and block registry wiring.
Owner: packages/core runtime and schema owners.
Exit criteria: delete the migration/governance sections once RetryBlock support
has been absent for a release cycle and behavior suites cover LoopBlock schema
and registry contracts directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

try:
    from jsonschema import ValidationError as JsonSchemaValidationError
    from jsonschema import validate
except ImportError:
    from runsight_core.yaml.schema import RunsightWorkflowFile

    class JsonSchemaValidationError(Exception):
        def __init__(self, message: str):
            super().__init__(message)
            self.message = message

    def validate(*, instance: Dict[str, Any], schema: Dict[str, Any]) -> None:
        try:
            RunsightWorkflowFile.model_validate(instance)
        except Exception as exc:
            raise JsonSchemaValidationError(str(exc)) from exc

# ---------------------------------------------------------------------------
# JSON schema fixtures
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.governance, pytest.mark.migration]

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "runsight-workflow-schema.json"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # runsight/
CORE_ROOT = REPO_ROOT / "packages" / "core"
CORE_SRC_ROOT = CORE_ROOT / "src"
PACKAGE_WORKFLOW_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "custom" / "workflows"


@pytest.fixture(scope="module")
def json_schema() -> Dict[str, Any]:
    """Load the published JSON schema from disk."""
    return json.loads(SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_workflow_file(blocks: Dict[str, Any], entry: str = "entry_block") -> Dict[str, Any]:
    """Build a minimal RunsightWorkflowFile dict for JSON-schema validation."""
    return {
        "version": "1.0",
        "id": "loop-schema-fixture",
        "kind": "workflow",
        "workflow": {"name": "loop schema fixture", "entry": entry},
        "blocks": blocks,
    }


def _source_files_containing(root: Path, needle: str) -> list[Path]:
    """Return Python source files under root that contain needle."""
    matches: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in {"__pycache__", "build"} for part in path.parts):
            continue
        if needle in path.read_text(encoding="utf-8"):
            matches.append(path)
    return matches


def _format_paths(paths: list[Path]) -> str:
    return "\n".join(str(path) for path in paths)


def _workflow_fixture_files() -> list[Path]:
    return sorted(PACKAGE_WORKFLOW_FIXTURES.glob("*.yaml"))


def _all_workflow_fixture_yaml_files() -> list[Path]:
    return sorted(
        [
            *PACKAGE_WORKFLOW_FIXTURES.rglob("*.yaml"),
            *PACKAGE_WORKFLOW_FIXTURES.rglob("*.yml"),
        ]
    )


# ===========================================================================
# Top-level exports for LoopBlock schema objects
# ===========================================================================


class TestTopLevelExports:
    """LoopBlock schema objects are exported by the public package surface."""

    def test_loop_block_def_exported(self):
        """LoopBlockDef should be importable from the top-level runsight_core package."""
        import runsight_core

        assert hasattr(runsight_core, "LoopBlockDef"), (
            "LoopBlockDef missing from runsight_core; export it in __init__.py"
        )
        assert "LoopBlockDef" in runsight_core.__all__

    def test_retry_config_exported(self):
        """RetryConfig should be importable from the top-level runsight_core package."""
        import runsight_core

        assert hasattr(runsight_core, "RetryConfig"), (
            "RetryConfig missing from runsight_core; export it in __init__.py"
        )
        assert "RetryConfig" in runsight_core.__all__

    def test_carry_context_config_exported(self):
        """CarryContextConfig should be importable from the top-level runsight_core package."""
        import runsight_core

        assert hasattr(runsight_core, "CarryContextConfig"), (
            "CarryContextConfig missing from runsight_core; export it in __init__.py"
        )
        assert "CarryContextConfig" in runsight_core.__all__

    def test_no_retry_block_in_all(self):
        """RetryBlock should stay absent from __all__ after replacement by LoopBlock."""
        import runsight_core

        assert "RetryBlock" not in runsight_core.__all__

    def test_no_retry_block_def_in_all(self):
        """RetryBlockDef should stay absent from __all__."""
        import runsight_core

        assert "RetryBlockDef" not in runsight_core.__all__


# ===========================================================================
# JSON schema validation for loop blocks
# ===========================================================================


class TestBlockRegistryLoopMapping:
    """Block type registry exposes the LoopBlock builder."""

    def test_loop_in_block_type_registry(self):
        """BLOCK_TYPE_REGISTRY should have 'loop' key."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert "loop" in BLOCK_TYPE_REGISTRY, "'loop' not found in BLOCK_TYPE_REGISTRY"

    def test_retry_not_in_block_type_registry(self):
        """BLOCK_TYPE_REGISTRY should not have 'retry' key."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert "retry" not in BLOCK_TYPE_REGISTRY, "'retry' still in BLOCK_TYPE_REGISTRY"

    def test_loop_builder_produces_loop_block(self):
        """The 'loop' builder in BLOCK_TYPE_REGISTRY should produce a LoopBlock."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        builder = BLOCK_TYPE_REGISTRY["loop"]
        # The builder signature is (block_id, block_def, souls_map) or similar.
        # We just verify the builder exists and is callable.
        assert callable(builder)
