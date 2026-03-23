"""
RUN-261: Verify LinearBlock and FanOutBlock have migrated from
direct windowing.prune_messages calls to budget.fit_to_budget().

These tests inspect the source code of linear.py and fanout.py to confirm:
1. No windowing import (post-call pruning removed)
2. Budget module is imported (fit_to_budget or related)
3. fit_to_budget is called in the source
4. prune_messages is not called
5. get_max_tokens is not called
"""

from __future__ import annotations

import importlib
import inspect


def _get_source(module_path: str) -> str:
    """Import a module by dotted path and return its source code."""
    mod = importlib.import_module(module_path)
    return inspect.getsource(mod)


def _get_class_method_source(module_path: str, class_name: str, method_name: str) -> str:
    """Return source of a specific class method."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    method = getattr(cls, method_name)
    return inspect.getsource(method)


# ===========================================================================
# LinearBlock source-level migration checks
# ===========================================================================

LINEAR_MODULE = "runsight_core.blocks.linear"


class TestLinearBlockNoPruneMessages:
    """linear.py must not contain prune_messages calls anywhere."""

    def test_linear_source_does_not_contain_prune_messages(self):
        source = _get_source(LINEAR_MODULE)
        assert "prune_messages" not in source, (
            "linear.py still contains 'prune_messages' — "
            "post-call pruning should be replaced by pre-call fit_to_budget()"
        )


class TestLinearBlockNoGetMaxTokens:
    """linear.py must not contain get_max_tokens calls."""

    def test_linear_source_does_not_contain_get_max_tokens(self):
        source = _get_source(LINEAR_MODULE)
        assert "get_max_tokens" not in source, (
            "linear.py still contains 'get_max_tokens' — "
            "budget manager handles token limits via fit_to_budget()"
        )


class TestLinearBlockNoWindowingImport:
    """linear.py must not import the windowing module."""

    def test_linear_source_does_not_import_windowing(self):
        source = _get_source(LINEAR_MODULE)
        assert "windowing" not in source, (
            "linear.py still references 'windowing' — "
            "all windowing calls should be replaced by budget.fit_to_budget()"
        )


class TestLinearBlockImportsBudget:
    """linear.py must import from the budget module."""

    def test_linear_source_imports_budget(self):
        source = _get_source(LINEAR_MODULE)
        assert "budget" in source, (
            "linear.py does not reference the budget module — "
            "fit_to_budget must be imported from runsight_core.memory.budget"
        )


class TestLinearBlockCallsFitToBudget:
    """linear.py execute() must call fit_to_budget."""

    def test_linear_execute_contains_fit_to_budget(self):
        source = _get_class_method_source(LINEAR_MODULE, "LinearBlock", "execute")
        assert "fit_to_budget" in source, (
            "LinearBlock.execute() does not contain 'fit_to_budget' — "
            "budget fitting must happen before runner.execute_task()"
        )


# ===========================================================================
# FanOutBlock source-level migration checks
# ===========================================================================

FANOUT_MODULE = "runsight_core.blocks.fanout"


class TestFanOutBlockNoPruneMessages:
    """fanout.py must not contain prune_messages calls anywhere."""

    def test_fanout_source_does_not_contain_prune_messages(self):
        source = _get_source(FANOUT_MODULE)
        assert "prune_messages" not in source, (
            "fanout.py still contains 'prune_messages' — "
            "post-call pruning should be replaced by pre-call fit_to_budget()"
        )


class TestFanOutBlockNoGetMaxTokens:
    """fanout.py must not contain get_max_tokens calls."""

    def test_fanout_source_does_not_contain_get_max_tokens(self):
        source = _get_source(FANOUT_MODULE)
        assert "get_max_tokens" not in source, (
            "fanout.py still contains 'get_max_tokens' — "
            "budget manager handles token limits via fit_to_budget()"
        )


class TestFanOutBlockNoWindowingImport:
    """fanout.py must not import the windowing module."""

    def test_fanout_source_does_not_import_windowing(self):
        source = _get_source(FANOUT_MODULE)
        assert "windowing" not in source, (
            "fanout.py still references 'windowing' — "
            "all windowing calls should be replaced by budget.fit_to_budget()"
        )


class TestFanOutBlockImportsBudget:
    """fanout.py must import from the budget module."""

    def test_fanout_source_imports_budget(self):
        source = _get_source(FANOUT_MODULE)
        assert "budget" in source, (
            "fanout.py does not reference the budget module — "
            "fit_to_budget must be imported from runsight_core.memory.budget"
        )


class TestFanOutBlockCallsFitToBudget:
    """fanout.py execute() must call fit_to_budget."""

    def test_fanout_execute_contains_fit_to_budget(self):
        source = _get_class_method_source(FANOUT_MODULE, "FanOutBlock", "execute")
        assert "fit_to_budget" in source, (
            "FanOutBlock.execute() does not contain 'fit_to_budget' — "
            "budget fitting must happen per-soul before runner.execute_task()"
        )
