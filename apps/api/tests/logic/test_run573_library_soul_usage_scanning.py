"""RUN-573: Library-only soul usage scanning.

Verify that _extract_workflow_soul_ids() and its consumers work correctly
under the library-only model (no inline souls: section in workflows).
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from runsight_api.domain.errors import SoulInUse
from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity
from runsight_api.logic.services.soul_service import SoulService


def workflow_entity(id: str, name: str, yaml: str | None) -> WorkflowEntity:
    return WorkflowEntity(id=id, name=name, yaml=yaml)


def make_service(workflow_repo=None) -> tuple[Mock, SoulService]:
    soul_repo = Mock()
    service = SoulService(soul_repo, workflow_repo=workflow_repo)
    return soul_repo, service


# ---------------------------------------------------------------------------
# AC1: Usage scanning does not reference inline souls: section
# ---------------------------------------------------------------------------


class TestAC1InlineSoulsIgnored:
    """Workflows without a souls: section must still produce correct soul_ref extraction."""

    def test_extract_soul_ids_without_souls_section(self):
        """Library-only YAML (no souls: section) extracts soul_ref values correctly."""
        wf = workflow_entity(
            "wf_1",
            "Library Only",
            """
blocks:
  analyze:
    type: linear
    soul_ref: web_researcher
  summarize:
    type: linear
    soul_ref: summarizer
""",
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        assert result == ["web_researcher", "summarizer"]

    def test_extract_ignores_souls_section_even_if_present(self):
        """If a legacy workflow still has a souls: section, only soul_ref in blocks counts.

        The souls: section should NOT contribute any IDs to the extraction result.
        A soul declared in souls: but NOT referenced via soul_ref in blocks is invisible.
        """
        wf = workflow_entity(
            "wf_legacy",
            "Legacy With Souls Section",
            """
souls:
  legacy_soul:
    role: Legacy
    system_prompt: I am legacy
blocks:
  draft:
    type: linear
    soul_ref: web_researcher
""",
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        # Must contain ONLY the block-level soul_ref, never the souls: key
        assert "legacy_soul" not in result
        assert result == ["web_researcher"]

    def test_extract_soul_ref_not_confused_with_souls_section_keys(self):
        """A soul_ref value that happens to match a souls: section key is counted
        once (from the block), not from the souls: section itself."""
        wf = workflow_entity(
            "wf_overlap",
            "Overlap",
            """
souls:
  web_researcher:
    role: Researcher
blocks:
  research:
    type: linear
    soul_ref: web_researcher
