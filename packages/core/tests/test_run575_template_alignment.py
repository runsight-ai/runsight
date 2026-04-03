"""
Failing tests for RUN-575: Align default workflow template with library-only souls.

After implementation:
1. Library soul files exist for the template's soul_refs (researcher, writer, reviewer)
2. No workflow YAML file in ``custom/workflows/`` contains an inline ``souls:`` section

All tests should FAIL until:
- ``custom/souls/researcher.yaml``, ``custom/souls/writer.yaml``,
  ``custom/souls/reviewer.yaml`` are created
- All ``custom/workflows/*.yaml`` files have their inline ``souls:`` sections removed
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Repo root discovery (same pattern as test_retryblock_migration.py)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # runsight/
CUSTOM_SOULS = REPO_ROOT / "custom" / "souls"
CUSTOM_WORKFLOWS = REPO_ROOT / "custom" / "workflows"


# ===========================================================================
# AC2: Library soul files exist for the template's soul_refs
# ===========================================================================


class TestLibrarySoulFilesExist:
    """The template references researcher, writer, reviewer via soul_ref.

    Each of these must have a corresponding YAML file in custom/souls/
    so the library-only parser can resolve them.
    """

    def test_researcher_soul_file_exists(self):
        """custom/souls/researcher.yaml must exist."""
        soul_file = CUSTOM_SOULS / "researcher.yaml"
        assert soul_file.exists(), (
            f"Missing library soul file: {soul_file}\n"
            "The template's soul_ref: researcher cannot resolve without it."
        )

    def test_writer_soul_file_exists(self):
        """custom/souls/writer.yaml must exist."""
        soul_file = CUSTOM_SOULS / "writer.yaml"
        assert soul_file.exists(), (
            f"Missing library soul file: {soul_file}\n"
            "The template's soul_ref: writer cannot resolve without it."
        )

    def test_reviewer_soul_file_exists(self):
        """custom/souls/reviewer.yaml must exist."""
        soul_file = CUSTOM_SOULS / "reviewer.yaml"
        assert soul_file.exists(), (
            f"Missing library soul file: {soul_file}\n"
            "The template's soul_ref: reviewer cannot resolve without it."
        )

    def test_researcher_soul_file_is_valid_yaml(self):
        """custom/souls/researcher.yaml must be parseable YAML with required fields."""
        soul_file = CUSTOM_SOULS / "researcher.yaml"
        if not soul_file.exists():
            pytest.skip("researcher.yaml does not exist yet")
        data = yaml.safe_load(soul_file.read_text())
        assert isinstance(data, dict), "Soul file must be a YAML mapping"
        assert "id" in data, "Soul file must contain 'id' field"
        assert "system_prompt" in data, "Soul file must contain 'system_prompt' field"

    def test_writer_soul_file_is_valid_yaml(self):
        """custom/souls/writer.yaml must be parseable YAML with required fields."""
        soul_file = CUSTOM_SOULS / "writer.yaml"
        if not soul_file.exists():
            pytest.skip("writer.yaml does not exist yet")
        data = yaml.safe_load(soul_file.read_text())
        assert isinstance(data, dict), "Soul file must be a YAML mapping"
        assert "id" in data, "Soul file must contain 'id' field"
        assert "system_prompt" in data, "Soul file must contain 'system_prompt' field"

    def test_reviewer_soul_file_is_valid_yaml(self):
        """custom/souls/reviewer.yaml must be parseable YAML with required fields."""
        soul_file = CUSTOM_SOULS / "reviewer.yaml"
        if not soul_file.exists():
            pytest.skip("reviewer.yaml does not exist yet")
        data = yaml.safe_load(soul_file.read_text())
        assert isinstance(data, dict), "Soul file must be a YAML mapping"
        assert "id" in data, "Soul file must contain 'id' field"
        assert "system_prompt" in data, "Soul file must contain 'system_prompt' field"


# ===========================================================================
# AC4: No workflow YAML files use inline souls
# ===========================================================================


class TestNoWorkflowsUseInlineSouls:
    """Every workflow YAML file in custom/workflows/ must be free of inline souls."""

    @staticmethod
    def _discover_workflow_files() -> list[Path]:
        """Return all .yaml files under custom/workflows/."""
        if not CUSTOM_WORKFLOWS.exists():
            return []
        return sorted(CUSTOM_WORKFLOWS.glob("*.yaml"))

    def test_custom_workflows_directory_exists(self):
        """Sanity check: custom/workflows/ must exist."""
        assert CUSTOM_WORKFLOWS.exists(), f"Directory not found: {CUSTOM_WORKFLOWS}"

    def test_at_least_one_workflow_file_exists(self):
        """Sanity check: there should be at least one workflow YAML file."""
        files = self._discover_workflow_files()
        assert len(files) > 0, "No workflow YAML files found in custom/workflows/"

    def test_no_workflow_has_inline_souls_section(self):
        """No workflow YAML file should contain a top-level `souls:` key with content."""
        files = self._discover_workflow_files()
        violations: list[str] = []

        for wf_file in files:
            try:
                data = yaml.safe_load(wf_file.read_text())
            except yaml.YAMLError:
                continue  # Skip unparseable files; not our concern here

            if not isinstance(data, dict):
                continue

            souls = data.get("souls")
            if souls is not None and souls != {}:
                violations.append(wf_file.name)

        assert violations == [], (
            "Workflow files still contain inline souls: section:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_each_workflow_file_individually(self):
        """Check each workflow file individually for inline souls (detailed failures)."""
        files = self._discover_workflow_files()

        for wf_file in files:
            try:
                data = yaml.safe_load(wf_file.read_text())
            except yaml.YAMLError:
                continue

            if not isinstance(data, dict):
                continue

            souls = data.get("souls")
            assert souls is None or souls == {}, (
                f"{wf_file.name} still has inline souls: section with keys: "
                f"{list(souls.keys()) if isinstance(souls, dict) else type(souls).__name__}"
            )
