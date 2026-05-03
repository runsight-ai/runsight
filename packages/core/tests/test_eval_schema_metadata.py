"""Workflow schema behavior for optional eval metadata."""

from __future__ import annotations

import json

import pytest
import runsight_core.yaml.parser  # noqa: F401
import yaml
from eval_fixture_helpers import eval_fixture_text
from runsight_core.eval.runner import run_eval
from runsight_core.yaml.schema import EvalSectionDef, RunsightWorkflowFile

NORMAL_EXECUTION_WITH_EVAL_YAML = eval_fixture_text("normal-execution-ignores-eval.yaml")
MINIMAL_WORKFLOW_NO_EVAL = eval_fixture_text("minimal-workflow-no-eval.yaml")
FIXTURE_TRANSFORM_YAML = eval_fixture_text("fixture-transform-pipeline.yaml")
MIXED_CASE_YAML = eval_fixture_text("mixed-case-eval.yaml")


def test_workflow_file_accepts_eval_section_without_changing_workflow_fields() -> None:
    raw_with = yaml.safe_load(NORMAL_EXECUTION_WITH_EVAL_YAML)
    raw_without = yaml.safe_load(NORMAL_EXECUTION_WITH_EVAL_YAML)
    del raw_without["eval"]

    wf_with = RunsightWorkflowFile.model_validate(raw_with)
    wf_without = RunsightWorkflowFile.model_validate(raw_without)

    assert isinstance(wf_with.eval, EvalSectionDef)
    assert wf_with.eval.cases[0].id == "eval_only_case"
    assert wf_with.workflow.name == wf_without.workflow.name
    assert wf_with.workflow.entry == wf_without.workflow.entry
    assert len(wf_with.workflow.transitions) == len(wf_without.workflow.transitions)
    assert wf_with.souls.keys() == wf_without.souls.keys()


def test_eval_section_is_optional_for_existing_workflow_yaml() -> None:
    raw = yaml.safe_load(MINIMAL_WORKFLOW_NO_EVAL)

    wf_file = RunsightWorkflowFile.model_validate(raw)

    assert wf_file.workflow.name == "no_eval_workflow"
    assert wf_file.eval is None
    assert not isinstance(wf_file.eval, EvalSectionDef)


@pytest.mark.asyncio
async def test_run_eval_does_not_mutate_yaml_or_eval_model() -> None:
    raw_before = yaml.safe_load(FIXTURE_TRANSFORM_YAML)
    before_snapshot = json.dumps(raw_before, sort_keys=True)
    mixed_raw = yaml.safe_load(MIXED_CASE_YAML)
    eval_before = EvalSectionDef.model_validate(mixed_raw["eval"])

    await run_eval(FIXTURE_TRANSFORM_YAML)
    await run_eval(MIXED_CASE_YAML)

    assert json.dumps(yaml.safe_load(FIXTURE_TRANSFORM_YAML), sort_keys=True) == before_snapshot
    eval_after = EvalSectionDef.model_validate(mixed_raw["eval"])
    assert eval_before == eval_after
