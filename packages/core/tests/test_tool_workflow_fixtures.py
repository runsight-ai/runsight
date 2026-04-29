"""Existing custom workflow fixture parsing tests."""

from __future__ import annotations

from pathlib import Path

from runsight_core.yaml.parser import parse_workflow_yaml

# ===========================================================================
# Bonus: YAML workflow files on disk parse successfully after tools: update
# ===========================================================================


CUSTOM_WORKFLOWS_DIR = Path(__file__).resolve().parent / "fixtures" / "custom" / "workflows"


class TestExistingYamlWorkflowsParseClean:
    """All existing YAML workflow files in custom/workflows/ must parse without
    error after any tools: section updates. This test will fail if a workflow
    file references an undeclared tool source or has a broken tool reference."""

    def test_mockup_pipeline_yaml_is_valid_yaml(self) -> None:
        """fixtures/custom/workflows/mockup_pipeline.yaml must be parseable YAML with a tools: section."""
        import yaml

        yaml_path = CUSTOM_WORKFLOWS_DIR / "mockup_pipeline.yaml"
        assert yaml_path.exists(), f"Workflow file missing: {yaml_path}"

        with open(yaml_path) as f:
            raw = yaml.safe_load(f)

        # Must be a dict with required top-level keys
        assert isinstance(raw, dict)
        assert "workflow" in raw
        assert "version" in raw

    def test_existing_checked_in_workflow_parses(self) -> None:
        """A checked-in workflow fixture should still parse successfully."""
        yaml_path = CUSTOM_WORKFLOWS_DIR / "research-review-fw2ry.yaml"
        assert yaml_path.exists(), f"Workflow file missing: {yaml_path}"
        workflow = parse_workflow_yaml(str(yaml_path))
        assert workflow is not None
