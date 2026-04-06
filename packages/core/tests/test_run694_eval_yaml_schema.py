"""
Failing tests for RUN-694: Embedded eval: YAML schema section for workflow test cases.

Tests exercise:
- AC1: Valid eval section parses without error and is accessible on the model
- AC2: Invalid eval section raises ValidationError with clear message
- AC3: Missing eval section defaults to None (backward compatible)
- Edge cases: minimal case, multiple cases, bad threshold, empty cases list
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# These imports WILL FAIL until the Green team implements EvalSectionDef / EvalCaseDef.
from runsight_core.yaml.schema import (
    EvalCaseDef,
    EvalSectionDef,
    RunsightWorkflowFile,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid workflow skeleton — reused across tests to satisfy the required
# 'workflow' key without noise.
_MINIMAL_WORKFLOW = {
    "workflow": {"name": "test_wf", "entry": "b1"},
    "blocks": {"b1": {"type": "linear", "soul_ref": "s1"}},
}


def _wf_with_eval(eval_section: dict) -> dict:
    """Return a minimal workflow dict with an eval section merged in."""
    return {**_MINIMAL_WORKFLOW, "eval": eval_section}


# Full eval section matching the ticket schema example.
_FULL_EVAL_SECTION = {
    "threshold": 0.8,
    "cases": [
        {
            "id": "basic_research",
            "description": "Standard research topic produces structured output",
            "inputs": {
                "task_instruction": "Research the impact of LLMs on software development",
            },
            "fixtures": {
                "analyze": "The analysis shows that LLMs have significantly impacted...",
            },
            "expected": {
                "analyze": [
                    {"type": "contains-any", "value": ["LLM", "language model"]},
                    {"type": "word-count", "value": {"min": 150}},
                ],
                "write_summary": [
                    {"type": "is-json"},
                ],
            },
        },
    ],
}


# ===========================================================================
# AC1 — Valid eval section parses correctly
# ===========================================================================


class TestEvalSectionValid:
    """AC1: Given a workflow YAML with an eval: section, it parses without error
    and the eval section is accessible on the workflow file model."""

    def test_full_eval_section_parses(self):
        """The canonical example from the ticket spec parses without error."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert wf.eval is not None

    def test_eval_is_eval_section_def_instance(self):
        """The parsed eval field is an EvalSectionDef instance."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert isinstance(wf.eval, EvalSectionDef)

    def test_threshold_accessible(self):
        """eval.threshold is accessible and has the correct value."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert wf.eval.threshold == 0.8

    def test_cases_accessible(self):
        """eval.cases is a non-empty list."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert len(wf.eval.cases) == 1

    def test_case_is_eval_case_def_instance(self):
        """Each case in eval.cases is an EvalCaseDef instance."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert isinstance(wf.eval.cases[0], EvalCaseDef)

    def test_case_id_accessible(self):
        """eval.cases[0].id is the expected value."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert wf.eval.cases[0].id == "basic_research"

    def test_case_description_accessible(self):
        """eval.cases[0].description is accessible."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert wf.eval.cases[0].description == (
            "Standard research topic produces structured output"
        )

    def test_case_inputs_accessible(self):
        """eval.cases[0].inputs is a dict with the correct keys."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert "task_instruction" in wf.eval.cases[0].inputs

    def test_case_fixtures_accessible(self):
        """eval.cases[0].fixtures is a dict keyed by block_id."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        assert "analyze" in wf.eval.cases[0].fixtures

    def test_case_expected_accessible(self):
        """eval.cases[0].expected is a dict keyed by block_id with assertion lists."""
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(_FULL_EVAL_SECTION))
        expected = wf.eval.cases[0].expected
        assert "analyze" in expected
        assert isinstance(expected["analyze"], list)
        assert len(expected["analyze"]) == 2

    def test_multiple_cases(self):
        """eval.cases can contain multiple test cases."""
        eval_section = {
            "threshold": 0.7,
            "cases": [
                {
                    "id": "case_one",
                    "inputs": {"prompt": "Hello"},
                    "expected": {"b1": [{"type": "contains", "value": "world"}]},
                },
                {
                    "id": "case_two",
                    "inputs": {"prompt": "Goodbye"},
                    "expected": {"b1": [{"type": "contains", "value": "farewell"}]},
                },
            ],
        }
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))
        assert len(wf.eval.cases) == 2
        assert wf.eval.cases[0].id == "case_one"
        assert wf.eval.cases[1].id == "case_two"

    def test_minimal_case_only_required_fields(self):
        """A case with only the required 'id' field and minimal expected parses."""
        eval_section = {
            "cases": [
                {
                    "id": "minimal",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))
        assert wf.eval.cases[0].id == "minimal"

    def test_case_description_is_optional(self):
        """A case without description should parse and default to None."""
        eval_section = {
            "cases": [
                {
                    "id": "no_desc",
                    "inputs": {"x": "y"},
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))
        assert wf.eval.cases[0].description is None

    def test_case_inputs_is_optional(self):
        """A case without inputs should parse and default to None or empty."""
        eval_section = {
            "cases": [
                {
                    "id": "no_inputs",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))
        case = wf.eval.cases[0]
        assert case.inputs is None or case.inputs == {}

    def test_case_fixtures_is_optional(self):
        """A case without fixtures should parse and default to None or empty."""
        eval_section = {
            "cases": [
                {
                    "id": "no_fixtures",
                    "inputs": {"x": "y"},
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))
        case = wf.eval.cases[0]
        assert case.fixtures is None or case.fixtures == {}

    def test_threshold_is_optional(self):
        """An eval section without threshold should parse (threshold defaults or is None)."""
        eval_section = {
            "cases": [
                {
                    "id": "no_threshold",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        wf = RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))
        assert wf.eval is not None


# ===========================================================================
# AC2 — Invalid eval section raises ValidationError
# ===========================================================================


class TestEvalSectionInvalid:
    """AC2: Given a workflow YAML with an invalid eval: section,
    parsing raises ValidationError with a clear message."""

    def test_missing_case_id(self):
        """A case without the required 'id' field raises ValidationError."""
        eval_section = {
            "cases": [
                {
                    "description": "No id",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        with pytest.raises(ValidationError, match="id"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))

    def test_threshold_not_a_number(self):
        """A non-numeric threshold raises ValidationError."""
        eval_section = {
            "threshold": "high",
            "cases": [
                {
                    "id": "bad_threshold",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        with pytest.raises(ValidationError, match="threshold"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))

    def test_threshold_below_zero(self):
        """A threshold < 0 raises ValidationError."""
        eval_section = {
            "threshold": -0.1,
            "cases": [
                {
                    "id": "neg_threshold",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        with pytest.raises(ValidationError, match="threshold"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))

    def test_threshold_above_one(self):
        """A threshold > 1 raises ValidationError."""
        eval_section = {
            "threshold": 1.5,
            "cases": [
                {
                    "id": "high_threshold",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        with pytest.raises(ValidationError, match="threshold"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))

    def test_cases_not_a_list(self):
        """Cases must be a list, not a dict or string."""
        eval_section = {
            "cases": "not_a_list",
        }
        with pytest.raises(ValidationError, match="cases"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))

    def test_empty_cases_list(self):
        """An empty cases list should be rejected (at least one case required)."""
        eval_section = {
            "cases": [],
        }
        with pytest.raises(ValidationError, match="cases"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))

    def test_case_id_not_a_string(self):
        """A numeric case id should raise ValidationError."""
        eval_section = {
            "cases": [
                {
                    "id": 123,
                    "expected": {"b1": [{"type": "is-json"}]},
                },
            ],
        }
        with pytest.raises(ValidationError, match="id"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))

    def test_duplicate_case_ids(self):
        """Two cases with the same id should raise ValidationError."""
        eval_section = {
            "cases": [
                {
                    "id": "dupe",
                    "expected": {"b1": [{"type": "is-json"}]},
                },
                {
                    "id": "dupe",
                    "expected": {"b1": [{"type": "contains", "value": "x"}]},
                },
            ],
        }
        with pytest.raises(ValidationError, match="dupe"):
            RunsightWorkflowFile.model_validate(_wf_with_eval(eval_section))


# ===========================================================================
# AC3 — No eval section -> eval is None (backward compatible)
# ===========================================================================


class TestEvalSectionBackwardCompat:
    """AC3: Given a workflow YAML without eval:, the eval field is None."""

    def test_no_eval_key_returns_none(self):
        """A workflow without eval: parses and eval is None."""
        wf = RunsightWorkflowFile.model_validate(_MINIMAL_WORKFLOW)
        assert wf.eval is None

    def test_existing_workflows_unaffected(self):
        """A workflow with tools and souls but no eval still parses normally."""
        data = {
            **_MINIMAL_WORKFLOW,
            "tools": ["http"],
            "souls": {
                "s1": {
                    "id": "s1",
                    "role": "assistant",
                    "system_prompt": "Be helpful",
                },
            },
        }
        wf = RunsightWorkflowFile.model_validate(data)
        assert wf.eval is None
        assert wf.tools == ["http"]
        assert "s1" in wf.souls


# ===========================================================================
# EvalCaseDef model tests (direct unit tests)
# ===========================================================================


class TestEvalCaseDefDirect:
    """Direct validation of EvalCaseDef model outside the workflow context."""

    def test_valid_case(self):
        """A fully-populated case validates successfully."""
        case = EvalCaseDef.model_validate(
            {
                "id": "test_case",
                "description": "A test case",
                "inputs": {"prompt": "hello"},
                "fixtures": {"b1": "canned output"},
                "expected": {"b1": [{"type": "is-json"}]},
            }
        )
        assert case.id == "test_case"

    def test_case_requires_id(self):
        """EvalCaseDef without id raises ValidationError."""
        with pytest.raises(ValidationError, match="id"):
            EvalCaseDef.model_validate(
                {
                    "description": "missing id",
                    "expected": {"b1": [{"type": "is-json"}]},
                }
            )


# ===========================================================================
# EvalSectionDef model tests (direct unit tests)
# ===========================================================================


class TestEvalSectionDefDirect:
    """Direct validation of EvalSectionDef model outside the workflow context."""

    def test_valid_section(self):
        """A fully-populated eval section validates successfully."""
        section = EvalSectionDef.model_validate(_FULL_EVAL_SECTION)
        assert section.threshold == 0.8
        assert len(section.cases) == 1

    def test_threshold_boundary_zero(self):
        """Threshold of exactly 0 is valid."""
        section = EvalSectionDef.model_validate(
            {
                "threshold": 0.0,
                "cases": [
                    {"id": "t", "expected": {"b1": [{"type": "is-json"}]}},
                ],
            }
        )
        assert section.threshold == 0.0

    def test_threshold_boundary_one(self):
        """Threshold of exactly 1.0 is valid."""
        section = EvalSectionDef.model_validate(
            {
                "threshold": 1.0,
                "cases": [
                    {"id": "t", "expected": {"b1": [{"type": "is-json"}]}},
                ],
            }
        )
        assert section.threshold == 1.0
