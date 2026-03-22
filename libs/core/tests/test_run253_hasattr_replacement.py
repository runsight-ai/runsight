"""
Tests for RUN-253: Replace hasattr pattern with typed BlockResult.output access.

Verifies via source inspection that:
- No `hasattr(*, "output")` patterns remain in blocks/ directory
- `isinstance(*, BlockResult)` is used instead
- `code.py` builder uses typed `CodeBlockDef` param (not `Any`) for `block_def`
- No `hasattr(block_def, "code")` in code.py builder
"""

import ast
import inspect
from pathlib import Path

import pytest

from runsight_core.state import BlockResult


# ==============================================================================
# Helpers
# ==============================================================================

BLOCKS_DIR = Path(__file__).resolve().parent.parent / "src" / "runsight_core" / "blocks"


def _read_source(filename: str) -> str:
    """Read a block source file and return its content."""
    return (BLOCKS_DIR / filename).read_text()


def _find_hasattr_calls(source: str, attr_name: str) -> list[tuple[int, str]]:
    """Return list of (line_number, line_text) for hasattr calls checking `attr_name`."""
    tree = ast.parse(source)
    hits: list[tuple[int, str]] = []
    lines = source.splitlines()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "hasattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == attr_name
        ):
            hits.append((node.lineno, lines[node.lineno - 1].strip()))
    return hits


def _find_isinstance_calls(source: str, type_name: str) -> list[tuple[int, str]]:
    """Return list of (line_number, line_text) for isinstance calls checking `type_name`."""
    tree = ast.parse(source)
    hits: list[tuple[int, str]] = []
    lines = source.splitlines()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Name)
            and node.args[1].id == type_name
        ):
            hits.append((node.lineno, lines[node.lineno - 1].strip()))
    return hits


# ==============================================================================
# Part 1 — No hasattr(*, "output") in blocks/ directory
# ==============================================================================


class TestNoHasattrOutputInBlocks:
    """Ensure zero `hasattr(result, "output")` patterns remain in all block files."""

    @pytest.mark.parametrize(
        "filename",
        ["loop.py", "gate.py", "synthesize.py", "file_writer.py", "code.py"],
    )
    def test_no_hasattr_output_in_file(self, filename: str):
        """File must not contain any `hasattr(*, 'output')` calls."""
        source = _read_source(filename)
        hits = _find_hasattr_calls(source, "output")
        assert hits == [], (
            f"{filename} still contains hasattr(*, 'output') at line(s): "
            + ", ".join(f"{lineno}: {text}" for lineno, text in hits)
        )


class TestIsinstanceBlockResultUsed:
    """Ensure `isinstance(*, BlockResult)` is used in files that previously had hasattr."""

    @pytest.mark.parametrize(
        "filename",
        ["loop.py", "gate.py", "synthesize.py", "file_writer.py", "code.py"],
    )
    def test_isinstance_blockresult_present(self, filename: str):
        """File must contain at least one `isinstance(*, BlockResult)` call."""
        source = _read_source(filename)
        hits = _find_isinstance_calls(source, "BlockResult")
        assert len(hits) >= 1, f"{filename} does not contain any isinstance(*, BlockResult) calls"

    def test_loop_has_two_isinstance_calls(self):
        """loop.py had two hasattr sites — it must now have at least two isinstance calls."""
        source = _read_source("loop.py")
        hits = _find_isinstance_calls(source, "BlockResult")
        assert len(hits) >= 2, (
            f"loop.py should have at least 2 isinstance(*, BlockResult) calls, found {len(hits)}"
        )


# ==============================================================================
# Part 2 — code.py builder uses typed CodeBlockDef parameter
# ==============================================================================


class TestCodeBuilderTypedParam:
    """Ensure the code.py `build()` function uses `CodeBlockDef` instead of `Any`."""

    def test_build_param_is_code_block_def(self):
        """The `block_def` parameter in code.py's build() must be typed as CodeBlockDef."""
        from runsight_core.blocks.code import build, CodeBlockDef

        sig = inspect.signature(build)
        block_def_param = sig.parameters.get("block_def")
        assert block_def_param is not None, "build() must have a 'block_def' parameter"
        assert block_def_param.annotation is CodeBlockDef, (
            f"build()'s block_def should be typed as CodeBlockDef, got {block_def_param.annotation}"
        )

    def test_no_hasattr_block_def_code_in_builder(self):
        """code.py must not contain `hasattr(block_def, 'code')` in the builder."""
        source = _read_source("code.py")
        hits = _find_hasattr_calls(source, "code")
        assert hits == [], "code.py still contains hasattr(*, 'code') at line(s): " + ", ".join(
            f"{lineno}: {text}" for lineno, text in hits
        )


# ==============================================================================
# Part 3 — Behavioral: isinstance works correctly with BlockResult vs non-BlockResult
# ==============================================================================


class TestIsinstanceBehavior:
    """Verify that isinstance(x, BlockResult) correctly distinguishes result types."""

    def test_block_result_is_instance(self):
        """A BlockResult object is recognized by isinstance."""
        result = BlockResult(output="hello")
        assert isinstance(result, BlockResult)

    def test_raw_string_is_not_block_result(self):
        """A raw string is NOT a BlockResult instance."""
        assert not isinstance("hello", BlockResult)

    def test_dict_is_not_block_result(self):
        """A dict is NOT a BlockResult instance."""
        assert not isinstance({"output": "hello"}, BlockResult)

    def test_none_is_not_block_result(self):
        """None is NOT a BlockResult instance."""
        assert not isinstance(None, BlockResult)
