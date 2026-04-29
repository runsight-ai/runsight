"""
Failing tests for RUN-818: Extract interceptors.py from ipc.py.

Acceptance criteria verified:
1. All 4 symbols are importable from runsight_core.isolation.interceptors
2. None of the 4 symbols are class/def-defined in ipc.py source text
3. ipc.py does NOT re-export (no `from .interceptors import`, no `__getattr__`)
4. IPCServer, IPCClient, _is_async_iterable remain in ipc.py
5. __init__.py imports InterceptorRegistry and IPCInterceptor from interceptors (not ipc)
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
_IPC_PY = _ISOLATION_PKG / "ipc.py"
_INTERCEPTORS_PY = _ISOLATION_PKG / "interceptors.py"
_INIT_PY = _ISOLATION_PKG / "__init__.py"

_MOVED_SYMBOLS = [
    "IPCInterceptor",
    "InterceptorRegistry",
    "BudgetInterceptor",
    "ObserverInterceptor",
]

_STAY_IN_IPC = ["IPCServer", "IPCClient", "_is_async_iterable"]


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


def _get_import_from_modules(source: str, symbol: str) -> list[str]:
    """Return module paths that `symbol` is imported FROM in the given source."""
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.names:
            for alias in node.names:
                if alias.name == symbol or alias.asname == symbol:
                    modules.append(node.module or "")
    return modules


# ---------------------------------------------------------------------------
# 1. interceptors.py exists and all 4 symbols are importable from it
# ---------------------------------------------------------------------------


def test_interceptors_file_exists() -> None:
    """interceptors.py must exist in the isolation package."""
    assert _INTERCEPTORS_PY.exists(), (
        f"{_INTERCEPTORS_PY} does not exist -- interceptors.py has not been created yet"
    )


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_symbol_importable_from_interceptors(symbol_name: str) -> None:
    """Each moved symbol must be importable from runsight_core.isolation.interceptors."""
    module = importlib.import_module("runsight_core.isolation.interceptors")
    assert hasattr(module, symbol_name), (
        f"runsight_core.isolation.interceptors is missing symbol: {symbol_name}"
    )


# ---------------------------------------------------------------------------
# 2. The 4 symbols are NOT class/def-defined in ipc.py source text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_symbol_not_defined_in_ipc_py(symbol_name: str) -> None:
    """Moved symbols must no longer be defined (class/def/assignment) in ipc.py."""
    source = _IPC_PY.read_text(encoding="utf-8")
    defined_names = _top_level_definition_names(source)
    assert symbol_name not in defined_names, (
        f"Symbol '{symbol_name}' is still defined as a top-level name in ipc.py -- "
        "it must be removed and placed in interceptors.py"
    )


# ---------------------------------------------------------------------------
# 3. ipc.py does NOT re-export (no `from .interceptors import`, no __getattr__)
# ---------------------------------------------------------------------------


def test_ipc_py_has_no_reexport_from_interceptors() -> None:
    """ipc.py must not contain `from .interceptors import` -- no re-exports allowed."""
    source = _IPC_PY.read_text(encoding="utf-8")
    assert "from .interceptors import" not in source, (
        "ipc.py contains a re-export: `from .interceptors import`. "
        "Per RUN-818, ipc.py must not re-export symbols from interceptors."
    )
    assert "from runsight_core.isolation.interceptors import" not in source, (
        "ipc.py contains an absolute re-export from interceptors. "
        "Per RUN-818, ipc.py must not re-export symbols from interceptors."
    )


def test_ipc_py_has_no_getattr_fallback() -> None:
    """ipc.py must not define a __getattr__ function for lazy re-exports."""
    source = _IPC_PY.read_text(encoding="utf-8")
    defined_names = _top_level_definition_names(source)
    assert "__getattr__" not in defined_names, (
        "ipc.py defines a __getattr__ function -- no lazy re-export fallbacks allowed per RUN-818."
    )


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_ipc_py_does_not_re_export_individual_symbol(symbol_name: str) -> None:
    """ipc.py must not import individual moved symbols to re-export them."""
    source = _IPC_PY.read_text(encoding="utf-8")
    modules = _get_import_from_modules(source, symbol_name)
    interceptors_imports = [m for m in modules if "interceptors" in m]
    assert not interceptors_imports, (
        f"ipc.py re-exports '{symbol_name}' from interceptors (via: {interceptors_imports}). "
        "No re-exports allowed per RUN-818."
    )


# ---------------------------------------------------------------------------
# 4. IPCServer, IPCClient, _is_async_iterable remain in ipc.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol_name", _STAY_IN_IPC)
def test_ipc_residents_still_defined_in_ipc_py(symbol_name: str) -> None:
    """IPCServer, IPCClient, and _is_async_iterable must remain as top-level definitions in ipc.py."""
    source = _IPC_PY.read_text(encoding="utf-8")
    defined_names = _top_level_definition_names(source)
    assert symbol_name in defined_names, (
        f"'{symbol_name}' is no longer defined in ipc.py -- it must stay there."
    )


@pytest.mark.parametrize("symbol_name", ["IPCServer", "IPCClient"])
def test_ipc_residents_module_is_ipc_not_interceptors(symbol_name: str) -> None:
    """IPCServer and IPCClient must be defined in the ipc module, not interceptors."""
    ipc_module = importlib.import_module("runsight_core.isolation.ipc")
    obj = getattr(ipc_module, symbol_name, None)
    assert obj is not None, f"runsight_core.isolation.ipc is missing '{symbol_name}'"
    defining_module = getattr(obj, "__module__", "") or ""
    assert "interceptors" not in defining_module, (
        f"'{symbol_name}' reports __module__={defining_module!r}, "
        "suggesting it was moved to interceptors. It must stay in ipc."
    )


# ---------------------------------------------------------------------------
# 5. __init__.py imports InterceptorRegistry and IPCInterceptor from interceptors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol_name", ["InterceptorRegistry", "IPCInterceptor"])
def test_init_imports_from_interceptors_not_ipc(symbol_name: str) -> None:
    """isolation/__init__.py must import InterceptorRegistry and IPCInterceptor from interceptors, not ipc."""
    source = _INIT_PY.read_text(encoding="utf-8")
    modules = _get_import_from_modules(source, symbol_name)

    # Must have at least one import of the symbol
    assert modules, (
        f"__init__.py does not import {symbol_name} at all -- "
        f"expected `from runsight_core.isolation.interceptors import {symbol_name}`"
    )

    # Must not import from ipc
    ipc_direct_imports = [
        m for m in modules if m.endswith(".ipc") or m == "runsight_core.isolation.ipc"
    ]
    assert not ipc_direct_imports, (
        f"__init__.py still imports {symbol_name} from ipc ({ipc_direct_imports}). "
        "After RUN-818, it must import from interceptors instead."
    )

    # Must import from interceptors
    interceptors_imports = [m for m in modules if "interceptors" in m]
    assert interceptors_imports, (
        f"__init__.py imports {symbol_name} from {modules} but not from interceptors. "
        f"Expected `from runsight_core.isolation.interceptors import {symbol_name}`."
    )
