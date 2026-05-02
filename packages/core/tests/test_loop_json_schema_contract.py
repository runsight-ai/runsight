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


class TestJsonSchemaLoopBlock:
    """Published JSON schema validates loop blocks with inner block refs."""

    def test_valid_loop_block_passes(self, json_schema):
        """A well-formed loop block with inner_block_refs should validate."""
        doc = _minimal_workflow_file(
            {
                "entry_block": {
                    "type": "loop",
                    "inner_block_refs": ["collect_step", "review_step"],
                }
            },
        )
        validate(instance=doc, schema=json_schema)

    def test_loop_block_without_inner_block_refs_fails(self, json_schema):
        """A loop block missing inner_block_refs must be rejected by JSON schema."""
        doc = _minimal_workflow_file(
            {"entry_block": {"type": "loop"}},
        )
        with pytest.raises(JsonSchemaValidationError):
            validate(instance=doc, schema=json_schema)

    def test_loop_block_empty_inner_block_refs_fails(self, json_schema):
        """A loop block with empty inner_block_refs array must be rejected (minItems: 1)."""
        doc = _minimal_workflow_file(
            {"entry_block": {"type": "loop", "inner_block_refs": []}},
        )
        with pytest.raises(JsonSchemaValidationError):
            validate(instance=doc, schema=json_schema)

    def test_loop_block_has_max_rounds(self, json_schema):
        """LoopBlockDef in JSON schema should have max_rounds field."""
        loop_def = json_schema["$defs"]["LoopBlockDef"]
        assert "max_rounds" in loop_def["properties"]

    def test_loop_block_has_break_condition(self, json_schema):
        """LoopBlockDef in JSON schema should have break_condition field."""
        loop_def = json_schema["$defs"]["LoopBlockDef"]
        assert "break_condition" in loop_def["properties"]

    def test_loop_block_has_carry_context(self, json_schema):
        """LoopBlockDef in JSON schema should have carry_context field."""
        loop_def = json_schema["$defs"]["LoopBlockDef"]
        assert "carry_context" in loop_def["properties"]

    def test_loop_block_inner_block_refs_is_string_array(self, json_schema):
        """inner_block_refs must be an array of strings in the JSON schema."""
        loop_def = json_schema["$defs"]["LoopBlockDef"]
        refs_schema = loop_def["properties"]["inner_block_refs"]
        assert refs_schema["type"] == "array"
        assert refs_schema["items"]["type"] == "string"


# ===========================================================================
# JSON schema rejection for retired retry blocks
# ===========================================================================


class TestJsonSchemaRejectsRetryType:
    """Published JSON schema rejects retired retry block definitions."""

    def test_retry_block_type_rejected(self, json_schema):
        """A block with type: retry should not validate against the JSON schema."""
        doc = _minimal_workflow_file(
            {
                "entry_block": {
                    "type": "retry",
                    "inner_block_ref": "legacy_child_block",
                    "max_retries": 3,
                }
            },
        )
        with pytest.raises(JsonSchemaValidationError):
            validate(instance=doc, schema=json_schema)

    def test_no_retry_block_def_in_schema(self, json_schema):
        """RetryBlockDef should not exist in the JSON schema $defs."""
        assert "RetryBlockDef" not in json_schema.get("$defs", {}), (
            "RetryBlockDef still present in JSON schema"
        )

    def test_retry_not_in_discriminator_mapping(self, json_schema):
        """The discriminator mapping in blocks should not contain 'retry'."""
        blocks_schema = json_schema["properties"]["blocks"]
        mapping = blocks_schema["additionalProperties"]["discriminator"]["mapping"]
        assert "retry" not in mapping, "'retry' still in discriminator mapping"


# ===========================================================================
# JSON schema validation for retry_config on block types
# ===========================================================================


class TestJsonSchemaRetryConfigOnBlocks:
    """Published JSON schema accepts retry_config on supported block types."""

    def test_retry_config_on_linear_block(self, json_schema):
        """A linear (soul) block with retry_config should validate."""
        doc = _minimal_workflow_file(
            {
                "entry_block": {
                    "type": "linear",
                    "soul_ref": "primary_soul",
                    "retry_config": {
                        "max_attempts": 3,
                        "backoff": "exponential",
                        "backoff_base_seconds": 2.0,
                    },
                },
            },
        )
        validate(instance=doc, schema=json_schema)

    def test_retry_config_on_code_block(self, json_schema):
        """A code block with retry_config should validate."""
        doc = _minimal_workflow_file(
            {
                "entry_block": {
                    "type": "code",
                    "code": "print('hello')",
                    "retry_config": {"max_attempts": 5},
                },
            },
        )
        validate(instance=doc, schema=json_schema)

    def test_retry_config_on_loop_block(self, json_schema):
        """A loop block with retry_config should validate."""
        doc = _minimal_workflow_file(
            {
                "entry_block": {
                    "type": "loop",
                    "inner_block_refs": ["collect_step"],
                    "retry_config": {"max_attempts": 2, "backoff": "fixed"},
                },
            },
        )
        validate(instance=doc, schema=json_schema)

    def test_retry_config_schema_definition_exists(self, json_schema):
        """RetryConfig must be defined in the JSON schema $defs."""
        assert "RetryConfig" in json_schema.get("$defs", {}), (
            "RetryConfig missing from JSON schema $defs"
        )

    def test_retry_config_has_max_attempts(self, json_schema):
        """RetryConfig in JSON schema should have max_attempts field."""
        rc = json_schema["$defs"]["RetryConfig"]
        assert "max_attempts" in rc["properties"]

    def test_retry_config_has_backoff(self, json_schema):
        """RetryConfig in JSON schema should have backoff field."""
        rc = json_schema["$defs"]["RetryConfig"]
        assert "backoff" in rc["properties"]


# ===========================================================================
# Package workflow fixture migration
# ===========================================================================
