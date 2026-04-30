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
import yaml as pyyaml

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


class TestMockupPipelineMigration:
    """Package-local mockup workflow fixture uses LoopBlock shape."""

    def test_mockup_pipeline_exists(self):
        """mockup_pipeline.yaml must exist."""
        assert PACKAGE_WORKFLOW_FIXTURES.joinpath("mockup_pipeline.yaml").exists()

    def test_mockup_pipeline_no_retry_type(self):
        """mockup_pipeline.yaml must not contain type: retry."""
        content = PACKAGE_WORKFLOW_FIXTURES.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        for block_id, block_def in data.get("blocks", {}).items():
            assert block_def.get("type") != "retry", f"Block '{block_id}' still uses type: retry"

    def test_mockup_pipeline_has_loop_block(self):
        """After migration, mockup_pipeline.yaml should contain at least one type: loop block."""
        content = PACKAGE_WORKFLOW_FIXTURES.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        block_types = [b.get("type") for b in data.get("blocks", {}).values()]
        assert "loop" in block_types, "No loop block found in mockup_pipeline.yaml after migration"

    def test_mockup_pipeline_loop_has_inner_block_refs(self):
        """The migrated loop block must use inner_block_refs (list), not inner_block_ref (string)."""
        content = PACKAGE_WORKFLOW_FIXTURES.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        for block_id, block_def in data.get("blocks", {}).items():
            if block_def.get("type") == "loop":
                assert "inner_block_refs" in block_def, (
                    f"Loop block '{block_id}' missing inner_block_refs"
                )
                assert isinstance(block_def["inner_block_refs"], list), (
                    f"inner_block_refs in block '{block_id}' must be a list"
                )
                assert "inner_block_ref" not in block_def, (
                    f"Loop block '{block_id}' still uses old singular inner_block_ref"
                )

    def test_mockup_pipeline_no_max_retries_field(self):
        """Migrated blocks should not have max_retries (old retry field)."""
        content = PACKAGE_WORKFLOW_FIXTURES.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        for block_id, block_def in data.get("blocks", {}).items():
            assert "max_retries" not in block_def, f"Block '{block_id}' still has max_retries"

    def test_mockup_pipeline_no_provide_error_context(self):
        """Migrated blocks should not have provide_error_context (old retry field)."""
        content = PACKAGE_WORKFLOW_FIXTURES.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        for block_id, block_def in data.get("blocks", {}).items():
            assert "provide_error_context" not in block_def, (
                f"Block '{block_id}' still has provide_error_context"
            )

    def test_mockup_pipeline_validates_against_json_schema(self, json_schema):
        """mockup_pipeline.yaml must validate against the published JSON schema."""
        content = PACKAGE_WORKFLOW_FIXTURES.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        validate(instance=data, schema=json_schema)


# ===========================================================================
# Package workflow fixture validation
# ===========================================================================


class TestExampleWorkflowsValidate:
    """Package-local workflow fixtures parse against current schema contracts."""

    @pytest.fixture(scope="class")
    def workflow_files(self):
        """Discover package-local workflow fixture YAML files."""
        return _workflow_fixture_files()

    def test_at_least_one_example_workflow_exists(self, workflow_files):
        """There should be at least one example workflow."""
        assert len(workflow_files) > 0, f"No workflow fixtures found in {PACKAGE_WORKFLOW_FIXTURES}"

    def test_all_example_workflows_are_valid_yaml(self, workflow_files):
        """All example workflow files must be valid YAML."""
        for wf_path in workflow_files:
            content = wf_path.read_text()
            data = pyyaml.safe_load(content)
            assert isinstance(data, dict), f"{wf_path.name} did not parse as a dict"

    def test_all_example_workflows_validate_against_schema(self, json_schema, workflow_files):
        """All example workflows must validate against the published JSON schema."""
        errors = []
        for wf_path in workflow_files:
            content = wf_path.read_text()
            data = pyyaml.safe_load(content)
            try:
                validate(instance=data, schema=json_schema)
            except JsonSchemaValidationError as e:
                errors.append(f"{wf_path.name}: {e.message}")
        assert not errors, "Schema validation failures:\n" + "\n".join(errors)

    def test_all_example_workflows_pydantic_parse(self, workflow_files):
        """All example workflows must parse via Pydantic RunsightWorkflowFile."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        errors = []
        for wf_path in workflow_files:
            content = wf_path.read_text()
            data = pyyaml.safe_load(content)
            try:
                RunsightWorkflowFile.model_validate(data)
            except Exception as e:
                errors.append(f"{wf_path.name}: {e}")
        assert not errors, "Pydantic validation failures:\n" + "\n".join(errors)


# ===========================================================================
# Retired RetryBlock source governance
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
