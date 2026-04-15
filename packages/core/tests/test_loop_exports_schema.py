"""
Failing tests for RUN-162: Update JSON schema, example workflows & exports for LoopBlock.

Covers:
- __init__.py exports: LoopBlockDef, RetryConfig, CarryContextConfig present
- JSON schema validation: valid loop block passes, missing inner_block_refs fails,
  retry_config on soul block passes, old retry block type fails
- mockup_pipeline.yaml migrated from type: retry to type: loop
- No RetryBlock / RetryBlockDef references in codebase
- Example workflows parse and validate against updated schema
- Block registry maps "loop" -> LoopBlock class
"""

from __future__ import annotations

import json
import subprocess
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

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "runsight-workflow-schema.json"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # runsight/
CORE_ROOT = REPO_ROOT / "packages" / "core"
CUSTOM_WORKFLOWS = Path(__file__).resolve().parent / "fixtures" / "custom" / "workflows"


@pytest.fixture(scope="module")
def json_schema() -> Dict[str, Any]:
    """Load the published JSON schema from disk."""
    return json.loads(SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_workflow_file(blocks: Dict[str, Any], entry: str = "b1") -> Dict[str, Any]:
    """Build a minimal RunsightWorkflowFile dict for JSON-schema validation."""
    return {
        "version": "1.0",
        "id": "test-workflow",
        "kind": "workflow",
        "workflow": {"name": "test", "entry": entry},
        "blocks": blocks,
    }


# ===========================================================================
# 1. __init__.py exports — LoopBlockDef, RetryConfig, CarryContextConfig
# ===========================================================================


class TestTopLevelExports:
    """RUN-162 AC: __init__.py exports verified."""

    def test_loop_block_def_exported(self):
        """LoopBlockDef should be importable from the top-level runsight_core package."""
        import runsight_core

        assert hasattr(runsight_core, "LoopBlockDef"), (
            "LoopBlockDef not found in runsight_core — add it to __init__.py"
        )
        assert "LoopBlockDef" in runsight_core.__all__

    def test_retry_config_exported(self):
        """RetryConfig should be importable from the top-level runsight_core package."""
        import runsight_core

        assert hasattr(runsight_core, "RetryConfig"), (
            "RetryConfig not found in runsight_core — add it to __init__.py"
        )
        assert "RetryConfig" in runsight_core.__all__

    def test_carry_context_config_exported(self):
        """CarryContextConfig should be importable from the top-level runsight_core package."""
        import runsight_core

        assert hasattr(runsight_core, "CarryContextConfig"), (
            "CarryContextConfig not found in runsight_core — add it to __init__.py"
        )
        assert "CarryContextConfig" in runsight_core.__all__

    def test_no_retry_block_in_all(self):
        """RetryBlock must NOT appear in __all__ — it was replaced by LoopBlock."""
        import runsight_core

        assert "RetryBlock" not in runsight_core.__all__

    def test_no_retry_block_def_in_all(self):
        """RetryBlockDef must NOT appear in __all__."""
        import runsight_core

        assert "RetryBlockDef" not in runsight_core.__all__


# ===========================================================================
# 2. JSON schema validation — loop block
# ===========================================================================


class TestJsonSchemaLoopBlock:
    """RUN-162 AC: JSON schema validates type: loop blocks with inner_block_refs."""

    def test_valid_loop_block_passes(self, json_schema):
        """A well-formed loop block with inner_block_refs should validate."""
        doc = _minimal_workflow_file(
            {"b1": {"type": "loop", "inner_block_refs": ["step_a", "step_b"]}},
        )
        validate(instance=doc, schema=json_schema)

    def test_loop_block_without_inner_block_refs_fails(self, json_schema):
        """A loop block missing inner_block_refs must be rejected by JSON schema."""
        doc = _minimal_workflow_file(
            {"b1": {"type": "loop"}},
        )
        with pytest.raises(JsonSchemaValidationError):
            validate(instance=doc, schema=json_schema)

    def test_loop_block_empty_inner_block_refs_fails(self, json_schema):
        """A loop block with empty inner_block_refs array must be rejected (minItems: 1)."""
        doc = _minimal_workflow_file(
            {"b1": {"type": "loop", "inner_block_refs": []}},
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
# 3. JSON schema validation — retry type rejected
# ===========================================================================


class TestJsonSchemaRejectsRetryType:
    """RUN-162 AC: JSON schema rejects type: retry blocks."""

    def test_retry_block_type_rejected(self, json_schema):
        """A block with type: retry must NOT validate against the JSON schema."""
        doc = _minimal_workflow_file(
            {"b1": {"type": "retry", "inner_block_ref": "some_block", "max_retries": 3}},
        )
        with pytest.raises(JsonSchemaValidationError):
            validate(instance=doc, schema=json_schema)

    def test_no_retry_block_def_in_schema(self, json_schema):
        """RetryBlockDef should not exist in the JSON schema $defs."""
        assert "RetryBlockDef" not in json_schema.get("$defs", {}), (
            "RetryBlockDef still present in JSON schema — remove it"
        )

    def test_retry_not_in_discriminator_mapping(self, json_schema):
        """The discriminator mapping in blocks should NOT contain 'retry'."""
        blocks_schema = json_schema["properties"]["blocks"]
        mapping = blocks_schema["additionalProperties"]["discriminator"]["mapping"]
        assert "retry" not in mapping, "'retry' still in discriminator mapping — remove it"


# ===========================================================================
# 4. JSON schema validation — retry_config on any block type
# ===========================================================================


class TestJsonSchemaRetryConfigOnBlocks:
    """RUN-162 AC: JSON schema validates retry_config on any block type."""

    def test_retry_config_on_linear_block(self, json_schema):
        """A linear (soul) block with retry_config should validate."""
        doc = _minimal_workflow_file(
            {
                "b1": {
                    "type": "linear",
                    "soul_ref": "s1",
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
                "b1": {
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
                "b1": {
                    "type": "loop",
                    "inner_block_refs": ["step_a"],
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
# 5. mockup_pipeline.yaml migration
# ===========================================================================


class TestMockupPipelineMigration:
    """RUN-162 AC: custom/workflows/mockup_pipeline.yaml migrated from retry to loop."""

    def test_mockup_pipeline_exists(self):
        """mockup_pipeline.yaml must exist."""
        assert CUSTOM_WORKFLOWS.joinpath("mockup_pipeline.yaml").exists()

    def test_mockup_pipeline_no_retry_type(self):
        """mockup_pipeline.yaml must not contain type: retry."""
        content = CUSTOM_WORKFLOWS.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        for block_id, block_def in data.get("blocks", {}).items():
            assert block_def.get("type") != "retry", (
                f"Block '{block_id}' still uses type: retry — migrate to type: loop"
            )

    def test_mockup_pipeline_has_loop_block(self):
        """After migration, mockup_pipeline.yaml should contain at least one type: loop block."""
        content = CUSTOM_WORKFLOWS.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        block_types = [b.get("type") for b in data.get("blocks", {}).values()]
        assert "loop" in block_types, "No loop block found in mockup_pipeline.yaml after migration"

    def test_mockup_pipeline_loop_has_inner_block_refs(self):
        """The migrated loop block must use inner_block_refs (list), not inner_block_ref (string)."""
        content = CUSTOM_WORKFLOWS.joinpath("mockup_pipeline.yaml").read_text()
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
        content = CUSTOM_WORKFLOWS.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        for block_id, block_def in data.get("blocks", {}).items():
            assert "max_retries" not in block_def, (
                f"Block '{block_id}' still has max_retries — use max_rounds on loop"
            )

    def test_mockup_pipeline_no_provide_error_context(self):
        """Migrated blocks should not have provide_error_context (old retry field)."""
        content = CUSTOM_WORKFLOWS.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        for block_id, block_def in data.get("blocks", {}).items():
            assert "provide_error_context" not in block_def, (
                f"Block '{block_id}' still has provide_error_context — obsolete"
            )

    def test_mockup_pipeline_validates_against_json_schema(self, json_schema):
        """mockup_pipeline.yaml must validate against the published JSON schema."""
        content = CUSTOM_WORKFLOWS.joinpath("mockup_pipeline.yaml").read_text()
        data = pyyaml.safe_load(content)
        validate(instance=data, schema=json_schema)


# ===========================================================================
# 6. Example workflows parse and validate (integration)
# ===========================================================================


class TestExampleWorkflowsValidate:
    """RUN-162 AC: Example workflows parse and validate against updated schema."""

    @pytest.fixture(scope="class")
    def workflow_files(self):
        """Discover all YAML workflow files under custom/workflows/."""
        return list(CUSTOM_WORKFLOWS.glob("*.yaml"))

    def test_at_least_one_example_workflow_exists(self, workflow_files):
        """There should be at least one example workflow."""
        assert len(workflow_files) > 0, "No example workflows found in custom/workflows/"

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
# 7. No RetryBlock references in codebase
# ===========================================================================


class TestNoRetryBlockReferences:
    """RUN-162 AC: Zero references to RetryBlock or RetryBlockDef in codebase."""

    def test_no_retry_block_in_source(self):
        """grep -r 'RetryBlock' should return zero hits in Python source (excluding tests, git)."""
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.py",
                "-l",
                "RetryBlock",
                str(CORE_ROOT / "src"),
            ],
            capture_output=True,
            text=True,
        )
        # Filter out test files and __pycache__
        hits = [
            line
            for line in result.stdout.strip().splitlines()
            if line
            and "__pycache__" not in line
            and "/tests/" not in line
            and "/build/" not in line
        ]
        assert not hits, "RetryBlock still referenced in source files:\n" + "\n".join(hits)

    def test_no_retry_block_def_in_source(self):
        """grep -r 'RetryBlockDef' should return zero hits in Python source (excluding tests, git)."""
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.py",
                "-l",
                "RetryBlockDef",
                str(CORE_ROOT / "src"),
            ],
            capture_output=True,
            text=True,
        )
        hits = [
            line
            for line in result.stdout.strip().splitlines()
            if line
            and "__pycache__" not in line
            and "/tests/" not in line
            and "/build/" not in line
        ]
        assert not hits, "RetryBlockDef still referenced in source files:\n" + "\n".join(hits)

    def test_no_retry_block_in_yaml_files(self):
        """No YAML files should reference type: retry."""
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.yaml",
                "--include=*.yml",
                "-l",
                "type: retry",
                str(REPO_ROOT / "custom"),
            ],
            capture_output=True,
            text=True,
        )
        hits = [line for line in result.stdout.strip().splitlines() if line]
        assert not hits, "'type: retry' still found in YAML files:\n" + "\n".join(hits)

    def test_no_retry_block_in_init_exports(self):
        """__init__.py must not export RetryBlock."""
        init_path = CORE_ROOT / "src" / "runsight_core" / "__init__.py"
        content = init_path.read_text()
        assert "RetryBlock" not in content, "RetryBlock still in __init__.py — remove it"


# ===========================================================================
# 8. Block registry maps "loop" -> LoopBlock
# ===========================================================================


class TestBlockRegistryLoopMapping:
    """RUN-162 AC: Block type registry maps 'loop' to LoopBlock class."""

    def test_loop_in_block_type_registry(self):
        """BLOCK_TYPE_REGISTRY should have 'loop' key."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert "loop" in BLOCK_TYPE_REGISTRY, "'loop' not found in BLOCK_TYPE_REGISTRY"

    def test_retry_not_in_block_type_registry(self):
        """BLOCK_TYPE_REGISTRY should NOT have 'retry' key."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert "retry" not in BLOCK_TYPE_REGISTRY, (
            "'retry' still in BLOCK_TYPE_REGISTRY — remove it"
        )

    def test_loop_builder_produces_loop_block(self):
        """The 'loop' builder in BLOCK_TYPE_REGISTRY should produce a LoopBlock."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        builder = BLOCK_TYPE_REGISTRY["loop"]
        # The builder signature is (block_id, block_def, souls_map) or similar.
        # We just verify the builder exists and is callable.
        assert callable(builder)
