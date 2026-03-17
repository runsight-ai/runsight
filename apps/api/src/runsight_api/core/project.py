"""Project detection: resolve base_path from marker file or directory structure."""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

MARKER_FILE = ".runsight-project"
MAX_WALK_DEPTH = 20


def _parse_marker(marker_path: Path) -> Optional[str]:
    """Parse a .runsight-project YAML file and return the resolved base_path.

    Returns None if the file is invalid or missing the base_path field.
    """
    try:
        text = marker_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict) or "base_path" not in data:
            logger.warning("Marker %s missing 'base_path' field, skipping", marker_path)
            return None
        raw = data["base_path"]
        resolved = (marker_path.parent / raw).resolve()
        return str(resolved)
    except Exception:
        logger.warning("Failed to parse marker %s, skipping", marker_path, exc_info=True)
        return None


def _find_marker(start: Path) -> Optional[str]:
    """Walk up from *start* looking for a .runsight-project file.

    Returns the resolved base_path string, or None.
    """
    current = start.resolve()
    for _ in range(MAX_WALK_DEPTH):
        candidate = current / MARKER_FILE
        try:
            found = candidate.is_file()
        except OSError:
            found = False
        if found:
            result = _parse_marker(candidate)
            if result is not None:
                logger.info("Found project marker at %s", candidate)
                return result
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _find_custom_workflows(start: Path) -> Optional[str]:
    """Walk up from *start* looking for a custom/workflows/ directory.

    Returns the parent of ``custom/`` as base_path, or None.
    """
    current = start.resolve()
    for _ in range(MAX_WALK_DEPTH):
        try:
            found = (current / "custom" / "workflows").is_dir()
        except OSError:
            found = False
        if found:
            logger.info("Auto-detected custom/workflows/ at %s", current)
            return str(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def resolve_base_path(env_value: Optional[str] = None) -> str:
    """Resolve the project base_path using a 4-tier priority.

    1. ``RUNSIGHT_BASE_PATH`` env var (passed in as *env_value*)
    2. ``.runsight-project`` marker file (walk up from CWD)
    3. Auto-detect ``custom/workflows/`` directory in ancestors
    4. CWD as last resort
    """
    # Tier 1: explicit env var
    if env_value is not None:
        logger.info("base_path from RUNSIGHT_BASE_PATH env var: %s", env_value)
        return env_value

    cwd = Path.cwd()

    # Tier 2: marker file
    marker_result = _find_marker(cwd)
    if marker_result is not None:
        return marker_result

    # Tier 3: auto-detect custom/workflows/
    auto_result = _find_custom_workflows(cwd)
    if auto_result is not None:
        return auto_result

    # Tier 4: CWD fallback
    logger.info("No project marker or custom/workflows/ found, using CWD: %s", cwd)
    return str(cwd)
