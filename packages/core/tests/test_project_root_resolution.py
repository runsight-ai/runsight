"""
Tests for project root resolution during soul discovery.

- Workflow files under custom/workflows/ must resolve library souls from
    the project root's custom/souls/, not from custom/workflows/custom/souls/.

- Recursive child workflow parsing via WorkflowRegistry must inherit the
    project root so library souls are discoverable from the child context.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from runsight_core.yaml.discovery import resolve_discovery_base_dir
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _setup_project(tmp_path: Path) -> Path:
    """Create a realistic project layout and return the project root."""
    root = tmp_path / "project"

    # Library soul
    _write_file(
        root / "custom" / "souls" / "researcher.yaml",
        """\
        id: researcher
        kind: soul
        name: Senior Researcher
        role: Senior Researcher
        system_prompt: You are an expert researcher.
        """,
    )

    return root


# ===========================================================================
# resolve_discovery_base_dir
# ===========================================================================


class TestFindProjectRoot:
    def test_finds_root_from_workflow_subdir(self, tmp_path):
        root = _setup_project(tmp_path)
        workflows_dir = root / "custom" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        result = Path(resolve_discovery_base_dir(workflows_dir)).resolve()

        assert result == root.resolve()

    def test_finds_root_from_deeply_nested_dir(self, tmp_path):
        root = _setup_project(tmp_path)
        deep = root / "custom" / "workflows" / "nested" / "deep"
        deep.mkdir(parents=True, exist_ok=True)

        result = Path(resolve_discovery_base_dir(deep)).resolve()

        assert result == root.resolve()

    def test_does_not_return_child_dir_as_root(self, tmp_path):
        """When no ancestor has custom/, result is never below start."""
        bare = tmp_path / "isolated" / "no_custom_here"
        bare.mkdir(parents=True)

        result = Path(resolve_discovery_base_dir(bare)).resolve()

        # Result must be start or an ancestor of start, never a child
        assert bare.resolve().is_relative_to(result) or result == bare.resolve()


# ===========================================================================
# parse_workflow_yaml from custom/workflows/ file path
# ===========================================================================


class TestFilePathSoulDiscovery:
    """Parsing a workflow file under custom/workflows/ must discover library
    souls from the project root's custom/souls/, not from the file's parent."""

    def test_workflow_file_in_custom_workflows_resolves_library_soul(self, tmp_path):
        root = _setup_project(tmp_path)

        _write_file(
            root / "custom" / "workflows" / "my_workflow.yaml",
            """\
            version: "1.0"
            id: workflow-file-discovery
            kind: workflow
            blocks:
              research:
                type: linear
                soul_ref: researcher
            workflow:
              id: workflow-file-discovery
              kind: workflow
              name: workflow_file_discovery
              entry: research
              transitions:
                - from: research
                  to: null
            """,
        )

        workflow_path = str(root / "custom" / "workflows" / "my_workflow.yaml")
        wf = parse_workflow_yaml(workflow_path)

        assert wf.name == "workflow_file_discovery"
        inner = getattr(wf.blocks["research"], "inner_block", wf.blocks["research"])
        assert inner.soul.role == "Senior Researcher"

    def test_workflow_file_at_project_root_still_works(self, tmp_path):
        """Sanity check: a workflow YAML at the project root also works."""
        root = _setup_project(tmp_path)

        _write_file(
            root / "root_workflow.yaml",
            """\
            version: "1.0"
            id: root-workflow-discovery
            kind: workflow
            blocks:
              research:
                type: linear
                soul_ref: researcher
            workflow:
              id: root-workflow-discovery
              kind: workflow
              name: root_workflow_discovery
              entry: research
              transitions:
                - from: research
                  to: null
            """,
        )

        wf = parse_workflow_yaml(str(root / "root_workflow.yaml"))
        assert wf.name == "root_workflow_discovery"

    def test_missing_soul_from_custom_workflows_gives_clear_error(self, tmp_path):
        root = _setup_project(tmp_path)

        _write_file(
            root / "custom" / "workflows" / "missing_soul_workflow.yaml",
            """\
            version: "1.0"
            id: missing-soul-workflow
            kind: workflow
            blocks:
              step1:
                type: linear
                soul_ref: nonexistent
            workflow:
              id: missing-soul-workflow
              kind: workflow
              name: missing_soul_workflow
              entry: step1
              transitions:
                - from: step1
                  to: null
            """,
        )

        with pytest.raises(ValueError, match="nonexistent"):
            parse_workflow_yaml(str(root / "custom" / "workflows" / "missing_soul_workflow.yaml"))


# ===========================================================================
# child workflow via registry inherits project root
# ===========================================================================


class TestRegistryChildWorkflowSoulDiscovery:
    """When a parent workflow loads a child via WorkflowRegistry, the child
    must still be able to resolve library souls from the project root."""

    def test_child_workflow_from_registry_resolves_library_souls(self, tmp_path):
        from runsight_core.yaml.registry import WorkflowRegistry
        from runsight_core.yaml.schema import RunsightWorkflowFile

        root = _setup_project(tmp_path)

        # Also add a second soul for the child
        _write_file(
            root / "custom" / "souls" / "writer.yaml",
            """\
            id: writer
            kind: soul
            name: Summary Writer
            role: Summary Writer
            system_prompt: You are a writer.
            """,
        )

        # Child workflow (registered by name, not file path)
        child_yaml = {
            "version": "1.0",
            "id": "child-summary-workflow",
            "kind": "workflow",
            "blocks": {
                "write": {
                    "type": "linear",
                    "soul_ref": "writer",
                }
            },
            "workflow": {
                "name": "child_summary_workflow",
                "entry": "write",
                "transitions": [{"from": "write", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_yaml)

        registry = WorkflowRegistry()
        registry.register("child_pipeline", child_file)

        # Parent workflow referencing child via workflow_ref
        _write_file(
            root / "custom" / "workflows" / "parent.yaml",
            """\
            version: "1.0"
            id: parent-research-workflow
            kind: workflow
            blocks:
              research:
                type: linear
                soul_ref: researcher
              child_step:
                type: workflow
                workflow_ref: child_pipeline
            workflow:
              id: parent-research-workflow
              kind: workflow
              name: parent_research_workflow
              entry: research
              transitions:
                - from: research
                  to: child_step
                - from: child_step
                  to: null
            """,
        )

        wf = parse_workflow_yaml(
            str(root / "custom" / "workflows" / "parent.yaml"),
            workflow_registry=registry,
        )

        assert wf.name == "parent_research_workflow"
        # Parent's soul resolved
        research_block = wf.blocks["research"]
        inner = getattr(research_block, "inner_block", research_block)
        assert inner.soul.role == "Senior Researcher"
        # Child workflow block exists and was parsed
        assert "child_step" in wf.blocks
