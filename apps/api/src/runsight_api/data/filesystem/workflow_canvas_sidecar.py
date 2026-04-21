"""Canvas sidecar read/write helpers for workflow persistence."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def read_canvas_sidecar(path: Path) -> Optional[dict[str, Any]]:
    """Read a canvas sidecar if present, warning and returning None on failure."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.warning("Failed to read canvas sidecar %s: %s", path, exc)
        return None


def write_canvas_sidecar(
    *,
    stem: str,
    canvas_state: Any,
    path: Path,
    atomic_write: Callable[[Path, str], None],
) -> list[dict[str, str]]:
    """Write a canvas sidecar, surfacing write failures as explicit warnings."""
    if canvas_state is None:
        return []
    if hasattr(canvas_state, "model_dump"):
        canvas_data = canvas_state.model_dump()
    elif isinstance(canvas_state, dict):
        canvas_data = canvas_state
    else:
        logger.warning("Unexpected canvas_state type: %s", type(canvas_state))
        return []

    try:
        content = json.dumps(canvas_data, indent=2, sort_keys=True)
        atomic_write(path, content)
        return []
    except Exception as exc:
        logger.warning("Failed to write canvas sidecar for %s: %s", stem, exc)
        return [
            {
                "message": f"Failed to write canvas sidecar for {stem}: {exc}",
                "source": "canvas_sidecar",
                "context": stem,
            }
        ]
