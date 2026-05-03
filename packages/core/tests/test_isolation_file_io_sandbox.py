"""File I/O base directory and path traversal sandbox behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.real_subprocess_isolation


class TestFileIOBaseDir:
    """File I/O handler must scope all paths to a per-workflow base directory."""

    @pytest.mark.asyncio
    async def test_file_io_handler_requires_base_dir(self, tmp_path: Path):
        """make_file_io_handler requires a base_dir parameter."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "workflow-files"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        assert handler is not None

    @pytest.mark.asyncio
    async def test_read_resolves_relative_to_base_dir(self, tmp_path: Path):
        """Reading a file resolves the path relative to base_dir."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-data"
        base.mkdir()
        (base / "notes.txt").write_text("hello from base")

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "notes.txt",
            }
        )

        assert result.get("content") == "hello from base"

    @pytest.mark.asyncio
    async def test_write_resolves_relative_to_base_dir(self, tmp_path: Path):
        """Writing a file places it inside base_dir."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-output"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "write",
                "path": "output.txt",
                "content": "result data",
            }
        )

        assert "error" not in result
        assert (base / "output.txt").read_text() == "result data"

    @pytest.mark.asyncio
    async def test_write_over_max_write_bytes_is_rejected(self, tmp_path: Path):
        """File writes are capped engine-side to avoid disk exhaustion."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-output"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base), max_write_bytes=4)
        result = await handler(
            {
                "action_type": "write",
                "path": "too-large.txt",
                "content": "12345",
            }
        )

        assert result == {"error": "file write exceeds max_write_bytes=4"}
        assert not (base / "too-large.txt").exists()

    @pytest.mark.asyncio
    async def test_cumulative_writes_over_max_total_write_bytes_are_rejected(self, tmp_path: Path):
        """Many individually valid writes cannot exceed the handler's total write budget."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-output"
        base.mkdir()

        handler = make_file_io_handler(
            base_dir=str(base),
            max_write_bytes=10,
            max_total_write_bytes=8,
        )
        first = await handler(
            {
                "action_type": "write",
                "path": "first.txt",
                "content": "1234",
            }
        )
        second = await handler(
            {
                "action_type": "write",
                "path": "second.txt",
                "content": "56789",
            }
        )

        assert first == {"ok": True}
        assert second == {"error": "file writes exceed max_total_write_bytes=8"}
        assert (base / "first.txt").read_text() == "1234"
        assert not (base / "second.txt").exists()

    @pytest.mark.asyncio
    async def test_absolute_path_rejected(self, tmp_path: Path):
        """Absolute paths must be rejected - only relative paths within base_dir."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-safe"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "/etc/passwd",
            }
        )

        assert "error" in result


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------


class TestFileIOPathTraversal:
    """File I/O handler must block path traversal via '..' in path components."""

    @pytest.mark.asyncio
    async def test_dotdot_in_path_rejected(self, tmp_path: Path):
        """Paths containing '..' are rejected."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-guarded"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "../../../etc/passwd",
            }
        )

        assert "error" in result
        assert "traversal" in result["error"].lower() or ".." in result["error"]

    @pytest.mark.asyncio
    async def test_dotdot_in_middle_of_path_rejected(self, tmp_path: Path):
        """Paths with '..' in a middle segment are rejected."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-mid"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "subdir/../../secret.txt",
            }
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_encoded_dotdot_rejected(self, tmp_path: Path):
        """URL-encoded '..' variants should also be caught."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-enc"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))

        # Even after normalization, if the resolved path escapes base_dir, it's blocked
        result = await handler(
            {
                "action_type": "read",
                "path": "subdir/%2e%2e/secret.txt",
            }
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_write_with_traversal_rejected(self, tmp_path: Path):
        """Write operations with path traversal are blocked."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-write-guard"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "write",
                "path": "../../escape.txt",
                "content": "malicious content",
            }
        )

        assert "error" in result
        # Ensure the file was not written outside base_dir
        assert not (tmp_path / "escape.txt").exists()

    @pytest.mark.asyncio
    async def test_symlink_to_sibling_prefix_directory_rejected(self, tmp_path: Path):
        """Symlink escapes to a similarly named sibling must be rejected."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-safe"
        sibling = tmp_path / "wf-safe-escape"
        base.mkdir()
        sibling.mkdir()
        (sibling / "secret.txt").write_text("outside")
        (base / "escape-link").symlink_to(sibling, target_is_directory=True)

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "escape-link/secret.txt",
            }
        )

        assert "error" in result
        assert "escape" in result["error"].lower() or "base" in result["error"].lower()


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------
