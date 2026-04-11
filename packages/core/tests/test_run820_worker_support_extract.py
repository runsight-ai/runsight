"""
Failing tests for RUN-820: Extract worker_support.py from worker.py.

Acceptance criteria verified:
1. All 7 symbols are importable from runsight_core.isolation.worker_support
2. None of the 7 symbols are class/def-defined in worker.py source text (AST)
3. worker.py does NOT re-export (no `from .worker_support import`, no `__getattr__`)
4. main(), _execute_envelope(), _heartbeat_loop(), _emit_heartbeat(), _error_result()
   remain in worker.py
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ISOLATION_PKG = Path(__file__).parent.parent / "src" / "runsight_core" / "isolation"
_WORKER_PY = _ISOLATION_PKG / "worker.py"
_WORKER_SUPPORT_PY = _ISOLATION_PKG / "worker_support.py"

_MOVED_SYMBOLS = [
    "parse_context_envelope",
    "reconstruct_soul",
    "build_budgeted_history",
    "build_scoped_state",
    "_BLOCK_TYPE_MAP",
    "_resolve_block_soul",
    "_create_block",
]

_STAY_IN_WORKER = [
    "main",
    "_execute_envelope",
    "_heartbeat_loop",
    "_emit_heartbeat",
    "_error_result",
]


def _top_level_definition_names(source: str) -> set[str]:
    """Return names of all top-level class/def/assignment targets in the source."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
    return names


# ---------------------------------------------------------------------------
# 1. worker_support.py exists and all 7 symbols are importable from it
# ---------------------------------------------------------------------------


def test_worker_support_file_exists() -> None:
    """worker_support.py must exist in the isolation package."""
    assert _WORKER_SUPPORT_PY.exists(), (
        f"{_WORKER_SUPPORT_PY} does not exist — worker_support.py has not been created yet"
    )


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_symbol_importable_from_worker_support(symbol_name: str) -> None:
    """Each moved symbol must be importable from runsight_core.isolation.worker_support."""
    module = importlib.import_module("runsight_core.isolation.worker_support")
    assert hasattr(module, symbol_name), (
        f"runsight_core.isolation.worker_support is missing symbol: {symbol_name}"
    )


# ---------------------------------------------------------------------------
# 2. The 7 symbols are NOT class/def-defined in worker.py source text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_symbol_not_defined_in_worker_py(symbol_name: str) -> None:
    """Moved symbols must no longer be defined (class/def/assignment) in worker.py."""
    source = _WORKER_PY.read_text(encoding="utf-8")
    defined_names = _top_level_definition_names(source)
    assert symbol_name not in defined_names, (
        f"Symbol '{symbol_name}' is still defined as a top-level name in worker.py — "
        "it must be removed and placed in worker_support.py"
    )


# ---------------------------------------------------------------------------
# 3. worker.py does NOT re-export (no `from .worker_support import`, no `__getattr__`)
# ---------------------------------------------------------------------------


def test_worker_py_has_no_reexport_from_worker_support() -> None:
    """worker.py must not contain `from .worker_support import` — no re-exports."""
    source = _WORKER_PY.read_text(encoding="utf-8")
    assert "from .worker_support import" not in source, (
        "worker.py contains a re-export: `from .worker_support import`. "
        "Per RUN-820, worker.py must not re-export symbols from worker_support."
    )
    assert "from runsight_core.isolation.worker_support import" not in source, (
        "worker.py contains an absolute re-export from worker_support. "
        "Per RUN-820, worker.py must not re-export symbols from worker_support."
    )


def test_worker_py_has_no_getattr_shim() -> None:
    """worker.py must not contain a __getattr__ function (no lazy-import shim)."""
    source = _WORKER_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__":
            pytest.fail(
                "worker.py defines a module-level __getattr__ function. "
                "Per RUN-820, no backwards-compat shims are allowed."
            )


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_worker_py_does_not_re_export_individual_symbol(symbol_name: str) -> None:
    """worker.py must not import individual moved symbols to re-export them."""
    source = _WORKER_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.names:
            module_name = node.module or ""
            if "worker_support" not in module_name:
                continue
            for alias in node.names:
                if alias.name == symbol_name or alias.asname == symbol_name:
                    pytest.fail(
                        f"worker.py re-exports '{symbol_name}' from worker_support "
                        f"(via import from {module_name}). No re-exports allowed per RUN-820."
                    )


# ---------------------------------------------------------------------------
# 4. main(), _execute_envelope(), _heartbeat_loop(), _emit_heartbeat(),
#    _error_result() remain in worker.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol_name", _STAY_IN_WORKER)
def test_worker_residents_still_defined_in_worker_py(symbol_name: str) -> None:
    """Core worker functions must remain as top-level definitions in worker.py."""
    source = _WORKER_PY.read_text(encoding="utf-8")
    defined_names = _top_level_definition_names(source)
    assert symbol_name in defined_names, (
        f"'{symbol_name}' is no longer defined in worker.py — it must stay there."
    )
