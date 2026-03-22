"""Tests for RUN-247: Log swallowed exception in POST /runs endpoint.

These tests verify that the except block in create_run uses
logger.exception() instead of a bare `pass`, includes the run ID
in the log message, and still returns the run (fire-and-forget).
"""

import ast
from pathlib import Path

# Path to the source file under test
RUNS_ROUTER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "runsight_api"
    / "transport"
    / "routers"
    / "runs.py"
)


def _parse_create_run_function() -> ast.FunctionDef:
    """Parse runs.py and return the AST node for create_run."""
    source = RUNS_ROUTER_PATH.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_run":
            return node
    raise AssertionError("create_run function not found in runs.py")


def _find_except_handlers(func_node: ast.AsyncFunctionDef) -> list[ast.ExceptHandler]:
    """Return all ExceptHandler nodes inside the given function."""
    handlers = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.ExceptHandler):
            handlers.append(node)
    return handlers


class TestExceptionLogging:
    """AC: Swallowed exception is logged with logger.exception()."""

    def test_except_block_does_not_use_bare_pass(self):
        """The except block must NOT be a bare `pass` statement."""
        func = _parse_create_run_function()
        handlers = _find_except_handlers(func)
        assert len(handlers) > 0, "Expected at least one except handler in create_run"

        for handler in handlers:
            # A bare pass is a single-statement body with just Pass
            is_bare_pass = len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)
            assert not is_bare_pass, (
                "except block contains bare `pass` — "
                "exception must be logged with logger.exception()"
            )

    def test_except_block_calls_logger_exception(self):
        """The except block must call logger.exception()."""
        func = _parse_create_run_function()
        handlers = _find_except_handlers(func)
        assert len(handlers) > 0

        found_logger_exception = False
        for handler in handlers:
            for node in ast.walk(handler):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "exception"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "logger"
                ):
                    found_logger_exception = True

        assert found_logger_exception, (
            "except block must call logger.exception() to log the swallowed error"
        )


class TestLogMessageIncludesRunId:
    """AC: Log message includes the run ID."""

    def test_logger_exception_references_run_id(self):
        """The logger.exception() call must reference run.id in its arguments."""
        func = _parse_create_run_function()
        handlers = _find_except_handlers(func)
        assert len(handlers) > 0

        for handler in handlers:
            for node in ast.walk(handler):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "exception"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "logger"
                ):
                    # Check that run.id appears somewhere in the call arguments
                    call_source = ast.dump(node)
                    assert "run" in call_source and "id" in call_source, (
                        "logger.exception() call must reference the run ID "
                        "(e.g., run.id) so errors can be traced to a specific run"
                    )
                    return

        raise AssertionError("No logger.exception() call found — cannot verify run ID reference")


class TestFireAndForgetPreserved:
    """AC: Run is still returned to client (fire-and-forget preserved)."""

    def test_except_block_does_not_reraise(self):
        """The except handler must NOT re-raise the exception."""
        func = _parse_create_run_function()
        handlers = _find_except_handlers(func)
        assert len(handlers) > 0

        for handler in handlers:
            for node in ast.walk(handler):
                if isinstance(node, ast.Raise):
                    raise AssertionError(
                        "except block re-raises the exception — "
                        "fire-and-forget pattern requires the run to be returned"
                    )

    def test_create_run_returns_after_except(self):
        """create_run must have a return statement after the try/except block."""
        func = _parse_create_run_function()

        # Find return statements at the top level of the function body
        has_return = False
        for node in func.body:
            if isinstance(node, ast.Return):
                has_return = True
                break
        # Also check after the try block
        found_try = False
        for node in func.body:
            if isinstance(node, ast.Try):
                found_try = True
                continue
            if found_try and isinstance(node, ast.Return):
                has_return = True
                break

        assert has_return, "create_run must return the RunResponse after the try/except block"
