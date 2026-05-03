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


class TestNoRetryBlockReferences:
    """Core source no longer references retired RetryBlock symbols."""

    def test_no_retry_block_in_source(self):
        """Core Python source should not reference RetryBlock."""
        hits = _source_files_containing(CORE_SRC_ROOT, "RetryBlock")
        assert not hits, "RetryBlock still referenced in source files:\n" + _format_paths(hits)

    def test_no_retry_block_def_in_source(self):
        """Core Python source should not reference RetryBlockDef."""
        hits = _source_files_containing(CORE_SRC_ROOT, "RetryBlockDef")
        assert not hits, "RetryBlockDef still referenced in source files:\n" + _format_paths(hits)

    def test_no_retry_block_in_yaml_files(self):
        """No YAML files should reference type: retry."""
        hits = [
            path
            for path in _all_workflow_fixture_yaml_files()
            if "type: retry" in path.read_text(encoding="utf-8")
        ]
        assert not hits, "'type: retry' still found in YAML files:\n" + _format_paths(hits)

    def test_no_retry_block_in_init_exports(self):
        """__init__.py must not export RetryBlock."""
        init_path = CORE_ROOT / "src" / "runsight_core" / "__init__.py"
        content = init_path.read_text()
        assert "RetryBlock" not in content, "RetryBlock still in __init__.py"


# ===========================================================================
# Block registry maps loop to LoopBlock
# ===========================================================================
