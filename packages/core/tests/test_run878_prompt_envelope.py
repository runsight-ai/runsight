"""
Failing tests for RUN-878: Rename TaskEnvelope → PromptEnvelope.

Covers:
- PromptEnvelope is importable from runsight_core.isolation (AC1, AC5)
- TaskEnvelope is NOT importable from runsight_core.isolation (AC1)
- ContextEnvelope has a `prompt` field, not `task` (AC2)
- DelegateArtifact has a `prompt` field, not `task` (AC3)
- No TaskEnvelope class defined in envelope.py source (AST check) (AC1)
- No Task import in worker_support.py source (AC4)
- No current_task usage in worker_support.py source (AC4)
- harness.py uses PromptEnvelope, not TaskEnvelope (AC5)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ISOLATION_PKG = Path(__file__).parent.parent / "src" / "runsight_core" / "isolation"
_ENVELOPE_PY = _ISOLATION_PKG / "envelope.py"
_WORKER_SUPPORT_PY = _ISOLATION_PKG / "worker_support.py"
_HARNESS_PY = _ISOLATION_PKG / "harness.py"
_INIT_PY = _ISOLATION_PKG / "__init__.py"


# ---------------------------------------------------------------------------
# AC1: PromptEnvelope is importable; TaskEnvelope is NOT
# ---------------------------------------------------------------------------


class TestPromptEnvelopeImportable:
    """PromptEnvelope must be exported from runsight_core.isolation."""

    def test_prompt_envelope_importable_from_isolation(self):
        """PromptEnvelope is importable from runsight_core.isolation."""
        from runsight_core.isolation import PromptEnvelope  # noqa: F401

    def test_prompt_envelope_in_dunder_all(self):
        """PromptEnvelope is listed in runsight_core.isolation.__all__."""
        import runsight_core.isolation as mod

        assert "PromptEnvelope" in mod.__all__

    def test_task_envelope_not_importable_from_isolation(self):
        """TaskEnvelope must NOT be importable from runsight_core.isolation."""
        with pytest.raises((ImportError, AttributeError)):
            from runsight_core.isolation import TaskEnvelope  # noqa: F401

    def test_task_envelope_not_in_dunder_all(self):
        """TaskEnvelope must NOT appear in runsight_core.isolation.__all__."""
        import runsight_core.isolation as mod

        assert "TaskEnvelope" not in mod.__all__

    def test_prompt_envelope_is_pydantic_base_model(self):
        """PromptEnvelope is a Pydantic BaseModel subclass."""
        from pydantic import BaseModel
        from runsight_core.isolation import PromptEnvelope

        assert issubclass(PromptEnvelope, BaseModel)


# ---------------------------------------------------------------------------
# AC2: ContextEnvelope.prompt (not .task)
# ---------------------------------------------------------------------------


class TestContextEnvelopePromptField:
    """ContextEnvelope must expose a `prompt` field, not `task`."""

    def _make_prompt_envelope(self):
        from runsight_core.isolation import PromptEnvelope

        return PromptEnvelope(id="pe-1", instruction="Do the thing.", context={"k": "v"})

    def _make_context_envelope(self):
        from runsight_core.isolation import ContextEnvelope, PromptEnvelope, SoulEnvelope

        soul = SoulEnvelope(
            id="soul-1",
            role="worker",
            system_prompt="You are helpful.",
            model_name="gpt-4o-mini",
            max_tool_iterations=3,
        )
        prompt = PromptEnvelope(id="pe-1", instruction="Do the thing.", context={})
        return ContextEnvelope(
            block_id="block-1",
            block_type="linear",
            block_config={},
            soul=soul,
            tools=[],
            prompt=prompt,
            scoped_results={},
            scoped_shared_memory={},
            conversation_history=[],
            timeout_seconds=30,
            max_output_bytes=1_000_000,
        )

    def test_context_envelope_has_prompt_field(self):
        """ContextEnvelope accepts and stores a `prompt` field."""
        env = self._make_context_envelope()
        assert hasattr(env, "prompt")

    def test_context_envelope_prompt_is_prompt_envelope(self):
        """ContextEnvelope.prompt is a PromptEnvelope instance."""
        from runsight_core.isolation import PromptEnvelope

        env = self._make_context_envelope()
        assert isinstance(env.prompt, PromptEnvelope)

    def test_context_envelope_prompt_has_correct_values(self):
        """ContextEnvelope.prompt carries id and instruction."""
        from runsight_core.isolation import ContextEnvelope, PromptEnvelope, SoulEnvelope

        soul = SoulEnvelope(
            id="s1",
            role="worker",
            system_prompt="",
            model_name="gpt-4o-mini",
            max_tool_iterations=1,
        )
        prompt = PromptEnvelope(id="pe-42", instruction="Summarize this.", context={"doc": "abc"})
        env = ContextEnvelope(
            block_id="b1",
            block_type="linear",
            block_config={},
            soul=soul,
            tools=[],
            prompt=prompt,
            scoped_results={},
            scoped_shared_memory={},
            conversation_history=[],
            timeout_seconds=10,
            max_output_bytes=512,
        )
        assert env.prompt.id == "pe-42"
        assert env.prompt.instruction == "Summarize this."
        assert env.prompt.context == {"doc": "abc"}

    def test_context_envelope_has_no_task_field(self):
        """ContextEnvelope must NOT have a `task` field."""
        env = self._make_context_envelope()
        assert not hasattr(env, "task"), "ContextEnvelope still has old 'task' field"

    def test_context_envelope_rejects_task_kwarg(self):
        """Constructing ContextEnvelope with `task=` must fail (no such field)."""
        from runsight_core.isolation import ContextEnvelope, PromptEnvelope, SoulEnvelope

        soul = SoulEnvelope(
            id="s1",
            role="worker",
            system_prompt="",
            model_name="gpt-4o-mini",
            max_tool_iterations=1,
        )
        with pytest.raises(Exception):
            ContextEnvelope(
                block_id="b1",
                block_type="linear",
                block_config={},
                soul=soul,
                tools=[],
                task=PromptEnvelope(id="t1", instruction="old", context={}),
                scoped_results={},
                scoped_shared_memory={},
                conversation_history=[],
                timeout_seconds=10,
                max_output_bytes=512,
            )


# ---------------------------------------------------------------------------
# AC3: DelegateArtifact.prompt (not .task)
# ---------------------------------------------------------------------------


class TestDelegateArtifactPromptField:
    """DelegateArtifact must expose a `prompt` field, not `task`."""

    def test_delegate_artifact_has_prompt_field(self):
        """DelegateArtifact is constructible with `prompt=`."""
        from runsight_core.isolation import DelegateArtifact

        da = DelegateArtifact(prompt="summarize the document")
        assert da.prompt == "summarize the document"

    def test_delegate_artifact_has_no_task_field(self):
        """DelegateArtifact must NOT have a `task` field."""
        from runsight_core.isolation import DelegateArtifact

        da = DelegateArtifact(prompt="do something")
        assert not hasattr(da, "task"), "DelegateArtifact still has old 'task' field"

    def test_delegate_artifact_rejects_task_kwarg(self):
        """Constructing DelegateArtifact with `task=` must fail."""
        from runsight_core.isolation import DelegateArtifact

        with pytest.raises(Exception):
            DelegateArtifact(task="old field")

    def test_delegate_artifact_round_trips_json(self):
        """DelegateArtifact with `prompt` survives JSON round-trip."""
        from runsight_core.isolation import DelegateArtifact

        original = DelegateArtifact(prompt="analyze the report")
        json_str = original.model_dump_json()
        restored = DelegateArtifact.model_validate_json(json_str)
        assert restored.prompt == "analyze the report"


# ---------------------------------------------------------------------------
# AC1 (AST): No TaskEnvelope class in envelope.py
# ---------------------------------------------------------------------------


class TestEnvelopeSourceNoTaskEnvelope:
    """envelope.py must not define a TaskEnvelope class."""

    def _parse_envelope_ast(self) -> ast.Module:
        source = _ENVELOPE_PY.read_text(encoding="utf-8")
        return ast.parse(source)

    def test_no_task_envelope_class_defined(self):
        """envelope.py must not contain a class named TaskEnvelope."""
        tree = self._parse_envelope_ast()
        class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        assert "TaskEnvelope" not in class_names, (
            f"TaskEnvelope class still defined in envelope.py. Classes found: {class_names}"
        )

    def test_prompt_envelope_class_defined(self):
        """envelope.py must define a class named PromptEnvelope."""
        tree = self._parse_envelope_ast()
        class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        assert "PromptEnvelope" in class_names, (
            f"PromptEnvelope class not found in envelope.py. Classes found: {class_names}"
        )

    def test_task_not_used_as_field_name_in_context_envelope(self):
        """envelope.py must not use 'task' as a field name in ContextEnvelope."""
        source = _ENVELOPE_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ContextEnvelope":
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        if isinstance(item.target, ast.Name) and item.target.id == "task":
                            pytest.fail(
                                "ContextEnvelope still has a field named 'task' in envelope.py"
                            )


# ---------------------------------------------------------------------------
# AC4: worker_support.py — no Task import, no current_task usage
# ---------------------------------------------------------------------------


class TestWorkerSupportNoTaskImport:
    """worker_support.py must not import Task or use current_task."""

    def _parse_worker_support_ast(self) -> ast.Module:
        source = _WORKER_SUPPORT_PY.read_text(encoding="utf-8")
        return ast.parse(source)

    def test_no_task_import_in_worker_support(self):
        """worker_support.py must not import Task from runsight_core.primitives."""
        tree = self._parse_worker_support_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name != "Task", (
                        f"worker_support.py still imports 'Task' from {node.module!r}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "Task", "worker_support.py still has a bare 'import Task'"

    def test_no_current_task_in_worker_support(self):
        """worker_support.py must not reference current_task."""
        source = _WORKER_SUPPORT_PY.read_text(encoding="utf-8")
        assert "current_task" not in source, (
            "worker_support.py still references 'current_task' — should be removed after "
            "TaskEnvelope→PromptEnvelope rename"
        )

    def test_no_task_envelope_import_in_worker_support(self):
        """worker_support.py must not import TaskEnvelope."""
        tree = self._parse_worker_support_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name != "TaskEnvelope", (
                        f"worker_support.py still imports 'TaskEnvelope' from {node.module!r}"
                    )


# ---------------------------------------------------------------------------
# AC5: harness.py uses PromptEnvelope, not TaskEnvelope
# ---------------------------------------------------------------------------


class TestHarnessUsesPromptEnvelope:
    """harness.py must reference PromptEnvelope, not TaskEnvelope."""

    def _parse_harness_ast(self) -> ast.Module:
        source = _HARNESS_PY.read_text(encoding="utf-8")
        return ast.parse(source)

    def test_harness_does_not_import_task_envelope(self):
        """harness.py must not import TaskEnvelope from isolation.envelope."""
        tree = self._parse_harness_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name != "TaskEnvelope", (
                        f"harness.py still imports 'TaskEnvelope' from {node.module!r}"
                    )

    def test_harness_imports_prompt_envelope(self):
        """harness.py must import PromptEnvelope from isolation.envelope."""
        tree = self._parse_harness_ast()
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.append(alias.name)
        assert "PromptEnvelope" in imported_names, (
            f"harness.py does not import 'PromptEnvelope'. Imports found: {imported_names}"
        )

    def test_harness_source_uses_prompt_envelope_not_task_envelope(self):
        """harness.py source must not contain the string 'TaskEnvelope'."""
        source = _HARNESS_PY.read_text(encoding="utf-8")
        assert "TaskEnvelope" not in source, (
            "harness.py still contains 'TaskEnvelope' — must be renamed to PromptEnvelope"
        )

    def test_harness_source_contains_prompt_envelope(self):
        """harness.py source must reference PromptEnvelope."""
        source = _HARNESS_PY.read_text(encoding="utf-8")
        assert "PromptEnvelope" in source, "harness.py does not reference 'PromptEnvelope' at all"


# ---------------------------------------------------------------------------
# AC5: __init__.py exports PromptEnvelope, not TaskEnvelope
# ---------------------------------------------------------------------------


class TestInitExports:
    """__init__.py must export PromptEnvelope and not TaskEnvelope."""

    def test_init_exports_prompt_envelope_in_source(self):
        """__init__.py source must include 'PromptEnvelope' in its imports/all."""
        source = _INIT_PY.read_text(encoding="utf-8")
        assert "PromptEnvelope" in source, "__init__.py does not reference 'PromptEnvelope'"

    def test_init_does_not_export_task_envelope_in_source(self):
        """__init__.py source must not include 'TaskEnvelope'."""
        source = _INIT_PY.read_text(encoding="utf-8")
        assert "TaskEnvelope" not in source, "__init__.py still references 'TaskEnvelope'"
