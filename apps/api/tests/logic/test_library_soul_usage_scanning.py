"""Library-only soul usage scanning.

Verify that _extract_workflow_soul_ids() and its consumers work correctly
under the library-only model (no inline souls: section in workflows).
"""

import pytest

from tests.logic.soul_service_helpers import (
    make_git_service,
    make_library_usage_service as make_service,
    make_soul_repo,
    make_workflow_repo,
    soul_entity,
    workflow_entity,
)
from tests.logic.soul_usage_fixtures import (
    MALFORMED_BLOCKS_YAML,
    dispatch_exit_yaml,
    legacy_soul_section_yaml,
    linear_and_dispatch_exit_yaml,
    linear_block_without_soul_ref_yaml,
    linear_blocks_yaml,
    no_blocks_yaml,
)
from runsight_api.domain.errors import SoulInUse
from runsight_api.logic.services.soul_service import SoulService


# ---------------------------------------------------------------------------
# Inline souls are ignored for usage scanning
# ---------------------------------------------------------------------------


class TestInlineSoulsIgnoredForUsageScanning:
    """Workflows without a souls: section must still produce correct soul_ref extraction."""

    def test_extract_soul_ids_without_souls_section(self):
        """Library-only YAML (no souls: section) extracts soul_ref values correctly."""
        wf = workflow_entity(
            "wf_library_primary",
            "Library Only",
            linear_blocks_yaml(
                "web_researcher",
                "summarizer",
                block_names=("analyze", "summarize"),
            ),
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
            legacy_soul_section_yaml("legacy_soul", "web_researcher"),
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
            legacy_soul_section_yaml(
                "web_researcher",
                "web_researcher",
                declared_role="Researcher",
                system_prompt=None,
                block_name="research",
            ),
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        assert result == ["web_researcher"]
        # Exactly one entry, not duplicated
        assert len(result) == 1


# ---------------------------------------------------------------------------
# soul_ref values are matched as library ids
# ---------------------------------------------------------------------------


class TestSoulRefSlugUsageMatching:
    """soul_ref: web_researcher increments web_researcher.yaml usage count."""

    def test_soul_ref_matches_library_slug_in_workflow_count(self):
        """soul_ref: web_researcher must map to the soul with id='web_researcher',
        which corresponds to custom/souls/web_researcher.yaml."""
        souls = [
            soul_entity("web_researcher", name="Researcher", role="Researcher"),
            soul_entity("editor", name="Editor", role="Editor"),
        ]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Research Pipeline",
                    linear_blocks_yaml("web_researcher"),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        web_researcher = next(s for s in result if s.id == "web_researcher")
        editor = next(s for s in result if s.id == "editor")
        assert web_researcher.workflow_count == 1
        assert editor.workflow_count == 0

    def test_soul_ref_slug_exact_match_not_substring(self):
        """soul_ref: 'researcher' must NOT count for soul id 'web_researcher'."""
        souls = [
            soul_entity("web_researcher", name="Web Researcher", role="Web Researcher"),
            soul_entity("researcher", name="Researcher", role="Researcher"),
        ]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Research",
                    linear_blocks_yaml("researcher"),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        web_researcher = next(s for s in result if s.id == "web_researcher")
        researcher = next(s for s in result if s.id == "researcher")
        assert web_researcher.workflow_count == 0
        assert researcher.workflow_count == 1

    def test_soul_ref_in_exit_counts_as_library_slug(self):
        """soul_ref inside exits[] also maps to library soul slugs."""
        souls = [soul_entity("web_researcher", name="Researcher", role="Researcher")]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_dispatch",
                    "Dispatch",
                    dispatch_exit_yaml("web_researcher"),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        web_researcher = result[0]
        assert web_researcher.workflow_count == 1

    def test_soul_ref_does_not_match_filename_stem_when_yaml_id_differs(self):
        """Workflow soul_ref values match embedded soul ids only."""
        souls = [soul_entity("researcher_1", name="Researcher", role="Researcher")]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Research",
                    linear_blocks_yaml("researcher"),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        assert result[0].workflow_count == 0


# ---------------------------------------------------------------------------
# Delete pre-check lists correct workflows for a library soul
# ---------------------------------------------------------------------------


class TestSoulDeletePreCheck:
    """get_soul_usages() returns workflows that reference the soul via soul_ref slug."""

    def test_get_soul_usages_lists_referencing_workflows(self):
        """Delete pre-check correctly identifies all workflows using a soul."""
        soul_repo, service = make_service()
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Pipeline A",
                    linear_blocks_yaml("web_researcher"),
                ),
                workflow_entity(
                    "wf_library_secondary",
                    "Pipeline B",
                    linear_blocks_yaml("editor"),
                ),
                workflow_entity(
                    "wf_library_tertiary",
                    "Pipeline C",
                    linear_and_dispatch_exit_yaml("web_researcher", "web_researcher"),
                ),
            ]
        )
        soul_repo.get_by_id.return_value = soul_entity(
            "web_researcher", name="Researcher", role="Researcher"
        )

        usages = service.get_soul_usages("web_researcher", workflow_repo)

        workflow_ids = [u["workflow_id"] for u in usages]
        assert "wf_library_primary" in workflow_ids
        assert "wf_library_secondary" not in workflow_ids
        assert "wf_library_tertiary" in workflow_ids
        assert len(usages) == 2

    def test_get_soul_usages_does_not_match_filename_stem_when_yaml_id_differs(self):
        """Usage scanning uses embedded soul ids only."""
        soul_repo, service = make_service()
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Research Pipeline",
                    linear_blocks_yaml("researcher"),
                ),
            ]
        )
        soul_repo.get_by_id.return_value = soul_entity(
            "researcher_1", name="Researcher", role="Researcher"
        )

        usages = service.get_soul_usages("researcher_1", workflow_repo)

        assert usages == []

    def test_delete_blocked_when_soul_in_use_library_only(self):
        """Delete is blocked with SoulInUse when library soul is referenced."""
        soul_repo = make_soul_repo(
            get_by_id=soul_entity("web_researcher", name="Researcher", role="Researcher")
        )
        git_service = make_git_service()
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Research Pipeline",
                    linear_blocks_yaml("web_researcher", block_names=("research",)),
                ),
            ]
        )
        service = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(SoulInUse) as exc_info:
            service.delete_soul("web_researcher", workflow_repo=workflow_repo)

        details = exc_info.value.to_dict()["details"]
        assert len(details["usages"]) == 1
        assert details["usages"][0]["workflow_id"] == "wf_library_primary"
        assert details["usages"][0]["workflow_name"] == "Research Pipeline"

    def test_delete_allowed_when_soul_not_referenced(self):
        """Delete succeeds when no workflow references the soul."""
        soul_repo = make_soul_repo(get_by_id=soul_entity("orphan", name="Orphan", role="Orphan"))
        git_service = make_git_service()
        soul_repo.delete.return_value = True
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Other",
                    linear_blocks_yaml("editor", block_names=("step",)),
                ),
            ]
        )
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
            linear_blocks_yaml("deleted_soul", block_names=("step",)),
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        assert "deleted_soul" in result


