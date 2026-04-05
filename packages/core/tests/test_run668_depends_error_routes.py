"""Failing tests for RUN-668: depends shorthand and error_route plumbing."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


class MockBlock(BaseBlock):
    """Minimal block for Workflow validation tests."""

    async def execute(self, state: WorkflowState) -> WorkflowState:
        return state


def _write_soul_file(base_dir: Path, name: str = "writer") -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(
        dedent(
            """\
            id: writer
            role: Writer
            system_prompt: Write carefully.
            """
        ),
        encoding="utf-8",
    )


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


class TestWorkflowErrorRoutePlumbing:
    """Workflow should store and validate declared error routes."""

    def test_set_error_route_stores_mapping(self):
        wf = Workflow(name="error_routes")
        wf.add_block(MockBlock("risky"))
        wf.add_block(MockBlock("handler"))

        result = wf.set_error_route("risky", "handler")

        assert result is wf
        assert wf._error_routes == {"risky": "handler"}

    def test_validate_rejects_unknown_error_route_target(self):
        wf = Workflow(name="unknown_error_target")
        wf.add_block(MockBlock("risky"))
        wf.set_entry("risky")
        wf.set_error_route("risky", "missing_handler")

        errors = wf.validate()

        assert any(
            "error_route" in error and "missing_handler" in error and "risky" in error
            for error in errors
        )

    def test_error_route_is_ignored_for_cycle_detection(self):
        wf = Workflow(name="error_route_not_a_cycle")
        wf.add_block(MockBlock("fetch"))
        wf.add_block(MockBlock("risky"))
        wf.add_transition("fetch", "risky")
        wf.set_entry("fetch")
        wf.set_error_route("risky", "fetch")

        assert wf.validate() == []


class TestSchemaAcceptsDependsAndErrorRoute:
    """RunsightWorkflowFile should accept the new block-level sugar fields."""

    def test_model_validate_accepts_depends_and_error_route_fields(self):
        file_def = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "fetch"},
                "blocks": {
                    "fetch": {"type": "linear", "soul_ref": "writer"},
                    "analyze": {
                        "type": "linear",
                        "soul_ref": "writer",
                        "depends": "fetch",
                    },
                    "risky": {
                        "type": "linear",
                        "soul_ref": "writer",
                        "error_route": "handler",
                    },
                    "handler": {"type": "linear", "soul_ref": "writer"},
                },
            }
        )

        assert file_def.blocks["analyze"].depends == "fetch"
        assert file_def.blocks["risky"].error_route == "handler"

    def test_model_validate_rejects_blank_depends_string(self):
        with pytest.raises((ValidationError, ValueError), match=r"depends"):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "test", "entry": "fetch"},
                    "blocks": {
                        "fetch": {"type": "linear", "soul_ref": "writer"},
                        "analyze": {
                            "type": "linear",
                            "soul_ref": "writer",
                            "depends": "",
                        },
                    },
                }
            )


class TestDependsParserSugar:
    """Parser should expand depends shorthand into plain transitions."""

    def test_depends_string_expands_to_plain_transition(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
                depends: fetch
            workflow:
              name: depends_single
              entry: fetch
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._transitions["fetch"] == "analyze"

    def test_depends_conflict_with_explicit_transition_raises_enriched_error(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
                depends: fetch
              review:
                type: linear
                soul_ref: writer
            workflow:
              name: depends_conflict
              entry: fetch
              transitions:
                - from: fetch
                  to: review
            """,
        )

        with pytest.raises(
            ValueError,
            match=r"depends.*fetch.*review.*analyze",
        ):
            parse_workflow_yaml(workflow_path)

    def test_depends_list_expands_to_multiple_plain_transitions(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
              summarize:
                type: linear
                soul_ref: writer
                depends:
                  - fetch
                  - analyze
            workflow:
              name: depends_list
              entry: fetch
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._transitions["fetch"] == "summarize"
        assert wf._transitions["analyze"] == "summarize"

    def test_single_item_depends_list_matches_string_form(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
                depends:
                  - fetch
            workflow:
              name: depends_single_list
              entry: fetch
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._transitions["fetch"] == "analyze"


class TestErrorRouteParserPlumbing:
    """Parser should bridge declared error routes onto Workflow storage."""

    def test_error_route_is_stored_on_workflow(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              risky:
                type: linear
                soul_ref: writer
                error_route: handler
              handler:
                type: linear
                soul_ref: writer
            workflow:
              name: error_route_storage
              entry: risky
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._error_routes == {"risky": "handler"}

    def test_error_route_target_must_exist(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              risky:
                type: linear
                soul_ref: writer
                error_route: handler_missing
            workflow:
              name: error_route_missing
              entry: risky
            """,
        )

        with pytest.raises(
            ValueError,
            match=r"error_route.*handler_missing.*unknown",
        ):
            parse_workflow_yaml(workflow_path)

    def test_error_route_does_not_participate_in_cycle_detection(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              risky:
                type: linear
                soul_ref: writer
                error_route: fetch
            workflow:
              name: error_route_cycle_ignore
              entry: fetch
              transitions:
                - from: fetch
                  to: risky
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._transitions == {"fetch": "risky"}
        assert wf._error_routes == {"risky": "fetch"}

    def test_error_route_can_coexist_with_workflow_block_on_error_catch(self):
        child_file = RunsightWorkflowFile.model_validate(
            {
                "version": "1.0",
                "blocks": {
                    "child_step": {
                        "type": "code",
                        "code": "result = 'ok'",
                    }
                },
                "workflow": {
                    "name": "child_workflow",
                    "entry": "child_step",
                    "transitions": [{"from": "child_step", "to": None}],
                },
            }
        )
        registry = WorkflowRegistry()
        registry.register("child_workflow", child_file)

        parent_yaml = {
            "version": "1.0",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                    "on_error": "catch",
                    "error_route": "handler",
                },
                "handler": {
                    "type": "code",
                    "code": "result = 'handled'",
                },
            },
            "workflow": {
                "name": "parent_workflow",
                "entry": "invoke_child",
                "transitions": [
                    {"from": "invoke_child", "to": "handler"},
                    {"from": "handler", "to": None},
                ],
            },
        }

        wf = parse_workflow_yaml(parent_yaml, workflow_registry=registry)

        workflow_block = wf._blocks["invoke_child"]
        assert workflow_block.on_error == "catch"
        assert wf._error_routes == {"invoke_child": "handler"}

    def test_no_depends_or_error_route_is_backward_compatible(self, tmp_path: Path):
        _write_soul_file(tmp_path)
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            blocks:
              fetch:
                type: linear
                soul_ref: writer
              analyze:
                type: linear
                soul_ref: writer
            workflow:
              name: no_sugar
              entry: fetch
              transitions:
                - from: fetch
                  to: analyze
            """,
        )

        wf = parse_workflow_yaml(workflow_path)

        assert wf._transitions == {"fetch": "analyze"}
        assert getattr(wf, "_error_routes", {}) == {}
