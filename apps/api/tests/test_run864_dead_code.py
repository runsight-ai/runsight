"""Red tests for RUN-864: remove dead code — ArtifactCleanupObserver and setup_app_state.

1. ArtifactCleanupObserver file must not exist.
2. Container.setup_app_state must not be defined in di.py.
3. No imports of ArtifactCleanupObserver anywhere in the source tree.
"""

from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_API_SRC = Path(__file__).parent.parent / "src" / "runsight_api"
_OBSERVERS_FILE = _API_SRC / "logic" / "observers" / "artifact_cleanup_observer.py"
_DI_FILE = _API_SRC / "core" / "di.py"


# ---------------------------------------------------------------------------
# 1. ArtifactCleanupObserver file must not exist
# ---------------------------------------------------------------------------


def test_no_artifact_cleanup_observer_file():
    """artifact_cleanup_observer.py must be deleted — it is never wired."""
    assert not _OBSERVERS_FILE.exists(), f"Dead file still present: {_OBSERVERS_FILE}"


# ---------------------------------------------------------------------------
# 2. Container.setup_app_state must not be in di.py
# ---------------------------------------------------------------------------


def test_no_setup_app_state_in_di():
    """Container.setup_app_state is a no-op; it must be removed from di.py."""
    assert _DI_FILE.exists(), f"di.py not found at {_DI_FILE}"

    source = _DI_FILE.read_text()
    assert "setup_app_state" not in source, "No-op method setup_app_state still present in di.py"


# ---------------------------------------------------------------------------
# 3. No imports of ArtifactCleanupObserver anywhere in the source tree
# ---------------------------------------------------------------------------


def test_no_artifact_cleanup_observer_imports():
    """No Python file in apps/api/src/ should import ArtifactCleanupObserver."""
    offenders = []
    for py_file in _API_SRC.rglob("*.py"):
        text = py_file.read_text()
        if "ArtifactCleanupObserver" in text:
            offenders.append(str(py_file))

    assert not offenders, "ArtifactCleanupObserver still referenced in source files:\n" + "\n".join(
        f"  {p}" for p in offenders
    )
