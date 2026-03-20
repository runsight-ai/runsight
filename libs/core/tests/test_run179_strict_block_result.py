"""
Failing tests for RUN-179: Remove auto-coercion validator + backward-compat methods.

These tests assert the DESIRED end state after RUN-179 is implemented:
- WorkflowState rejects raw strings in results (no auto-coercion)
- BlockResult no longer has backward-compat string-protocol methods
- The json.loads monkey-patch shim is removed

All tests in this file are expected to FAIL against the current implementation
because the auto-coercion validator and backward-compat methods still exist.
"""

import pytest


# ==============================================================================
# Strict Typing: WorkflowState rejects raw strings in results
# ==============================================================================


class TestWorkflowStateRejectsRawStrings:
    """After RUN-179, WorkflowState must reject raw strings in results."""

    def test_raw_string_in_results_raises_validation_error(self):
        """WorkflowState(results={"key": "string"}) must raise ValidationError."""
        from pydantic import ValidationError

        from runsight_core.state import WorkflowState

        with pytest.raises(ValidationError):
            WorkflowState(results={"key": "string"})

    def test_block_result_in_results_still_works(self):
        """WorkflowState(results={"key": BlockResult(output="x")}) must work."""
        from runsight_core.state import BlockResult, WorkflowState

        state = WorkflowState(results={"key": BlockResult(output="x")})
        assert isinstance(state.results["key"], BlockResult)
        assert state.results["key"].output == "x"

    def test_empty_results_still_works(self):
        """WorkflowState(results={}) must still work."""
        from runsight_core.state import WorkflowState

        state = WorkflowState(results={})
        assert state.results == {}

    def test_mixed_dict_with_string_raises_validation_error(self):
        """Mixed dict {"a": "string", "b": BlockResult(...)} must raise ValidationError."""
        from pydantic import ValidationError

        from runsight_core.state import BlockResult, WorkflowState

        with pytest.raises(ValidationError):
            WorkflowState(results={"a": "string", "b": BlockResult(output="x")})

    def test_multiple_raw_strings_raise_validation_error(self):
        """Multiple raw string values must all be rejected."""
        from pydantic import ValidationError

        from runsight_core.state import WorkflowState

        with pytest.raises(ValidationError):
            WorkflowState(results={"a": "foo", "b": "bar", "c": "baz"})


# ==============================================================================
# Validator Removal Verification
# ==============================================================================


class TestAutoCoercionValidatorRemoved:
    """Verify the auto-coercion validator method no longer exists on WorkflowState."""

    def test_coerce_validator_method_does_not_exist(self):
        """WorkflowState must NOT have _coerce_str_to_block_result method."""
        from runsight_core.state import WorkflowState

        assert not hasattr(WorkflowState, "_coerce_str_to_block_result"), (
            "_coerce_str_to_block_result validator still exists on WorkflowState — "
            "it should be removed in RUN-179"
        )


# ==============================================================================
# Backward-Compat Method Removal on BlockResult
# ==============================================================================


class TestBlockResultBackwardCompatRemoved:
    """Verify backward-compat string-protocol methods are removed from BlockResult."""

    def test_block_result_has_no_len(self):
        """BlockResult must NOT have a __len__ method (string-protocol shim)."""
        from runsight_core.state import BlockResult

        # BlockResult should not define __len__; the base BaseModel doesn't have it,
        # so if it's absent from BlockResult the hasattr check will be False.
        assert "__len__" not in BlockResult.__dict__, (
            "BlockResult still defines __len__ — "
            "this backward-compat method should be removed in RUN-179"
        )

    def test_block_result_has_no_contains(self):
        """BlockResult must NOT have a __contains__ method (string-protocol shim)."""
        from runsight_core.state import BlockResult

        assert "__contains__" not in BlockResult.__dict__, (
            "BlockResult still defines __contains__ — "
            "this backward-compat method should be removed in RUN-179"
        )

    def test_block_result_has_no_custom_eq(self):
        """BlockResult must NOT have a custom __eq__ that compares with strings."""
        from runsight_core.state import BlockResult

        # After removal, BlockResult("x") == "x" should be False
        # (standard Pydantic __eq__ does not match across types)
        br = BlockResult(output="hello")
        assert br != "hello", (
            "BlockResult still compares equal to a plain string — "
            "the custom __eq__ should be removed in RUN-179"
        )

    def test_block_result_len_call_raises_type_error(self):
        """len(BlockResult(...)) should raise TypeError after __len__ removal."""
        from runsight_core.state import BlockResult

        br = BlockResult(output="hello")
        with pytest.raises(TypeError):
            len(br)

    def test_block_result_contains_raises_type_error(self):
        """'x' in BlockResult(...) should raise TypeError after __contains__ removal."""
        from runsight_core.state import BlockResult

        br = BlockResult(output="hello")
        with pytest.raises(TypeError):
            "hell" in br


# ==============================================================================
# json.loads Monkey-Patch Shim Removal
# ==============================================================================


class TestJsonLoadsShimRemoved:
    """Verify the json.loads monkey-patch for BlockResult is removed."""

    def test_json_loads_with_block_result_raises_type_error(self):
        """json.loads(BlockResult(...)) should raise TypeError after shim removal.

        The monkey-patch made json.loads transparently unwrap BlockResult.
        After removal, passing a non-string to json.loads should fail.
        """
        import json

        from runsight_core.state import BlockResult

        br = BlockResult(output='{"key": "value"}')
        with pytest.raises(TypeError):
            json.loads(br)
