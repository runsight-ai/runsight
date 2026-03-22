"""Tests for RUN-248: get_execution_service return type must be Optional[ExecutionService].

These tests verify via source inspection that:
1. The return type annotation includes Optional or None union
2. The return type is not just bare ExecutionService
3. All callers of get_execution_service handle the None case
"""

import ast
from pathlib import Path
from typing import get_type_hints


from runsight_api.transport.deps import get_execution_service
from runsight_api.logic.services.execution_service import ExecutionService


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


class TestCallersHandleNone:
    """All router functions that depend on get_execution_service must handle None."""

    @staticmethod
    def _get_caller_source(module_path: Path) -> str:
        return module_path.read_text()

    @staticmethod
    def _find_functions_using_execution_service(source: str) -> list[str]:
        """Find function names that have execution_service as a parameter."""
        tree = ast.parse(source)
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    if arg.arg == "execution_service":
                        functions.append(node.name)
        return functions

    @staticmethod
    def _function_has_none_check(source: str, func_name: str) -> bool:
        """Check if a function body contains a None guard for execution_service."""
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                # Check for patterns: `is None`, `is not None`, `if not execution_service`,
                # `if execution_service`
                for child in ast.walk(node):
                    if isinstance(child, ast.Compare):
                        for comparator in child.comparators:
                            if isinstance(comparator, ast.Constant) and comparator.value is None:
                                for op in child.ops:
                                    if isinstance(op, (ast.Is, ast.IsNot)):
                                        # Check if the comparison involves execution_service
                                        if (
                                            isinstance(child.left, ast.Name)
                                            and child.left.id == "execution_service"
                                        ):
                                            return True
                    # Also check: `if execution_service:` or `if not execution_service:`
                    if isinstance(child, ast.If):
                        test = child.test
                        if isinstance(test, ast.Name) and test.id == "execution_service":
                            return True
                        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                            if (
                                isinstance(test.operand, ast.Name)
                                and test.operand.id == "execution_service"
                            ):
                                return True
        return False

    @staticmethod
    def _function_has_optional_type_hint(source: str, func_name: str) -> bool:
        """Check if execution_service parameter has Optional type hint in source."""
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                for arg in node.args.args:
                    if arg.arg == "execution_service" and arg.annotation:
                        ann_source = ast.unparse(arg.annotation)
                        if "Optional" in ann_source or "None" in ann_source:
                            return True
        return False

    def test_runs_router_create_run_handles_none(self):
        """create_run in runs.py must guard against execution_service being None."""
        runs_router_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "runsight_api"
            / "transport"
            / "routers"
            / "runs.py"
        )
        source = self._get_caller_source(runs_router_path)
        callers = self._find_functions_using_execution_service(source)
        assert "create_run" in callers, "create_run should use execution_service"

        has_none_check = self._function_has_none_check(source, "create_run")
        has_optional_hint = self._function_has_optional_type_hint(source, "create_run")
        assert has_none_check or has_optional_hint, (
            "create_run must handle None execution_service (None check or Optional type hint)"
        )

    def test_runs_router_cancel_run_handles_none(self):
        """cancel_run in runs.py must guard against execution_service being None."""
        runs_router_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "runsight_api"
            / "transport"
            / "routers"
            / "runs.py"
        )
        source = self._get_caller_source(runs_router_path)
        callers = self._find_functions_using_execution_service(source)
        assert "cancel_run" in callers, "cancel_run should use execution_service"

        has_none_check = self._function_has_none_check(source, "cancel_run")
        has_optional_hint = self._function_has_optional_type_hint(source, "cancel_run")
        assert has_none_check or has_optional_hint, (
            "cancel_run must handle None execution_service (None check or Optional type hint)"
        )

    def test_sse_stream_handles_none(self):
        """stream_run_events in sse_stream.py must guard against execution_service being None."""
        sse_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "runsight_api"
            / "transport"
            / "routers"
            / "sse_stream.py"
        )
        source = self._get_caller_source(sse_path)
        callers = self._find_functions_using_execution_service(source)
        assert "stream_run_events" in callers, "stream_run_events should use execution_service"

        has_none_check = self._function_has_none_check(source, "stream_run_events")
        has_optional_hint = self._function_has_optional_type_hint(source, "stream_run_events")
        assert has_none_check or has_optional_hint, (
            "stream_run_events must handle None execution_service (None check or Optional type hint)"
        )

    def test_all_callers_use_optional_type_hint(self):
        """Every caller with execution_service parameter should type it as Optional."""
        routers_dir = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "runsight_api"
            / "transport"
            / "routers"
        )
        issues = []
        for py_file in routers_dir.glob("*.py"):
            source = py_file.read_text()
            callers = self._find_functions_using_execution_service(source)
            for func_name in callers:
                has_optional = self._function_has_optional_type_hint(source, func_name)
                if not has_optional:
                    issues.append(f"{py_file.name}::{func_name} lacks Optional type hint")
        assert not issues, (
            "All callers should type execution_service as Optional[ExecutionService]: "
            + "; ".join(issues)
        )