""",
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        assert result == ["web_researcher"]
        # Exactly one entry, not duplicated
        assert len(result) == 1


# ---------------------------------------------------------------------------
# AC2: soul_ref values are matched as library slugs (filename stems)
# ---------------------------------------------------------------------------


class TestAC2SoulRefSlugMatching:
    """soul_ref: web_researcher increments web_researcher.yaml usage count."""

    def test_soul_ref_matches_library_slug_in_workflow_count(self):
        """soul_ref: web_researcher must map to the soul with id='web_researcher',
        which corresponds to custom/souls/web_researcher.yaml."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [
            SoulEntity(id="web_researcher", role="Researcher"),
            SoulEntity(id="editor", role="Editor"),
        ]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Research Pipeline",
                """
blocks:
  step1:
    type: linear
    soul_ref: web_researcher
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        web_researcher = next(s for s in result if s.id == "web_researcher")
        editor = next(s for s in result if s.id == "editor")
        assert web_researcher.workflow_count == 1
        assert editor.workflow_count == 0

    def test_soul_ref_slug_exact_match_not_substring(self):
        """soul_ref: 'researcher' must NOT count for soul id 'web_researcher'."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [
            SoulEntity(id="web_researcher", role="Web Researcher"),
            SoulEntity(id="researcher", role="Researcher"),
        ]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Research",
                """
blocks:
  step1:
    type: linear
    soul_ref: researcher
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        web_researcher = next(s for s in result if s.id == "web_researcher")
        researcher = next(s for s in result if s.id == "researcher")
        assert web_researcher.workflow_count == 0
        assert researcher.workflow_count == 1

    def test_soul_ref_in_exit_counts_as_library_slug(self):
        """soul_ref inside exits[] also maps to library soul slugs."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [SoulEntity(id="web_researcher", role="Researcher")]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_dispatch",
                "Dispatch",
                """
blocks:
  route:
    type: dispatch
    exits:
      - id: research_exit
        label: Research
        soul_ref: web_researcher
        task: Do research
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        web_researcher = result[0]
        assert web_researcher.workflow_count == 1

    def test_soul_ref_matches_filename_stem_when_yaml_id_differs(self):
        """Workflow soul_ref values should match the soul filename stem, not only the embedded YAML id."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [SoulEntity(id="researcher_1", role="Researcher")]
        soul_repo.list_all.return_value = souls
        soul_repo._resolve_existing_path.side_effect = lambda soul_id: Path(
            f"/tmp/custom/souls/{'researcher' if soul_id == 'researcher_1' else soul_id}.yaml"
        )
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Research",
                """
blocks:
  step1:
    type: linear
    soul_ref: researcher
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        assert result[0].workflow_count == 1


# ---------------------------------------------------------------------------
# AC3: Delete pre-check lists correct workflows for a library soul
# ---------------------------------------------------------------------------


class TestAC3DeletePreCheck:
    """get_soul_usages() returns workflows that reference the soul via soul_ref slug."""

    def test_get_soul_usages_lists_referencing_workflows(self):
        """Delete pre-check correctly identifies all workflows using a soul."""
        soul_repo, service = make_service()
        workflow_repo = Mock()
        soul_repo.get_by_id.return_value = SoulEntity(id="web_researcher", role="Researcher")
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Pipeline A",
                """
blocks:
  step1:
    type: linear
    soul_ref: web_researcher
""",
            ),
            workflow_entity(
                "wf_2",
                "Pipeline B",
                """
blocks:
  step1:
    type: linear
    soul_ref: editor
""",
            ),
            workflow_entity(
                "wf_3",
                "Pipeline C",
                """
blocks:
  step1:
    type: linear
    soul_ref: web_researcher
  step2:
    type: dispatch
    exits:
      - id: e1
        soul_ref: web_researcher
""",
            ),
        ]

        usages = service.get_soul_usages("web_researcher", workflow_repo)

        workflow_ids = [u["workflow_id"] for u in usages]
        assert "wf_1" in workflow_ids
        assert "wf_2" not in workflow_ids
        assert "wf_3" in workflow_ids
        assert len(usages) == 2

    def test_get_soul_usages_matches_filename_stem_when_yaml_id_differs(self):
        """Usage scanning should still find workflows when the file stem and embedded soul id differ."""
        soul_repo, service = make_service()
        workflow_repo = Mock()
        soul_repo.get_by_id.return_value = SoulEntity(id="researcher_1", role="Researcher")
        soul_repo._resolve_existing_path.side_effect = lambda soul_id: Path(
            f"/tmp/custom/souls/{'researcher' if soul_id == 'researcher_1' else soul_id}.yaml"
        )
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Research Pipeline",
                """
blocks:
  step1:
    type: linear
    soul_ref: researcher
""",
            ),
        ]

        usages = service.get_soul_usages("researcher_1", workflow_repo)

        assert usages == [{"workflow_id": "wf_1", "workflow_name": "Research Pipeline"}]

    def test_delete_blocked_when_soul_in_use_library_only(self):
        """Delete is blocked with SoulInUse when library soul is referenced."""
        soul_repo = Mock()
        git_service = Mock()
        workflow_repo = Mock()
        soul_repo.get_by_id.return_value = SoulEntity(id="web_researcher", role="Researcher")
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Research Pipeline",
                """
blocks:
  research:
    type: linear
    soul_ref: web_researcher
