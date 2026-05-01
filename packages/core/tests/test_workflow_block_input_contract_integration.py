"""WorkflowBlock integration tests for the public input contract."""

from __future__ import annotations

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


def _analysis_workflow_file(name: str = "registry_analysis_workflow") -> RunsightWorkflowFile:
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
            "blocks": {"analysis_step": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": name,
                "entry": "analysis_step",
                "transitions": [{"from": "analysis_step", "to": None}],
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
                "workflow_ref": "analysis_pipeline",
                "inputs": {"task": "task.id"},
                "outputs": {"results.out": "results.summary"},
                "max_depth": 8,
            }
        )

        assert block_def.type == "workflow"
        assert block_def.workflow_ref == "analysis_pipeline"
        assert block_def.inputs == {"task": "task.id"}
        assert block_def.outputs == {"results.out": "results.summary"}
        assert block_def.max_depth == 8

    def test_schema_rejects_public_output_names_until_output_contract_exists(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="child source path|output contract|dotted"):
            adapter.validate_python(
                {
                    "type": "workflow",
                    "workflow_ref": "analysis_pipeline",
                    "outputs": {"results.out": "summary"},
                }
            )


class TestParserRegistryIntegration:
    def test_parser_requires_registry_for_workflow_blocks(self) -> None:
        yaml_dict = {
            "version": "1.0",
            "id": "missing-analysis-registry-parent",
            "kind": "workflow",
            "blocks": {
                "missing_analysis_workflow_block": {
                    "type": "workflow",
                    "workflow_ref": "missing_analysis_workflow",
                }
            },
            "workflow": {
                "name": "missing_analysis_parent_workflow",
                "entry": "missing_analysis_workflow_block",
                "transitions": [{"from": "missing_analysis_workflow_block", "to": None}],
            },
        }

        with pytest.raises(ValueError, match="registry|WorkflowRegistry"):
            parse_workflow_yaml(yaml_dict)

    def test_parser_resolves_workflow_from_registry_without_child_interface(self) -> None:
        analysis_workflow_file = _analysis_workflow_file()
        registry = WorkflowRegistry()
        registry.register("registry_analysis_workflow", analysis_workflow_file)

        parent_dict = {
            "version": "1.0",
            "id": "analysis-registry-parent",
            "kind": "workflow",
            "blocks": {
                "invoke_analysis": {
                    "type": "workflow",
                    "workflow_ref": "registry_analysis_workflow",
                    "inputs": {"topic": "shared_memory.research_topic"},
                    "outputs": {"results.analysis": "results.analysis_step"},
                }
            },
            "workflow": {
                "name": "analysis_parent_workflow",
                "entry": "invoke_analysis",
                "transitions": [{"from": "invoke_analysis", "to": None}],
            },
        }

        parent_workflow = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        assert isinstance(parent_workflow, Workflow)
        block = parent_workflow._blocks["invoke_analysis"]
        assert isinstance(block, WorkflowBlock)
        assert block.child_workflow.name == "registry_analysis_workflow"
        assert block.inputs == {"topic": "shared_memory.research_topic"}
        assert block.outputs == {"results.analysis": "results.analysis_step"}


class TestParserMaxDepthResolution:
    def test_block_level_max_depth_overrides_global(self) -> None:
        analysis_workflow_file = _analysis_workflow_file("block_depth_analysis_workflow")
        registry = WorkflowRegistry()
        registry.register("block_depth_analysis_workflow", analysis_workflow_file)

        parent_dict = {
            "version": "1.0",
            "id": "block-depth-parent",
            "kind": "workflow",
            "config": {"max_workflow_depth": 12},
            "blocks": {
                "block_depth_workflow_block": {
                    "type": "workflow",
                    "workflow_ref": "block_depth_analysis_workflow",
                    "max_depth": 5,
                }
            },
            "workflow": {
                "name": "block_depth_parent_workflow",
                "entry": "block_depth_workflow_block",
                "transitions": [{"from": "block_depth_workflow_block", "to": None}],
            },
        }

        wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        assert wf._blocks["block_depth_workflow_block"].max_depth == 5

    def test_global_config_used_when_no_block_level(self) -> None:
        analysis_workflow_file = _analysis_workflow_file("global_depth_analysis_workflow")
        registry = WorkflowRegistry()
        registry.register("global_depth_analysis_workflow", analysis_workflow_file)

        parent_dict = {
            "version": "1.0",
            "id": "global-depth-parent",
            "kind": "workflow",
            "config": {"max_workflow_depth": 7},
            "blocks": {
                "global_depth_workflow_block": {
                    "type": "workflow",
                    "workflow_ref": "global_depth_analysis_workflow",
                }
            },
            "workflow": {
                "name": "global_depth_parent_workflow",
                "entry": "global_depth_workflow_block",
                "transitions": [{"from": "global_depth_workflow_block", "to": None}],
            },
        }

        wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        assert wf._blocks["global_depth_workflow_block"].max_depth == 7


@pytest.mark.asyncio
class TestWorkflowBlockErrorHandling:
    async def test_invalid_input_mapping_path_raises_at_runtime(self) -> None:
        analysis_workflow_file = _analysis_workflow_file("invalid_mapping_analysis_workflow")
        registry = WorkflowRegistry()
        registry.register("invalid_mapping_analysis_workflow", analysis_workflow_file)

        parent_dict = {
            "version": "1.0",
            "id": "invalid-input-parent",
            "kind": "workflow",
            "blocks": {
                "invalid_input_mapping_workflow_block": {
                    "type": "workflow",
                    "workflow_ref": "invalid_mapping_analysis_workflow",
                    "inputs": {"input": "shared_memory.nonexistent_key"},
                }
            },
            "workflow": {
                "name": "invalid_mapping_parent_workflow",
                "entry": "invalid_input_mapping_workflow_block",
                "transitions": [{"from": "invalid_input_mapping_workflow_block", "to": None}],
            },
        }
        parent_workflow = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        with pytest.raises(KeyError):
            await parent_workflow.run(WorkflowState())


class TestWorkflowWithoutWorkflowBlocks:
    def test_parse_simple_workflow_without_workflow_blocks(self) -> None:
        yaml_dict = {
            "version": "1.0",
            "id": "simple-linear-workflow",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "blocks": {"simple_linear_step": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": "simple_linear_workflow",
                "entry": "simple_linear_step",
                "transitions": [{"from": "simple_linear_step", "to": None}],
            },
        }

        wf = parse_workflow_yaml(yaml_dict)
        assert wf.name == "simple_linear_workflow"
        assert "simple_linear_step" in wf._blocks


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
    def test_external_soul_resolves_for_workflow_with_registry(self, tmp_path: Path) -> None:
        _write_soul_file(
            tmp_path,
            "researcher",
            soul_id="researcher",
            role="Senior Researcher",
            prompt="You research topics.",
        )
        analysis_workflow_file = _analysis_workflow_file()
        registry = WorkflowRegistry()
        registry.register("registry_analysis_workflow", analysis_workflow_file)

        path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            id: external-soul-analysis-parent
            kind: workflow
            blocks:
              invoke_analysis:
                type: workflow
                workflow_ref: registry_analysis_workflow
                inputs:
                  topic: shared_memory.input_topic
                outputs:
                  results.analysis: results.analysis_step
            workflow:
              name: external_soul_analysis_parent_workflow
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
        assert block.child_workflow.name == "registry_analysis_workflow"
