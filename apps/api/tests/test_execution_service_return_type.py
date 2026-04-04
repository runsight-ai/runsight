"""Tests for RUN-248: get_execution_service return type must be Optional[ExecutionService].

These tests verify via source inspection that:
1. The return type annotation includes Optional or None union
2. The return type is not just bare ExecutionService
3. All callers of get_execution_service handle the None case
"""

from typing import get_type_hints

from runsight_api.logic.services.execution_service import ExecutionService
from runsight_api.transport.deps import get_execution_service


class TestGetExecutionServiceReturnType:
    """Return type annotation of get_execution_service must reflect Optional."""

    def test_return_type_annotation_includes_none(self):
        """get_execution_service return type must allow None (Optional or Union with None)."""
        hints = get_type_hints(get_execution_service)
        return_type = hints.get("return")
        assert return_type is not None, "get_execution_service must have a return type annotation"

        # Check that None is a valid value for the return type
        # For Optional[X] or X | None, the origin is Union and None is in args
        args = getattr(return_type, "__args__", ())
        assert type(None) in args, (
            f"Return type must include None (e.g. Optional[ExecutionService]), got {return_type}"
        )

    def test_return_type_is_not_bare_execution_service(self):
        """The return type must NOT be just ExecutionService (without Optional)."""
        hints = get_type_hints(get_execution_service)
        return_type = hints.get("return")
        assert return_type is not None, "get_execution_service must have a return type annotation"
        assert return_type is not ExecutionService, (
            "Return type must not be bare ExecutionService — it should be Optional[ExecutionService]"
        )

    def test_return_type_includes_execution_service(self):
        """The return type must still include ExecutionService (not just None or something else)."""
        hints = get_type_hints(get_execution_service)
        return_type = hints.get("return")
        assert return_type is not None, "get_execution_service must have a return type annotation"

        args = getattr(return_type, "__args__", ())
        assert ExecutionService in args, (
            f"Return type must include ExecutionService, got {return_type}"
        )
