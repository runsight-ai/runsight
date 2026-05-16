"""Source locations for PromptEnvelope isolation tests."""

from __future__ import annotations

from pathlib import Path

ISOLATION_PKG = Path(__file__).parent.parent / "src" / "runsight_core" / "isolation"
ENVELOPE_PY = ISOLATION_PKG / "envelope.py"
WORKER_SUPPORT_PY = ISOLATION_PKG / "worker_support.py"
WRAPPER_PY = ISOLATION_PKG / "wrapper.py"
INIT_PY = ISOLATION_PKG / "__init__.py"
