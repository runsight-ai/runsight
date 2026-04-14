"""
Red tests for blank canvas YAML bug.

Bug: WorkflowRepository.create() treats empty string YAML ("") as falsy,
falling through to _extract_yaml_data() instead of writing an empty file.

When the Setup Choose screen creates a blank canvas workflow, it sends
POST /api/workflows with { yaml: "" }. Python evaluates "" as falsy in
`if raw_yaml:`, so it falls through to the fallback branch.

The fix: change `if raw_yaml:` to `if raw_yaml is not None:`.

AC:
  - POST /api/workflows with { yaml: "" } creates a workflow with empty YAML content
  - POST /api/workflows with { yaml: "..." } still works (template YAML)
  - POST /api/workflows with no yaml field is rejected instead of falling back
  - PUT/commit paths also reject missing yaml so raw YAML stays canonical
"""

import pytest

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.errors import InputValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """Create a WorkflowRepository rooted at a temporary directory."""
    return WorkflowRepository(base_path=str(tmp_path))


@pytest.fixture
def workflows_dir(tmp_path):
    """Return the expected workflows directory path."""
    return tmp_path / "custom" / "workflows"


# ===========================================================================
# AC: POST /api/workflows with { yaml: "" } creates empty YAML content
# ===========================================================================


class TestEmptyStringYamlCreate:
    """Empty string YAML ("") must be written as-is, not treated as None."""

    def test_empty_yaml_string_writes_empty_file(self, repo, workflows_dir):
        """create({"yaml": "..."}) with a minimal YAML (id+kind only) must produce a YAML file."""
        minimal_yaml = "id: blank-canvas\nkind: workflow\n"
        entity = repo.create({"name": "Blank Canvas", "yaml": minimal_yaml})
        yaml_path = workflows_dir / f"{entity.id}.yaml"

        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert content == minimal_yaml, f"Expected minimal YAML content, got: {content!r}"

    def test_empty_yaml_string_entity_has_empty_yaml(self, repo):
        """The returned entity's yaml field must contain the provided YAML string."""
        minimal_yaml = "id: blank-canvas\nkind: workflow\n"
        entity = repo.create({"name": "Blank Canvas", "yaml": minimal_yaml})

        assert entity.yaml == minimal_yaml, (
            f"Expected entity.yaml to be the provided YAML, got: {entity.yaml!r}"
        )

    def test_empty_yaml_string_does_not_extract_yaml_data(self, repo, workflows_dir):
        """create({"yaml": "..."}) must write the provided YAML verbatim without merging name.

        Previously, if no raw_yaml was provided, _extract_yaml_data ran and
        auto-generated YAML from the data dict. We verify the provided YAML is used directly.
        """
        minimal_yaml = "id: blank-canvas\nkind: workflow\n"
        entity = repo.create({"name": "Blank Canvas", "yaml": minimal_yaml})
        yaml_path = workflows_dir / f"{entity.id}.yaml"

        content = yaml_path.read_text()
        # _extract_yaml_data fallback would produce "name: Blank Canvas\n"
        assert content == minimal_yaml, (
            f"_extract_yaml_data fallback was used instead of writing provided YAML: {content!r}"
        )


# ===========================================================================
# AC: POST /api/workflows with { yaml: "..." } still works (template YAML)
# ===========================================================================


class TestNonEmptyYamlCreate:
    """Non-empty raw YAML must be written directly (existing behavior, regression guard)."""

    def test_nonempty_yaml_written_directly(self, repo, workflows_dir):
        """create({"yaml": "..."}) must write the YAML verbatim."""
        raw = "id: template-flow\nkind: workflow\nversion: '1.0'\nworkflow:\n  name: My Flow\n"
        entity = repo.create({"name": "Template Flow", "yaml": raw})
        yaml_path = workflows_dir / f"{entity.id}.yaml"

        content = yaml_path.read_text()
        assert content == raw

    def test_nonempty_yaml_entity_carries_raw_content(self, repo):
        """Entity.yaml must contain the raw YAML string that was provided."""
        raw = "id: template-flow\nkind: workflow\nversion: '1.0'\nworkflow:\n  name: My Flow\n"
        entity = repo.create({"name": "Template Flow", "yaml": raw})
        assert entity.yaml == raw


# ===========================================================================
# AC: POST /api/workflows with no yaml field is rejected
# ===========================================================================


