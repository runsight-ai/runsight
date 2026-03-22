"""
Tests for RUN-251: async file I/O in FileWriterBlock.execute.

Verifies that FileWriterBlock wraps synchronous Path.mkdir() and
Path.write_text() calls in asyncio.to_thread() so the event loop
is never blocked.
"""

import ast
import asyncio
import inspect
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from runsight_core.blocks.file_writer import FileWriterBlock
from runsight_core.state import BlockResult, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_execute_source() -> str:
    """Return the source code of FileWriterBlock.execute."""
    return textwrap.dedent(inspect.getsource(FileWriterBlock.execute))


def _get_module_source() -> str:
    """Return the full source of the file_writer module."""
    import runsight_core.blocks.file_writer as mod

    return inspect.getsource(mod)


# ---------------------------------------------------------------------------
# AC-1: mkdir() and write_text() are wrapped in asyncio.to_thread()
# ---------------------------------------------------------------------------


class TestAsyncToThreadWrapping:
    """Verify file I/O calls are delegated to asyncio.to_thread."""

    def test_module_imports_asyncio(self):
        """file_writer.py must import asyncio at the module level."""
        source = _get_module_source()
        tree = ast.parse(source)
        import_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_names.append(node.module)
        assert "asyncio" in import_names, (
            "file_writer.py does not import 'asyncio'; asyncio.to_thread cannot be used without it"
        )

    def test_execute_uses_asyncio_to_thread(self):
        """execute() must contain at least two asyncio.to_thread calls
        (one for mkdir, one for write_text)."""
        source = _get_execute_source()
        tree = ast.parse(source)
        to_thread_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                call = node.value
                if isinstance(call, ast.Call):
                    func = call.func
                    # asyncio.to_thread(...)
                    if (
                        isinstance(func, ast.Attribute)
                        and func.attr == "to_thread"
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "asyncio"
                    ):
                        to_thread_calls.append(call)
        assert len(to_thread_calls) >= 2, (
            f"Expected at least 2 asyncio.to_thread() calls in execute(); "
            f"found {len(to_thread_calls)}"
        )


# ---------------------------------------------------------------------------
# AC-2: No synchronous Path.mkdir() or Path.write_text() in execute()
# ---------------------------------------------------------------------------


class TestNoSynchronousCalls:
    """Verify that bare (non-to_thread) mkdir/write_text calls are absent."""

    def test_no_bare_mkdir_call(self):
        """execute() must NOT call .mkdir() directly (outside to_thread)."""
        source = _get_execute_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            # Look for top-level expression statements like `output.parent.mkdir(...)`
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Attribute) and call.func.attr == "mkdir":
                    pytest.fail(
                        "Found bare .mkdir() call in execute(); "
                        "it must be wrapped in asyncio.to_thread()"
                    )

    def test_no_bare_write_text_call(self):
        """execute() must NOT call .write_text() directly (outside to_thread)."""
        source = _get_execute_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Attribute) and call.func.attr == "write_text":
                    pytest.fail(
                        "Found bare .write_text() call in execute(); "
                        "it must be wrapped in asyncio.to_thread()"
                    )


# ---------------------------------------------------------------------------
# AC-3: FileWriterBlock still produces correct output files
# ---------------------------------------------------------------------------


class TestFunctionalCorrectness:
    """Verify that the async-ified FileWriterBlock still works end-to-end."""

    @pytest.mark.asyncio
    async def test_file_written_correctly(self):
        """Content is written to the expected path with correct encoding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "output.txt")
            content = "Hello async world!\nLine two."
            block = FileWriterBlock(
                block_id="fw1",
                output_path=output_path,
                content_key="data",
            )
            state = WorkflowState(results={"data": BlockResult(output=content)})

            await block.execute(state)

            written = Path(output_path).read_text(encoding="utf-8")
            assert written == content

    @pytest.mark.asyncio
    async def test_parent_directories_created(self):
        """Nested parent directories are created when they do not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "a" / "b" / "c" / "deep.txt")
            content = "deep content"
            block = FileWriterBlock(
                block_id="fw2",
                output_path=output_path,
                content_key="data",
            )
            state = WorkflowState(results={"data": BlockResult(output=content)})

            await block.execute(state)

            assert Path(output_path).exists()
            assert Path(output_path).read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_result_state_contains_char_count(self):
        """Returned state includes block result with character count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "result.txt")
            content = "exactly twenty chars"  # 20 chars
            block = FileWriterBlock(
                block_id="fw3",
                output_path=output_path,
                content_key="data",
            )
            state = WorkflowState(results={"data": BlockResult(output=content)})

            result_state = await block.execute(state)

            msg = result_state.results["fw3"].output
            assert f"Written {len(content)} chars to {output_path}" == msg

    @pytest.mark.asyncio
    async def test_execute_does_not_block_event_loop(self):
        """Demonstrate that file I/O runs in a thread by verifying
        asyncio.to_thread is actually awaited during execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "async_test.txt")
            content = "thread check"
            block = FileWriterBlock(
                block_id="fw4",
                output_path=output_path,
                content_key="data",
            )
            state = WorkflowState(results={"data": BlockResult(output=content)})

            to_thread_calls = []
            original_to_thread = asyncio.to_thread

            async def tracking_to_thread(func, *args, **kwargs):
                to_thread_calls.append(func.__name__ if hasattr(func, "__name__") else str(func))
                return await original_to_thread(func, *args, **kwargs)

            with patch("asyncio.to_thread", side_effect=tracking_to_thread):
                await block.execute(state)

            assert len(to_thread_calls) >= 2, (
                f"Expected asyncio.to_thread to be called at least twice "
                f"(mkdir + write_text); got {len(to_thread_calls)} calls"
            )
            # The file should still be written correctly
            assert Path(output_path).read_text(encoding="utf-8") == content