# ---------------------------------------------------------------------------
# Usage counts across zero, one, and many workflows
# ---------------------------------------------------------------------------


class TestSoulUsageCountVariants:
    """Tests for 0, 1, and N usages across multiple workflows."""

    def test_zero_usages(self):
        """Soul with zero references across all workflows has count 0."""
        souls = [soul_entity("unused_soul", name="Unused", role="Unused")]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Workflow A",
                    linear_blocks_yaml("other_soul", block_names=("step",)),
                ),
                workflow_entity(
                    "wf_library_secondary",
                    "Workflow B",
                    linear_block_without_soul_ref_yaml(),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        assert result[0].workflow_count == 0

    def test_one_usage_single_workflow(self):
        """Soul referenced in exactly one workflow has count 1."""
        souls = [soul_entity("web_researcher", name="Researcher", role="Researcher")]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Single Use",
                    linear_blocks_yaml("web_researcher", block_names=("step",)),
                ),
                workflow_entity(
                    "wf_library_secondary",
                    "No Use",
                    linear_blocks_yaml("other", block_names=("step",)),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        assert result[0].workflow_count == 1

    def test_n_usages_across_multiple_workflows(self):
        """Soul referenced across N workflows has count N (workflow-level, not block-level)."""
        souls = [soul_entity("web_researcher", name="Researcher", role="Researcher")]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Pipeline A",
                    linear_blocks_yaml("web_researcher", "web_researcher"),
                ),
                workflow_entity(
                    "wf_library_secondary",
                    "Pipeline B",
                    linear_blocks_yaml("web_researcher"),
                ),
                workflow_entity(
                    "wf_library_tertiary",
                    "Pipeline C",
                    dispatch_exit_yaml("web_researcher", exit_id="e1", label=None, task=None),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        # Count is per-workflow, not per-block. 3 workflows reference it.
        assert result[0].workflow_count == 3

    def test_multiple_souls_mixed_usage_counts(self):
        """Multiple souls with varying usage counts across multiple workflows."""
        souls = [
            soul_entity("researcher", name="Researcher", role="Researcher"),
            soul_entity("editor", name="Editor", role="Editor"),
            soul_entity("reviewer", name="Reviewer", role="Reviewer"),
            soul_entity("orphan", name="Orphan", role="Orphan"),
        ]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Full Pipeline",
                    linear_blocks_yaml(
                        "researcher",
                        "editor",
                        "reviewer",
                        block_names=("research", "edit", "review"),
                    ),
                ),
                workflow_entity(
                    "wf_library_secondary",
                    "Review Only",
                    linear_blocks_yaml("reviewer", block_names=("review",)),
                ),
                workflow_entity(
                    "wf_library_tertiary",
                    "Research Only",
                    linear_blocks_yaml("researcher", block_names=("research",)),
                ),
            ]
        )
        service = SoulService(soul_repo)
        result = service.list_souls(workflow_repo=workflow_repo)

        counts = {s.id: s.workflow_count for s in result}
        assert counts["researcher"] == 2
        assert counts["editor"] == 1
        assert counts["reviewer"] == 2
        assert counts["orphan"] == 0

    def test_zero_usages_empty_workflow_list(self):
        """When there are no workflows at all, all souls have count 0."""
        souls = [
            soul_entity("researcher", name="Researcher", role="Researcher"),
            soul_entity("editor", name="Editor", role="Editor"),
        ]
        soul_repo = make_soul_repo(souls=souls)
        workflow_repo = make_workflow_repo([])
        service = SoulService(soul_repo)

        result = service.list_souls(workflow_repo=workflow_repo)

        assert all(s.workflow_count == 0 for s in result)

    def test_workflow_with_no_blocks_section(self):
        """Workflow YAML with no blocks section produces zero soul IDs."""
        wf = workflow_entity(
            "wf_empty",
            "Empty",
            no_blocks_yaml(name="Empty Workflow", description="No blocks here"),
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
        wf = workflow_entity("wf_bad", "Broken", MALFORMED_BLOCKS_YAML)
        result = SoulService._extract_workflow_soul_ids(wf)
        assert result == []

    def test_deduplication_within_single_workflow(self):
        """Same soul_ref appearing in multiple blocks of one workflow is deduplicated
        in the extraction (appears once in the ID list)."""
        wf = workflow_entity(
            "wf_dup",
            "Duplicated Refs",
            linear_and_dispatch_exit_yaml("researcher", "researcher", dispatch_block_name="step3"),
        )
        result = SoulService._extract_workflow_soul_ids(wf)
        # Deduplicated: only one entry for 'researcher'
        assert result == ["researcher"]

    def test_get_soul_usages_zero_for_unreferenced_soul(self):
        """get_soul_usages returns empty list when soul exists but is unreferenced."""
        soul_repo, service = make_service()
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Other",
                    linear_blocks_yaml("editor", block_names=("step",)),
                ),
            ]
        )
        soul_repo.get_by_id.return_value = soul_entity("orphan", name="Orphan", role="Orphan")

        usages = service.get_soul_usages("orphan", workflow_repo)
        assert usages == []

    def test_get_soul_usages_n_workflows(self):
        """get_soul_usages returns all N workflows referencing the soul."""
        soul_repo, service = make_service()
        workflow_repo = make_workflow_repo(
            [
                workflow_entity(
                    "wf_library_primary",
                    "Pipeline A",
                    linear_blocks_yaml("web_researcher", block_names=("step",)),
                ),
                workflow_entity(
                    "wf_library_secondary",
                    "Pipeline B",
                    linear_blocks_yaml("web_researcher", block_names=("step",)),
                ),
                workflow_entity(
                    "wf_library_tertiary",
                    "Pipeline C",
                    linear_blocks_yaml("editor", block_names=("step",)),
                ),
            ]
        )
        soul_repo.get_by_id.return_value = soul_entity(
            "web_researcher", name="Researcher", role="Researcher"
        )

        usages = service.get_soul_usages("web_researcher", workflow_repo)

        assert len(usages) == 2
        assert usages[0] == {"workflow_id": "wf_library_primary", "workflow_name": "Pipeline A"}
        assert usages[1] == {"workflow_id": "wf_library_secondary", "workflow_name": "Pipeline B"}