""",
            ),
        ]
        service = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(SoulInUse) as exc_info:
            service.delete_soul("web_researcher", workflow_repo=workflow_repo)

        details = exc_info.value.to_dict()["details"]
        assert len(details["usages"]) == 1
        assert details["usages"][0]["workflow_id"] == "wf_1"
        assert details["usages"][0]["workflow_name"] == "Research Pipeline"

    def test_delete_allowed_when_soul_not_referenced(self):
        """Delete succeeds when no workflow references the soul."""
        soul_repo = Mock()
        git_service = Mock()
        workflow_repo = Mock()
        soul_repo.get_by_id.return_value = SoulEntity(id="orphan", role="Orphan")
        soul_repo.delete.return_value = True
        git_service.is_clean.return_value = False
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Other",
                """
blocks:
  step:
    type: linear
    soul_ref: editor
""",
            ),
        ]
        service = SoulService(soul_repo, git_service=git_service)

        result = service.delete_soul("orphan", workflow_repo=workflow_repo)

        assert result is True
        soul_repo.delete.assert_called_once_with("orphan")

    def test_get_soul_usages_with_workflow_referencing_deleted_soul(self):
        """A workflow referencing a deleted soul still counts in usage scanning.

        Even if the soul file was deleted from disk, if a workflow YAML still
        contains soul_ref: deleted_soul, it must appear in the scan results.
        This tests the scanning side — get_soul_usages requires the soul to exist,
        but _extract_workflow_soul_ids should still find the reference.
        """
        wf = workflow_entity(
            "wf_stale",
            "Stale Ref",
            """
blocks:
  step:
    type: linear
    soul_ref: deleted_soul
