"""
API dead-code boundary governance for removed startup observer wiring.

Owner: apps/api core DI and observer wiring owners.
Boundary: the retired ArtifactCleanupObserver file and Container.setup_app_state
hook must stay removed from API runtime source.
Exit criteria: delete this governance suite once normal startup and observer
wiring tests make reintroducing this dead path impossible.
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_API_SRC = Path(__file__).parent.parent / "src" / "runsight_api"
_OBSERVERS_FILE = _API_SRC / "logic" / "observers" / "artifact_cleanup_observer.py"
_DI_FILE = _API_SRC / "core" / "di.py"


def _read_source(path: Path) -> str:
    assert path.exists(), f"Expected source file to exist: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. ArtifactCleanupObserver file must not exist
# ---------------------------------------------------------------------------


class TestApiDeadCodeBoundaryGovernance:
    """Owner: apps/api core/observer wiring. Exit: startup behavior tests own this boundary."""

    def test_no_artifact_cleanup_observer_file(self):
        assert not _OBSERVERS_FILE.exists(), f"Dead file still present: {_OBSERVERS_FILE}"

    def test_no_setup_app_state_in_di(self):
        source = _read_source(_DI_FILE)
        assert "setup_app_state" not in source, (
            "No-op method setup_app_state still present in di.py"
        )

    def test_no_artifact_cleanup_observer_imports(self):
        offenders = []
        for py_file in _API_SRC.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if "ArtifactCleanupObserver" in text:
                offenders.append(str(py_file))

        assert not offenders, (
            "ArtifactCleanupObserver still referenced in source files:\n"
            + "\n".join(f"  {p}" for p in offenders)
        )
