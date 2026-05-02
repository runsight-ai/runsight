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
