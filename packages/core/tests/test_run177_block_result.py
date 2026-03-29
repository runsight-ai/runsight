"""
Failing tests for RUN-177: BlockResult model + WorkflowState type change.

Tests cover:
- BlockResult model instantiation with required and optional fields
- BlockResult.from_string() convenience constructor
- BlockResult.model_dump() JSON serialization
- BlockResult edge cases (empty string, None metadata)
- BlockResult importability from runsight_core.state and runsight_core
- WorkflowState auto-coercion: str -> BlockResult via field validator
- WorkflowState mixed dict coercion (str + BlockResult values)
- WorkflowState model_copy preserving BlockResult types
- WorkflowState empty results still works
"""

import pytest
from typing import Dict


# ==============================================================================
# BlockResult Model Tests
# ==============================================================================


class TestBlockResultModel:
    """Tests for the BlockResult Pydantic model."""

    def test_block_result_instantiation_with_output_only(self):
        """BlockResult can be created with just the required `output` field."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="hello world")
        assert result.output == "hello world"

    def test_block_result_defaults(self):
        """BlockResult optional fields default to None."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="test")
        assert result.artifact_ref is None
        assert result.artifact_type is None
        assert result.metadata is None

    def test_block_result_with_all_fields(self):
        """BlockResult accepts all fields when provided."""
        from runsight_core.state import BlockResult

        result = BlockResult(
            output="generated text",
            artifact_ref="s3://bucket/artifact.json",
            artifact_type="json",
            metadata={"model": "gpt-4", "tokens": 150},
        )
        assert result.output == "generated text"
        assert result.artifact_ref == "s3://bucket/artifact.json"
        assert result.artifact_type == "json"
        assert result.metadata == {"model": "gpt-4", "tokens": 150}

    def test_block_result_from_string(self):
        """BlockResult.from_string() creates a BlockResult with output set."""
        from runsight_core.state import BlockResult

        result = BlockResult.from_string("hello")
        assert isinstance(result, BlockResult)
        assert result.output == "hello"
        assert result.artifact_ref is None
        assert result.artifact_type is None
        assert result.metadata is None

    def test_block_result_model_dump_is_json_serializable(self):
        """BlockResult.model_dump() returns a JSON-serializable dict."""
        import json
        from runsight_core.state import BlockResult

        result = BlockResult(
            output="test output",
            artifact_ref="ref/path",
            artifact_type="text",
            metadata={"key": "value"},
        )
        dumped = result.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["output"] == "test output"
        assert dumped["artifact_ref"] == "ref/path"
        assert dumped["artifact_type"] == "text"
        assert dumped["metadata"] == {"key": "value"}
        # Must be JSON-serializable without error
        json_str = json.dumps(dumped)
        assert isinstance(json_str, str)

    def test_block_result_empty_string_output(self):
        """BlockResult with empty string output is valid."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="")
        assert result.output == ""

    def test_block_result_metadata_defaults_to_none_not_empty_dict(self):
        """BlockResult.metadata defaults to None, not {}."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="test")
        assert result.metadata is None
        assert result.metadata != {}

    def test_block_result_importable_from_state_module(self):
        """BlockResult is importable from runsight_core.state."""
        from runsight_core.state import BlockResult

        assert BlockResult is not None

    def test_block_result_importable_from_top_level(self):
        """BlockResult is importable from runsight_core (top-level __init__)."""
        from runsight_core import BlockResult

        assert BlockResult is not None


# ==============================================================================
# WorkflowState Auto-Coercion Tests
# ==============================================================================


class TestWorkflowStateAutoCoercion:
    """Tests for the WorkflowState results field auto-coercing str -> BlockResult."""

    def test_string_value_rejected_by_workflow_state(self):
        """WorkflowState(results={"key": "value"}) raises ValidationError after RUN-179."""
        from pydantic import ValidationError

        from runsight_core.state import WorkflowState

        with pytest.raises(ValidationError):
            WorkflowState(results={"key": "value"})

    def test_block_result_value_output_matches(self):
        """state.results['key'].output returns the original string."""
        from runsight_core.state import BlockResult, WorkflowState

        state = WorkflowState(results={"key": BlockResult(output="value")})
        assert state.results["key"].output == "value"

    def test_block_result_value_artifact_ref_is_none(self):
        """state.results['key'].artifact_ref is None for output-only BlockResult."""
        from runsight_core.state import BlockResult, WorkflowState

        state = WorkflowState(results={"key": BlockResult(output="value")})
        assert state.results["key"].artifact_ref is None

    def test_block_result_accepted_directly(self):
        """WorkflowState(results={"key": BlockResult(output="x")}) works."""
        from runsight_core.state import BlockResult, WorkflowState

        br = BlockResult(output="x")
        state = WorkflowState(results={"key": br})
        assert isinstance(state.results["key"], BlockResult)
        assert state.results["key"].output == "x"

    def test_mixed_dict_with_string_rejected(self):
        """Mixed dict with str and BlockResult values raises ValidationError after RUN-179."""
        from pydantic import ValidationError

        from runsight_core.state import BlockResult, WorkflowState

        br = BlockResult(output="x")
        with pytest.raises(ValidationError):
            WorkflowState(results={"a": "string_val", "b": br})

    def test_empty_results_still_works(self):
        """WorkflowState with empty results dict still works after type change."""
        from runsight_core.state import WorkflowState

        state = WorkflowState(results={})
        assert state.results == {}
        # Confirm the results type annotation changed to Dict[str, BlockResult]
        annotation = WorkflowState.model_fields["results"].annotation
        assert annotation is not Dict[str, str], "results should no longer be Dict[str, str]"


# ==============================================================================
# WorkflowState model_copy with BlockResult
# ==============================================================================


class TestWorkflowStateModelCopyWithBlockResult:
    """Tests for model_copy preserving BlockResult in results."""

    def test_model_copy_preserves_block_result_types(self):
        """model_copy(update={...}) preserves BlockResult instances in results."""
        from runsight_core.state import BlockResult, WorkflowState

        br_a = BlockResult(output="output_a", artifact_ref="ref_a")
        state1 = WorkflowState(results={"a": br_a})

        br_b = BlockResult(output="output_b")
        state2 = state1.model_copy(update={"results": {"a": br_a, "b": br_b}})

        # Original unchanged
        assert len(state1.results) == 1
        assert isinstance(state1.results["a"], BlockResult)
        assert state1.results["a"].output == "output_a"
        assert state1.results["a"].artifact_ref == "ref_a"

        # Copy has both
        assert len(state2.results) == 2
        assert isinstance(state2.results["a"], BlockResult)
        assert isinstance(state2.results["b"], BlockResult)
        assert state2.results["b"].output == "output_b"
