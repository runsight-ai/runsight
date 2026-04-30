"""End-to-end WorkflowBlock integration tests for the public input contract."""

from __future__ import annotations

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile

_RESEARCHER_SOUL = {
    "researcher": {
        "id": "researcher",
        "kind": "soul",
        "name": "Researcher",
        "role": "Senior Researcher",
        "system_prompt": "You research topics.",
    }
}


def _child_workflow_file(name: str = "analysis_child") -> RunsightWorkflowFile:
    return RunsightWorkflowFile.model_validate(
        {
            "version": "1.0",
            "id": name,
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "inputs": {
                "topic": {"type": "string", "required": False},
                "input": {"type": "string", "required": False},
            },
            "blocks": {"step1": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": name,
                "entry": "step1",
                "transitions": [{"from": "step1", "to": None}],
            },
        }
    )


class TestSchemaParsingIntegration:
    def test_schema_enforces_workflow_ref_requirement(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="workflow_ref"):
            adapter.validate_python({"type": "workflow"})

    def test_schema_allows_workflow_with_contract_fields(self) -> None:
        adapter = TypeAdapter(BlockDef)

        block_def = adapter.validate_python(
            {
                "type": "workflow",
                "workflow_ref": "child_pipeline",
                "inputs": {"task": "task.id"},
                "outputs": {"results.out": "results.summary"},
                "max_depth": 8,
            }
        )

        assert block_def.type == "workflow"
        assert block_def.workflow_ref == "child_pipeline"
        assert block_def.inputs == {"task": "task.id"}
        assert block_def.outputs == {"results.out": "results.summary"}
        assert block_def.max_depth == 8

    def test_schema_rejects_public_output_names_until_output_contract_exists(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="child source path|output contract|dotted"):
            adapter.validate_python(
                {
                    "type": "workflow",
                    "workflow_ref": "child_pipeline",
                    "outputs": {"results.out": "summary"},
                }
            )


class TestParserRegistryIntegration:
    def test_parser_requires_registry_for_workflow_blocks(self) -> None:
        yaml_dict = {
            "version": "1.0",
            "id": "workflow-block-e2e-workflow",
            "kind": "workflow",
            "blocks": {"child_ref": {"type": "workflow", "workflow_ref": "missing_child"}},
            "workflow": {
                "name": "parent",
                "entry": "child_ref",
                "transitions": [{"from": "child_ref", "to": None}],
            },
        }

        with pytest.raises(ValueError, match="registry|WorkflowRegistry"):
            parse_workflow_yaml(yaml_dict)

    def test_parser_resolves_workflow_from_registry_without_child_interface(self) -> None:
        child_file = _child_workflow_file()
        registry = WorkflowRegistry()
        registry.register("analysis_child", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "workflow-block-e2e-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke_analysis": {
                    "type": "workflow",
                    "workflow_ref": "analysis_child",
                    "inputs": {"topic": "shared_memory.research_topic"},
                    "outputs": {"results.analysis": "results.step1"},
                }
            },
            "workflow": {
                "name": "main_workflow",
                "entry": "invoke_analysis",
                "transitions": [{"from": "invoke_analysis", "to": None}],
            },
        }

        parent_workflow = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        assert isinstance(parent_workflow, Workflow)
        block = parent_workflow._blocks["invoke_analysis"]
        assert isinstance(block, WorkflowBlock)
        assert block.child_workflow.name == "analysis_child"
        assert block.inputs == {"topic": "shared_memory.research_topic"}
        assert block.outputs == {"results.analysis": "results.step1"}


class TestParserMaxDepthResolution:
    def test_block_level_max_depth_overrides_global(self) -> None:
        child_file = _child_workflow_file("child-c")
        registry = WorkflowRegistry()
        registry.register("child-c", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "workflow-block-e2e-workflow",
            "kind": "workflow",
            "config": {"max_workflow_depth": 12},
            "blocks": {"invoke": {"type": "workflow", "workflow_ref": "child-c", "max_depth": 5}},
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        assert wf._blocks["invoke"].max_depth == 5

    def test_global_config_used_when_no_block_level(self) -> None:
        child_file = _child_workflow_file("child-c")
        registry = WorkflowRegistry()
        registry.register("child-c", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "workflow-block-e2e-workflow",
            "kind": "workflow",
            "config": {"max_workflow_depth": 7},
            "blocks": {"invoke": {"type": "workflow", "workflow_ref": "child-c"}},
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        assert wf._blocks["invoke"].max_depth == 7


@pytest.mark.asyncio
class TestWorkflowBlockErrorHandling:
    async def test_invalid_input_mapping_path_raises_at_runtime(self) -> None:
        child_file = _child_workflow_file("child-c")
        registry = WorkflowRegistry()
        registry.register("child-c", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "workflow-block-e2e-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "child-c",
                    "inputs": {"input": "shared_memory.nonexistent_key"},
                }
            },
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }
        parent_workflow = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        with pytest.raises(KeyError):
            await parent_workflow.run(WorkflowState())


class TestBackwardCompatibility:
    def test_parse_simple_workflow_without_workflow_blocks(self) -> None:
        yaml_dict = {
            "version": "1.0",
            "id": "workflow-block-e2e-workflow",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "blocks": {"step1": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": "simple",
                "entry": "step1",
                "transitions": [{"from": "step1", "to": None}],
            },
        }

        wf = parse_workflow_yaml(yaml_dict)
        assert wf.name == "simple"
        assert "step1" in wf._blocks


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _write_soul_file(base_dir: Path, name: str, *, soul_id: str, role: str, prompt: str) -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(
        dedent(f"""\
        id: {soul_id}
        kind: soul
        name: {soul_id.capitalize()}
        role: {role}
        system_prompt: {prompt}
        """),
        encoding="utf-8",
    )


class TestExternalSoulFileResolution:
    def test_external_soul_resolves_for_workflow_with_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "researcher",
                soul_id="researcher",
                role="Senior Researcher",
                prompt="You research topics.",
            )
            child_file = _child_workflow_file()
            registry = WorkflowRegistry()
            registry.register("analysis_child", child_file)

            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                id: workflow-block-e2e-workflow
                kind: workflow
                blocks:
                  invoke_analysis:
                    type: workflow
                    workflow_ref: analysis_child
                    inputs:
                      topic: shared_memory.input_topic
                    outputs:
                      results.analysis: results.step1
                workflow:
                  name: main_workflow
                  entry: invoke_analysis
                  transitions:
                    - from: invoke_analysis
                      to: null
                """,
            )

            parent_workflow = parse_workflow_yaml(path, workflow_registry=registry)

            assert isinstance(parent_workflow, Workflow)
            block = parent_workflow._blocks["invoke_analysis"]
            assert isinstance(block, WorkflowBlock)
            assert block.child_workflow.name == "analysis_child"
