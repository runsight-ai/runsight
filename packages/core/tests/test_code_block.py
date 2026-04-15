"""
Tests for CodeBlock — sandboxed Python code execution block.
"""

import json
import textwrap

import pytest
from conftest import execute_block_for_test
from runsight_core import CodeBlock
from runsight_core.state import WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> WorkflowState:
    defaults = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


SIMPLE_CODE = textwrap.dedent("""\
def main(data):
    return {"greeting": "hello " + data["shared_memory"].get("name", "world")}
""")

MATH_CODE = textwrap.dedent("""\
import math
import json
import re

def main(data):
    val = data["shared_memory"].get("x", 9)
    return {"sqrt": math.sqrt(val), "is_digit": bool(re.match(r"^\\d+$", str(val)))}
""")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCodeBlockHappyPath:
    @pytest.mark.asyncio
    async def test_basic_transform(self):
        block = CodeBlock("cb1", SIMPLE_CODE)
        state = _make_state(shared_memory={"name": "alice"})
        result = await execute_block_for_test(block, state)

        assert "cb1" in result.results
        parsed = json.loads(result.results["cb1"].output)
        assert parsed["greeting"] == "hello alice"
        assert any("executed successfully" in m["content"] for m in result.execution_log)

    @pytest.mark.asyncio
    async def test_allowed_imports(self):
        block = CodeBlock("cb2", MATH_CODE)
        state = _make_state(shared_memory={"x": 16})
        result = await execute_block_for_test(block, state)

        assert "cb2" in result.results
        parsed = json.loads(result.results["cb2"].output)
        assert parsed["sqrt"] == 4.0
        assert parsed["is_digit"] is True

    @pytest.mark.asyncio
    async def test_state_not_mutated(self):
        block = CodeBlock("cb3", SIMPLE_CODE)
        state = _make_state(shared_memory={"name": "bob"})
        result = await execute_block_for_test(block, state)

        # Original state unchanged
        assert "cb3" not in state.results
        assert len(state.execution_log) == 0
        # New state has result
        assert "cb3" in result.results

    @pytest.mark.asyncio
    async def test_cost_and_tokens_unchanged(self):
        block = CodeBlock("cb_cost", SIMPLE_CODE)
        state = _make_state(shared_memory={"name": "x"})
        state = state.model_copy(update={"total_cost_usd": 1.5, "total_tokens": 100})
        result = await execute_block_for_test(block, state)

        assert result.total_cost_usd == 1.5
        assert result.total_tokens == 100

    @pytest.mark.asyncio
    async def test_string_return(self):
        code = textwrap.dedent("""\
def main(data):
    return "just a string"
""")
        block = CodeBlock("cb_str", code)
        state = _make_state()
        result = await execute_block_for_test(block, state)
        # String results stored directly
        assert result.results["cb_str"].output == "just a string"


# ---------------------------------------------------------------------------
# AST validation — blocked imports
# ---------------------------------------------------------------------------


class TestCodeBlockASTRejection:
    def test_import_os(self):
        code = "import os\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_from_os_import(self):
        code = "from os import path\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_import_sys(self):
        code = "import sys\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_import_subprocess(self):
        code = "import subprocess\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_import_socket(self):
        code = "import socket\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_import_importlib(self):
        code = "import importlib\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_import(self):
        code = "__import__('os')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_eval_call(self):
        code = "x = eval('1+1')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_exec_call(self):
        code = "exec('pass')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_open_call(self):
        code = "f = open('file')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_compile_call(self):
        code = "compile('pass', '', 'exec')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_unlisted_import(self):
        code = "import requests\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not in the allowed list"):
            CodeBlock("x", code)


# ---------------------------------------------------------------------------
# Empty code / missing main
# ---------------------------------------------------------------------------


class TestCodeBlockValidation:
    def test_empty_code(self):
        with pytest.raises(ValueError, match="empty"):
            CodeBlock("x", "")

    def test_whitespace_only(self):
        with pytest.raises(ValueError, match="empty"):
            CodeBlock("x", "   \n  ")

    def test_missing_main(self):
        with pytest.raises(ValueError, match="main"):
            CodeBlock("x", "def helper(): pass")


# ---------------------------------------------------------------------------
# Runtime errors
# ---------------------------------------------------------------------------


class TestCodeBlockRuntimeErrors:
    @pytest.mark.asyncio
    async def test_timeout_kills_process(self):
        code = textwrap.dedent("""\
def main(data):
    while True:
        pass
""")
        block = CodeBlock("cb_timeout", code, timeout_seconds=1)
        state = _make_state()
        with pytest.raises(TimeoutError, match="timed out"):
            await execute_block_for_test(block, state)

    @pytest.mark.asyncio
    async def test_user_exception_captured(self):
        code = textwrap.dedent("""\
def main(data):
    raise RuntimeError("boom")
""")
        block = CodeBlock("cb_err", code)
        state = _make_state()
        result = await execute_block_for_test(block, state)

        assert "cb_err" in result.results
        assert "Error:" in result.results["cb_err"].output
        assert "boom" in result.results["cb_err"].output

    @pytest.mark.asyncio
    async def test_non_json_return(self):
        code = textwrap.dedent("""\
def main(data):
    return object()
""")
        block = CodeBlock("cb_nonjson", code)
        state = _make_state()
        result = await execute_block_for_test(block, state)

        assert "cb_nonjson" in result.results
        assert "Error" in result.results["cb_nonjson"].output


# ---------------------------------------------------------------------------
# Custom allowed_imports
# ---------------------------------------------------------------------------


class TestCodeBlockCustomImports:
    def test_custom_allowed_imports(self):
        code = textwrap.dedent("""\
import json
def main(data):
    return {}
""")
        # Only allow json, so math would fail
        block = CodeBlock("x", code, allowed_imports=["json"])
        assert block.allowed_imports == ["json"]

    def test_custom_rejects_unlisted(self):
        code = textwrap.dedent("""\
import math
def main(data):
    return {}
""")
        with pytest.raises(ValueError, match="not in the allowed list"):
            CodeBlock("x", code, allowed_imports=["json"])

    def test_custom_allows_extra(self):
        """Custom list can allow modules not in the default list."""
        code = textwrap.dedent("""\
import statistics
def main(data):
    return {}
""")
        # statistics is not in DEFAULT but we allow it
        block = CodeBlock("x", code, allowed_imports=["statistics"])
        assert "statistics" in block.allowed_imports
