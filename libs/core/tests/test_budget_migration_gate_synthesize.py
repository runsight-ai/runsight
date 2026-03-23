"""
RUN-262: Verify GateBlock and SynthesizeBlock have migrated Task construction
to the unified pattern (task.instruction for fixed template, task.context for
variable data) and wire budget manager via fit_to_budget().

These tests inspect the source code of gate.py and synthesize.py to confirm:
1. Budget module is imported (fit_to_budget or related)
2. fit_to_budget is called in the execute() method
3. Task is constructed with a context= parameter (variable data separated)
4. The old pattern of f-string interpolating variable content into instruction is gone
"""

from __future__ import annotations

import importlib
import inspect
import re


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
# GateBlock source-level migration checks
# ===========================================================================

GATE_MODULE = "runsight_core.blocks.gate"


class TestGateBlockImportsBudget:
    """gate.py must import from the budget module."""

    def test_gate_source_imports_budget(self):
        source = _get_source(GATE_MODULE)
        assert "budget" in source, (
            "gate.py does not reference the budget module — "
            "fit_to_budget must be imported from runsight_core.memory.budget"
        )


class TestGateBlockCallsFitToBudget:
    """gate.py execute() must call fit_to_budget."""

    def test_gate_execute_contains_fit_to_budget(self):
        source = _get_class_method_source(GATE_MODULE, "GateBlock", "execute")
        assert "fit_to_budget" in source, (
            "GateBlock.execute() does not contain 'fit_to_budget' — "
            "budget fitting must happen before runner.execute_task()"
        )


class TestGateBlockUsesTaskContext:
    """GateBlock must construct Task with context= for variable content."""

    def test_gate_execute_constructs_task_with_context(self):
        source = _get_class_method_source(GATE_MODULE, "GateBlock", "execute")
        # Look for Task(...context=...) construction
        assert re.search(r"Task\(.*context\s*=", source, re.DOTALL), (
            "GateBlock.execute() does not construct Task with context= parameter — "
            "variable content (evaluated gate input) must go in task.context, "
            "not interpolated into task.instruction"
        )


class TestGateBlockNoContentInInstruction:
    """GateBlock must NOT f-string interpolate content into the instruction."""

    def test_gate_execute_does_not_interpolate_content_into_instruction(self):
        source = _get_class_method_source(GATE_MODULE, "GateBlock", "execute")
        # The old pattern has {content} inside the instruction f-string
        assert "{content}" not in source, (
            "GateBlock.execute() still f-string interpolates {content} into instruction — "
            "variable content must be passed via task.context instead"
        )


# ===========================================================================
# SynthesizeBlock source-level migration checks
# ===========================================================================

SYNTHESIZE_MODULE = "runsight_core.blocks.synthesize"


class TestSynthesizeBlockImportsBudget:
    """synthesize.py must import from the budget module."""

    def test_synthesize_source_imports_budget(self):
        source = _get_source(SYNTHESIZE_MODULE)
        assert "budget" in source, (
            "synthesize.py does not reference the budget module — "
            "fit_to_budget must be imported from runsight_core.memory.budget"
        )


class TestSynthesizeBlockCallsFitToBudget:
    """synthesize.py execute() must call fit_to_budget."""

    def test_synthesize_execute_contains_fit_to_budget(self):
        source = _get_class_method_source(SYNTHESIZE_MODULE, "SynthesizeBlock", "execute")
        assert "fit_to_budget" in source, (
            "SynthesizeBlock.execute() does not contain 'fit_to_budget' — "
            "budget fitting must happen before runner.execute_task()"
        )


class TestSynthesizeBlockUsesTaskContext:
    """SynthesizeBlock must construct Task with context= for combined outputs."""

    def test_synthesize_execute_constructs_task_with_context(self):
        source = _get_class_method_source(SYNTHESIZE_MODULE, "SynthesizeBlock", "execute")
        # Look for Task(...context=...) construction
        assert re.search(r"Task\(.*context\s*=", source, re.DOTALL), (
            "SynthesizeBlock.execute() does not construct Task with context= parameter — "
            "combined block outputs must go in task.context, "
            "not concatenated into task.instruction"
        )


class TestSynthesizeBlockNoOutputsInInstruction:
    """SynthesizeBlock must NOT concatenate outputs into the instruction string."""

    def test_synthesize_execute_does_not_interpolate_outputs_into_instruction(self):
        source = _get_class_method_source(SYNTHESIZE_MODULE, "SynthesizeBlock", "execute")
        # The old pattern has {combined_outputs} inside the instruction f-string
        assert "{combined_outputs}" not in source, (
            "SynthesizeBlock.execute() still f-string interpolates {combined_outputs} "
            "into instruction — combined outputs must be passed via task.context instead"
        )