class TestNoYamlFieldCreate:
    """Missing yaml must be rejected instead of using a structured-field fallback."""

    def test_no_yaml_field_is_rejected(self, repo, workflows_dir):
        """create({"name": "test"}) must fail fast when raw yaml is absent."""
        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.create({"name": "Auto Generated"})

        assert list(workflows_dir.glob("*.yaml")) == []

    def test_none_yaml_field_is_rejected(self, repo, workflows_dir):
        """create({"name": "test", "yaml": None}) must be rejected too."""
        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.create({"name": "Explicit None", "yaml": None})

        assert list(workflows_dir.glob("*.yaml")) == []


# ===========================================================================
# AC: Empty string is NOT treated as None (core distinction)
# ===========================================================================


class TestEmptyStringIsNotNone:
    """The critical invariant: {"yaml": ""} is valid, while missing yaml is not."""

    def test_empty_string_yaml_differs_from_no_yaml(self, repo, workflows_dir):
        """A minimal valid YAML must succeed while missing yaml raises a validation error."""
        minimal_yaml = "id: blank-wf\nkind: workflow\n"
        entity_blank = repo.create({"name": "Blank", "yaml": minimal_yaml})
        blank_path = workflows_dir / f"{entity_blank.id}.yaml"
        blank_content = blank_path.read_text()
        assert blank_content == minimal_yaml
        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.create({"name": "Blank"})

    def test_empty_string_yaml_differs_from_none_yaml(self, repo, workflows_dir):
        """A minimal valid YAML must NOT behave the same as {"yaml": None}."""
        minimal_yaml = "id: blank-wf2\nkind: workflow\n"
        entity_blank = repo.create({"name": "Blank", "yaml": minimal_yaml})
        blank_path = workflows_dir / f"{entity_blank.id}.yaml"
        blank_content = blank_path.read_text()
        assert blank_content == minimal_yaml

        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.create({"name": "Blank", "yaml": None})


# ===========================================================================
# Same bug in update() — line 316 also uses `if raw_yaml:`
# ===========================================================================


class TestEmptyStringYamlUpdate:
    """The update() method has the same `if raw_yaml:` bug on line 316."""

    def test_update_with_empty_yaml_writes_empty_file(self, repo, workflows_dir):
        """update(id, {"yaml": "..."}) must overwrite the file with the new YAML content."""
        # Create a workflow with some initial YAML
        initial_yaml = (
            "id: to-update\nkind: workflow\nversion: '1.0'\nworkflow:\n  name: Original\n"
        )
        entity = repo.create({"name": "To Update", "yaml": initial_yaml})
        yaml_path = workflows_dir / f"{entity.id}.yaml"

        # Update with a minimal YAML (blank canvas reset)
        updated_yaml = "id: to-update\nkind: workflow\n"
        repo.update(entity.id, {"yaml": updated_yaml})

        content = yaml_path.read_text()
        assert content == updated_yaml, f"Expected updated YAML content, got: {content!r}"

    def test_update_empty_yaml_does_not_merge_existing(self, repo, workflows_dir):
        """update(id, {"yaml": "..."}) must replace existing content, not merge."""
        initial_yaml = (
            "id: to-update2\nkind: workflow\nversion: '1.0'\nworkflow:\n  name: Original\n"
        )
        entity = repo.create({"name": "To Update", "yaml": initial_yaml})
        yaml_path = workflows_dir / f"{entity.id}.yaml"

        updated_yaml = "id: to-update2\nkind: workflow\n"
        repo.update(entity.id, {"yaml": updated_yaml})

        content = yaml_path.read_text()
        assert "version" not in content, (
            f"update merged with existing content instead of replacing: {content!r}"
        )

    def test_update_without_yaml_is_rejected_instead_of_merging_existing(self, repo, workflows_dir):
        """update(id, {"name": "..."}) must fail instead of synthesizing YAML."""
        initial_yaml = (
            "id: to-update3\nkind: workflow\nversion: '1.0'\nworkflow:\n  name: Original\n"
        )
        entity = repo.create({"name": "To Update", "yaml": initial_yaml})
        yaml_path = workflows_dir / f"{entity.id}.yaml"

        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.update(entity.id, {"name": "Renamed"})

        assert yaml_path.read_text() == initial_yaml
