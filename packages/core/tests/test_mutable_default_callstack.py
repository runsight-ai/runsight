"""
Tests for RUN-246: Fix mutable default call_stack=[] in WorkflowBlock.execute.

Verifies that:
- The execute method uses None as default for call_stack (not [])
- Source code does not contain the mutable default pattern
- No B006 linter warning (flake8-bugbear mutable default argument)
"""

import inspect

from runsight_core import WorkflowBlock

# ---------------------------------------------------------------------------
# Signature inspection
# ---------------------------------------------------------------------------


class TestCallStackSignatureDefault:
    """call_stack parameter on execute() must default to None, not []."""

    def test_call_stack_default_is_none(self):
        """The default value for call_stack should be None, not a mutable list."""
        sig = inspect.signature(WorkflowBlock.execute)
        param = sig.parameters["call_stack"]
        assert param.default is None, (
            f"Expected call_stack default to be None, got {param.default!r}"
        )

    def test_call_stack_default_is_not_a_list(self):
        """The default value for call_stack must not be a list object."""
        sig = inspect.signature(WorkflowBlock.execute)
        param = sig.parameters["call_stack"]
        assert not isinstance(param.default, list), (
            f"call_stack default is a list ({param.default!r}); "
            "mutable defaults are shared across calls"
        )
