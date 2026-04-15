"""
RUN-327 — CodeBlock sandbox hardening tests.

These tests cover:
1. User code that accesses `sys` at runtime gets NameError (sys not available in harness)
2. User code with dict literals `{"key": "value"}` doesn't crash the harness template
3. User code with f-strings containing `{}` works correctly
4. User code with set literals `{1, 2, 3}` works correctly
5. AST validation still catches `import os` (forbidden import)
6. Harness template does not contain `import sys` at module level
"""

import json

import pytest
from conftest import execute_block_for_test
from runsight_core.blocks.code import (
    _HARNESS_TEMPLATE,
    BLOCKED_MODULES,
    CodeBlock,
)
from runsight_core.state import WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> WorkflowState:
    """Create a minimal WorkflowState for tests."""
    defaults = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


# ---------------------------------------------------------------------------
# 1. User code cannot access `sys` at runtime
# ---------------------------------------------------------------------------


class TestSysNotAvailableAtRuntime:
    """Harness must NOT make `sys` available to user code."""

    @pytest.mark.asyncio
    async def test_user_code_accessing_sys_gets_name_error(self):
        """User code that references `sys` should fail at runtime
        because the harness no longer imports sys."""
        code = (
            "def main(data):\n"
            "    try:\n"
            "        _ = sys.path\n"
            "        return {'sys_available': True}\n"
            "    except NameError:\n"
            "        return {'sys_available': False}\n"
        )
        block = CodeBlock("test_sys", code=code)
        state = _make_state()
        new_state = await execute_block_for_test(block, state)
        result = new_state.results["test_sys"]
        parsed = json.loads(result.output)
        assert parsed["sys_available"] is False

    @pytest.mark.asyncio
    async def test_user_code_calling_sys_exit_fails(self):
        """User code calling sys.exit() should error because sys is not
        importable in the sandboxed subprocess (not in allowed_imports)."""
        # sys is in BLOCKED_MODULES, so `import sys` in user code is blocked
        # by AST validation. But the *harness* currently provides it.
        # After the fix, even if user code tries `sys.exit()` without importing,
        # it should get NameError since harness no longer imports sys.
        code = (
            "def main(data):\n"
            "    try:\n"
            "        sys.exit(1)\n"
            "    except NameError:\n"
            "        return {'blocked': True}\n"
        )
        block = CodeBlock("test_sys_exit", code=code)
        state = _make_state()
        new_state = await execute_block_for_test(block, state)
        result = new_state.results["test_sys_exit"]
        parsed = json.loads(result.output)
        assert parsed["blocked"] is True


# ---------------------------------------------------------------------------
# 2. User code with dict literals doesn't crash the harness
# ---------------------------------------------------------------------------


class TestDictLiteralsInUserCode:
    """Dict literals with `{}` must not break harness template expansion."""

    @pytest.mark.asyncio
    async def test_dict_literal_in_user_code(self):
        """Code containing dict literal `{"key": "value"}` must not raise
        KeyError/IndexError during harness template assembly."""
        code = 'def main(data):\n    d = {"key": "value", "count": 42}\n    return d\n'
        block = CodeBlock("test_dict", code=code)
        state = _make_state()
        new_state = await execute_block_for_test(block, state)
        result = new_state.results["test_dict"]
        parsed = json.loads(result.output)
        assert parsed["key"] == "value"
        assert parsed["count"] == 42

    @pytest.mark.asyncio
    async def test_nested_dict_literal(self):
        """Nested dicts with multiple `{}` pairs must work."""
        code = 'def main(data):\n    d = {"outer": {"inner": "val"}}\n    return d\n'
        block = CodeBlock("test_nested_dict", code=code)
        state = _make_state()
        new_state = await execute_block_for_test(block, state)
        result = new_state.results["test_nested_dict"]
        parsed = json.loads(result.output)
        assert parsed["outer"]["inner"] == "val"


# ---------------------------------------------------------------------------
# 3. User code with f-strings containing {} works correctly
# ---------------------------------------------------------------------------


class TestFStringsInUserCode:
    """F-strings with `{}` must not break harness template expansion."""

    @pytest.mark.asyncio
    async def test_fstring_in_user_code(self):
        """Code containing f-string expressions must execute correctly."""
        code = (
            "def main(data):\n"
            '    name = "world"\n'
            '    msg = f"hello {name}"\n'
            '    return {"message": msg}\n'
        )
        block = CodeBlock("test_fstring", code=code)
        state = _make_state()
        new_state = await execute_block_for_test(block, state)
        result = new_state.results["test_fstring"]
        parsed = json.loads(result.output)
        assert parsed["message"] == "hello world"


# ---------------------------------------------------------------------------
# 4. User code with set literals works correctly
# ---------------------------------------------------------------------------


class TestSetLiteralsInUserCode:
    """Set literals with `{}` must not break harness template expansion."""

    @pytest.mark.asyncio
    async def test_set_literal_in_user_code(self):
        """Code containing set literal `{1, 2, 3}` must execute correctly."""
        code = (
            "def main(data):\n"
            "    s = {1, 2, 3}\n"
            '    return {"length": len(s), "items": sorted(list(s))}\n'
        )
        block = CodeBlock("test_set", code=code)
        state = _make_state()
        new_state = await execute_block_for_test(block, state)
        result = new_state.results["test_set"]
        parsed = json.loads(result.output)
        assert parsed["length"] == 3
        assert parsed["items"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 5. AST validation still catches forbidden imports
# ---------------------------------------------------------------------------


class TestASTValidationStillWorks:
    """AST validation must continue to block forbidden imports."""

    def test_import_os_is_blocked(self):
        """import os must be rejected by AST validation."""
        code = "import os\ndef main(data):\n    return {'path': os.getcwd()}\n"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("test_os", code=code)

    def test_import_subprocess_is_blocked(self):
        """import subprocess must be rejected by AST validation."""
        code = "import subprocess\ndef main(data):\n    return {}\n"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("test_subprocess", code=code)

    def test_import_sys_in_user_code_is_blocked(self):
        """import sys in user code must be rejected by AST validation."""
        code = "import sys\ndef main(data):\n    return {}\n"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("test_sys_import", code=code)


# ---------------------------------------------------------------------------
# 6. Harness template does not contain `import sys`
# ---------------------------------------------------------------------------


class TestHarnessTemplateNoSys:
    """The harness template must not import sys at module level."""

    def test_harness_template_does_not_import_sys(self):
        """_HARNESS_TEMPLATE must not contain 'import sys'."""
        # Check both possible forms: `import sys` and `import sys,`
        assert "import sys" not in _HARNESS_TEMPLATE

    def test_sys_in_blocked_modules(self):
        """sys must remain in BLOCKED_MODULES."""
        assert "sys" in BLOCKED_MODULES
