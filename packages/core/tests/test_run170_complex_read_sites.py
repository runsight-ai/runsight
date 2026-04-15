"""
Failing tests for RUN-170: Complex read site migrations.

Three complex read sites that consume BlockResult from state.results:

1. CodeBlock subprocess serialization (implementations.py ~line 1364):
   json.dumps({"results": state.results, ...}) — TypeError because BlockResult
   is not JSON-serializable by stdlib json.dumps.

2. WorkflowBlock._resolve_dotted (implementations.py ~line 888):
   Returns field_dict[key] which is now a BlockResult. Callers may need
   .output extraction. We verify the method works and returns a BlockResult.

3. primitives._resolve_from_ref (primitives.py ~line 125):
   Already fixed in RUN-177 — unwraps BlockResult.output. Tests verify
   correctness with JSON, non-JSON, and plain outputs.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from conftest import execute_block_for_test
from runsight_core.state import BlockResult, WorkflowState

# =============================================================================
# 1. CodeBlock subprocess serialization
# =============================================================================


class TestCodeBlockSubprocessSerialization:
    """CodeBlock.execute() must serialize state.results containing BlockResult
    objects into the JSON payload sent to the subprocess via stdin.

    Current code does:
        json.dumps({"results": state.results, ...})
    which raises TypeError because BlockResult is not JSON-serializable.

    After fix, the subprocess should receive plain string values.
    """

    @pytest.mark.asyncio
    async def test_codeblock_serializes_results_with_block_result(self):
        """json.dumps should not raise TypeError when results contain BlockResult."""
        from runsight_core import CodeBlock

        block = CodeBlock(
            block_id="code1",
            code='def main(data): return {"echo": data["results"]["prev"]}',
        )

        state = WorkflowState(
            results={"prev": BlockResult(output="hello world")},
        )

        # Mock subprocess to capture what's sent on stdin
        captured_stdin = {}

        async def fake_create_subprocess_exec(*args, **kwargs):
            proc = MagicMock()

            async def fake_communicate(input=None):
                captured_stdin["data"] = input
                # Return valid JSON output
                return (b'{"echo": "hello world"}', b"")

            proc.communicate = fake_communicate
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
            await execute_block_for_test(block, state)

        # The subprocess should have received valid JSON on stdin
        assert "data" in captured_stdin, "Subprocess was never called"
        payload = json.loads(captured_stdin["data"])
        # The results values should be plain strings, not BlockResult repr
        assert payload["results"]["prev"] == "hello world"
        assert isinstance(payload["results"]["prev"], str)

    @pytest.mark.asyncio
    async def test_codeblock_serializes_mixed_results(self):
        """Results dict with multiple BlockResult values serializes correctly."""
        from runsight_core import CodeBlock

        block = CodeBlock(
            block_id="code2",
            code='def main(data): return {"ok": True}',
        )

        state = WorkflowState(
            results={
                "step_a": BlockResult(output="result A"),
                "step_b": BlockResult(output='{"nested": "json"}'),
                "step_c": BlockResult(output=""),
            },
        )

        captured_stdin = {}

        async def fake_create_subprocess_exec(*args, **kwargs):
            proc = MagicMock()

            async def fake_communicate(input=None):
                captured_stdin["data"] = input
                return (b'{"ok": true}', b"")

            proc.communicate = fake_communicate
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
            await execute_block_for_test(block, state)

        payload = json.loads(captured_stdin["data"])
        assert payload["results"]["step_a"] == "result A"
        assert payload["results"]["step_b"] == '{"nested": "json"}'
        assert payload["results"]["step_c"] == ""

    @pytest.mark.asyncio
    async def test_codeblock_serializes_results_with_metadata(self):
        """BlockResult with artifact metadata — only output should appear in JSON."""
        from runsight_core import CodeBlock

        block = CodeBlock(
            block_id="code3",
            code='def main(data): return data["results"]',
        )

        state = WorkflowState(
            results={
                "enriched": BlockResult(
                    output="enriched value",
                    artifact_ref="s3://bucket/file.json",
                    artifact_type="json",
                    metadata={"model": "gpt-4"},
                ),
            },
        )

        captured_stdin = {}

        async def fake_create_subprocess_exec(*args, **kwargs):
            proc = MagicMock()

            async def fake_communicate(input=None):
                captured_stdin["data"] = input
                return (b'{"enriched": "enriched value"}', b"")

            proc.communicate = fake_communicate
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
            await execute_block_for_test(block, state)

        payload = json.loads(captured_stdin["data"])
        # Should be the plain output string, not the full BlockResult model
        assert payload["results"]["enriched"] == "enriched value"
        assert isinstance(payload["results"]["enriched"], str)


# =============================================================================
# 2. WorkflowBlock._resolve_dotted with BlockResult
# =============================================================================


class TestWorkflowBlockResolveDottedBlockResult:
    """WorkflowBlock._resolve_dotted returns field_dict[key] for results paths.
    Since results values are now BlockResult, verify the method returns a
    BlockResult and callers can extract .output."""

    def _make_workflow_block(self):
        """Create a minimal WorkflowBlock for testing _resolve_dotted."""
        from runsight_core import WorkflowBlock
        from runsight_core.workflow import Workflow

        child_workflow = MagicMock(spec=Workflow)
        child_workflow.name = "child"
        child_workflow.steps = []

        wb = WorkflowBlock(
            block_id="wb1",
            child_workflow=child_workflow,
            inputs={},
            outputs={},
        )
        return wb

    def test_resolve_dotted_returns_block_result_for_results_path(self):
        """_resolve_dotted('results.prev') returns the BlockResult object."""
        wb = self._make_workflow_block()
        state = WorkflowState(
            results={"prev": BlockResult(output="resolved value")},
        )
        result = wb._resolve_dotted(state, "results.prev")
        assert isinstance(result, BlockResult)
        assert result.output == "resolved value"

    def test_resolve_dotted_block_result_output_is_extractable(self):
        """Callers can extract .output from the returned BlockResult."""
        wb = self._make_workflow_block()
        state = WorkflowState(
            results={"step1": BlockResult(output="step 1 output")},
        )
        result = wb._resolve_dotted(state, "results.step1")
        # The value should be usable as a string via .output
        assert result.output == "step 1 output"
        # And via __str__
        assert str(result) == "step 1 output"

    def test_resolve_dotted_block_result_with_json_output(self):
        """BlockResult with JSON string output — callers can parse it."""
        wb = self._make_workflow_block()
        state = WorkflowState(
            results={"data": BlockResult(output='{"key": "value"}')},
        )
        result = wb._resolve_dotted(state, "results.data")
        parsed = json.loads(result.output)
        assert parsed == {"key": "value"}


# =============================================================================
# 3. primitives._resolve_from_ref with BlockResult (fixed in RUN-177)
# =============================================================================


class TestResolveFromRefBlockResult:
    """Input resolution unwraps BlockResult.output (originally RUN-177).
    Step._resolve_from_ref was removed in RUN-892; resolution now lives in
    block_io._resolve_ref. These tests verify the canonical path."""

    def test_resolve_ref_unwraps_block_result(self):
        """_resolve_ref extracts .output from BlockResult."""
        from runsight_core.block_io import _resolve_ref

        state = WorkflowState(
            results={"source": BlockResult(output="plain text output")},
        )
        result = _resolve_ref("source", state)
        assert result == "plain text output"
        assert isinstance(result, str)

    def test_resolve_ref_block_result_with_json_and_path(self):
        """_resolve_ref parses JSON output and resolves dotted path."""
        from runsight_core.block_io import _resolve_ref

        state = WorkflowState(
            results={
                "api_call": BlockResult(output='{"response": {"status": "ok", "data": [1,2,3]}}')
            },
        )
        result = _resolve_ref("api_call.response.status", state)
        assert result == "ok"

    def test_resolve_ref_block_result_non_json_output(self):
        """Non-JSON output with field path returns raw string."""
        from runsight_core.block_io import _resolve_ref

        state = WorkflowState(
            results={"writer": BlockResult(output="This is not JSON at all")},
        )
        # When output is not JSON and a field path is requested, returns raw string
        result = _resolve_ref("writer.some_field", state)
        assert result == "This is not JSON at all"

    def test_resolve_ref_block_result_json_string_literal(self):
        """JSON string literal output (e.g. '"hello"') returns the string."""
        from runsight_core.block_io import _resolve_ref

        state = WorkflowState(
            results={"quoter": BlockResult(output='"hello world"')},
        )
        result = _resolve_ref("quoter", state)
        # No field path — returns the raw output string
        assert result == '"hello world"'
