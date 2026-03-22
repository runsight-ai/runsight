"""Shared utilities for filesystem-backed repositories."""

import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    """Write content to a file atomically via temp file + rename.

    The temp file is created in the same directory to ensure os.rename
    operates within a single filesystem.
    """
    parent = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.rename(tmp_path, str(path))
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