""",
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        assert "deleted_soul" in result


# ---------------------------------------------------------------------------
# AC4: 0 usages, 1 usage, N usages across multiple workflows
# ---------------------------------------------------------------------------


class TestAC4UsageCountVariants:
    """Tests for 0, 1, and N usages across multiple workflows."""

    def test_zero_usages(self):
        """Soul with zero references across all workflows has count 0."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [SoulEntity(id="unused_soul", role="Unused")]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Workflow A",
                """
blocks:
  step:
    type: linear
    soul_ref: other_soul
""",
            ),
            workflow_entity(
                "wf_2",
                "Workflow B",
                """
blocks:
  step:
    type: linear
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        assert result[0].workflow_count == 0

    def test_one_usage_single_workflow(self):
        """Soul referenced in exactly one workflow has count 1."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [SoulEntity(id="web_researcher", role="Researcher")]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Single Use",
                """
blocks:
  step:
    type: linear
    soul_ref: web_researcher
""",
            ),
            workflow_entity(
                "wf_2",
                "No Use",
                """
blocks:
  step:
    type: linear
    soul_ref: other
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        assert result[0].workflow_count == 1

    def test_n_usages_across_multiple_workflows(self):
        """Soul referenced across N workflows has count N (workflow-level, not block-level)."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [SoulEntity(id="web_researcher", role="Researcher")]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Pipeline A",
                """
blocks:
  step1:
    type: linear
    soul_ref: web_researcher
  step2:
    type: linear
    soul_ref: web_researcher
""",
            ),
            workflow_entity(
                "wf_2",
                "Pipeline B",
                """
blocks:
  step1:
    type: linear
    soul_ref: web_researcher
""",
            ),
            workflow_entity(
                "wf_3",
                "Pipeline C",
                """
blocks:
  route:
    type: dispatch
    exits:
      - id: e1
        soul_ref: web_researcher
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        # Count is per-workflow, not per-block. 3 workflows reference it.
        assert result[0].workflow_count == 3

    def test_multiple_souls_mixed_usage_counts(self):
        """Multiple souls with varying usage counts across multiple workflows."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [
            SoulEntity(id="researcher", role="Researcher"),
            SoulEntity(id="editor", role="Editor"),
            SoulEntity(id="reviewer", role="Reviewer"),
            SoulEntity(id="orphan", role="Orphan"),
        ]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Full Pipeline",
                """
blocks:
  research:
    type: linear
    soul_ref: researcher
  edit:
    type: linear
    soul_ref: editor
  review:
    type: linear
    soul_ref: reviewer
""",
            ),
            workflow_entity(
                "wf_2",
                "Review Only",
                """
blocks:
  review:
    type: linear
    soul_ref: reviewer
""",
            ),
            workflow_entity(
                "wf_3",
                "Research Only",
                """
blocks:
  research:
    type: linear
    soul_ref: researcher
""",
            ),
        ]
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        counts = {s.id: s.workflow_count for s in result}
        assert counts["researcher"] == 2
        assert counts["editor"] == 1
        assert counts["reviewer"] == 2
        assert counts["orphan"] == 0

    def test_zero_usages_empty_workflow_list(self):
        """When there are no workflows at all, all souls have count 0."""
        soul_repo = Mock()
        workflow_repo = Mock()
        souls = [
            SoulEntity(id="researcher", role="Researcher"),
            SoulEntity(id="editor", role="Editor"),
        ]
        soul_repo.list_all.return_value = souls
        workflow_repo.list_all.return_value = []
        service = SoulService(soul_repo)

        result = service.list_souls(workflow_repo=workflow_repo)

        assert all(s.workflow_count == 0 for s in result)

    def test_workflow_with_no_blocks_section(self):
        """Workflow YAML with no blocks section produces zero soul IDs."""
        wf = workflow_entity(
            "wf_empty",
            "Empty",
            """
workflow:
  name: Empty Workflow
  description: No blocks here
""",
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        assert result == []

    def test_workflow_with_none_yaml(self):
        """Workflow with None yaml produces zero soul IDs."""
        wf = workflow_entity("wf_none", "No YAML", None)
        result = SoulService._extract_workflow_soul_ids(wf)
        assert result == []

    def test_workflow_with_malformed_yaml_skipped(self):
        """Malformed YAML is skipped gracefully, returning empty list."""
        wf = workflow_entity("wf_bad", "Broken", "blocks: [broken yaml {{{")
        result = SoulService._extract_workflow_soul_ids(wf)
        assert result == []

    def test_deduplication_within_single_workflow(self):
        """Same soul_ref appearing in multiple blocks of one workflow is deduplicated
        in the extraction (appears once in the ID list)."""
        wf = workflow_entity(
            "wf_dup",
            "Duplicated Refs",
            """
blocks:
  step1:
    type: linear
    soul_ref: researcher
  step2:
    type: linear
    soul_ref: researcher
  step3:
    type: dispatch
    exits:
      - id: e1
        soul_ref: researcher
""",
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        # Deduplicated: only one entry for 'researcher'
        assert result == ["researcher"]

    def test_get_soul_usages_zero_for_unreferenced_soul(self):
        """get_soul_usages returns empty list when soul exists but is unreferenced."""
        soul_repo, service = make_service()
        workflow_repo = Mock()
        soul_repo.get_by_id.return_value = SoulEntity(id="orphan", role="Orphan")
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Other",
                """
blocks:
  step:
    type: linear
    soul_ref: editor
""",
            ),
        ]

        usages = service.get_soul_usages("orphan", workflow_repo)
        assert usages == []

    def test_get_soul_usages_n_workflows(self):
        """get_soul_usages returns all N workflows referencing the soul."""
        soul_repo, service = make_service()
        workflow_repo = Mock()
        soul_repo.get_by_id.return_value = SoulEntity(id="web_researcher", role="Researcher")
        workflow_repo.list_all.return_value = [
            workflow_entity(
                "wf_1",
                "Pipeline A",
                """
blocks:
  step:
    type: linear
    soul_ref: web_researcher
""",
            ),
            workflow_entity(
                "wf_2",
                "Pipeline B",
                """
blocks:
  step:
    type: linear
    soul_ref: web_researcher
""",
            ),
            workflow_entity(
                "wf_3",
                "Pipeline C",
                """
blocks:
  step:
    type: linear
    soul_ref: editor
""",
            ),
        ]

        usages = service.get_soul_usages("web_researcher", workflow_repo)

        assert len(usages) == 2
        assert usages[0] == {"workflow_id": "wf_1", "workflow_name": "Pipeline A"}
        assert usages[1] == {"workflow_id": "wf_2", "workflow_name": "Pipeline B"}
