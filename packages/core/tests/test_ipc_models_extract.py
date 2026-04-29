"""
Failing tests for RUN-817: Extract ipc_models.py from ipc.py.

Acceptance criteria verified:
1. All 8 symbols are importable from runsight_core.isolation.ipc_models
2. None of the 8 symbols are class/def-defined in ipc.py source text
3. ipc.py does NOT re-export the symbols via `from .ipc_models import`
4. __init__.py imports GrantToken from ipc_models (not from ipc)
5. IPCServer and IPCClient remain defined in ipc.py
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
_IPC_MODELS_PY = _ISOLATION_PKG / "ipc_models.py"
_INIT_PY = _ISOLATION_PKG / "__init__.py"

_MOVED_SYMBOLS = [
    "RPC_ALLOWLIST",
    "_current_ipc_request_id",
    "HandlerResult",
    "Handler",
    "GrantToken",
    "IPCRequest",
    "CapabilityRequest",
    "CapabilityResponse",
    "IPCResponseFrame",
]

_STAY_IN_IPC = ["IPCServer", "IPCClient"]


# ---------------------------------------------------------------------------
# 1. ipc_models.py exists and all 8 symbols are importable from it
# ---------------------------------------------------------------------------


def test_ipc_models_file_exists() -> None:
    """ipc_models.py must exist in the isolation package."""
    assert _IPC_MODELS_PY.exists(), (
        f"{_IPC_MODELS_PY} does not exist — ipc_models.py has not been created yet"
    )


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_symbol_importable_from_ipc_models(symbol_name: str) -> None:
    """Each moved symbol must be importable from runsight_core.isolation.ipc_models."""
    module = importlib.import_module("runsight_core.isolation.ipc_models")
    assert hasattr(module, symbol_name), (
        f"runsight_core.isolation.ipc_models is missing symbol: {symbol_name}"
    )


# ---------------------------------------------------------------------------
# 2. The 8 symbols are NOT class/def-defined in ipc.py source text
# ---------------------------------------------------------------------------


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


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_symbol_not_defined_in_ipc_py(symbol_name: str) -> None:
    """Moved symbols must no longer be defined (class/def/assignment) in ipc.py."""
    source = _IPC_PY.read_text(encoding="utf-8")
    defined_names = _top_level_definition_names(source)
    assert symbol_name not in defined_names, (
        f"Symbol '{symbol_name}' is still defined as a top-level name in ipc.py — "
        "it must be removed and placed in ipc_models.py"
    )


# ---------------------------------------------------------------------------
# 3. ipc.py does NOT re-export the symbols via `from .ipc_models import`
# ---------------------------------------------------------------------------


def test_ipc_py_has_no_reexport_from_ipc_models() -> None:
    """ipc.py must not contain `from .ipc_models import` — no re-exports allowed."""
    source = _IPC_PY.read_text(encoding="utf-8")
    # Check the raw source text for any re-export statement
    assert "from .ipc_models import" not in source, (
        "ipc.py contains a re-export: `from .ipc_models import`. "
        "Per RUN-817, ipc.py must not re-export symbols from ipc_models."
    )
    assert "from runsight_core.isolation.ipc_models import" not in source, (
        "ipc.py contains an absolute re-export from ipc_models. "
        "Per RUN-817, ipc.py must not re-export symbols from ipc_models."
    )


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


@pytest.mark.parametrize("symbol_name", _MOVED_SYMBOLS)
def test_ipc_py_does_not_re_export_individual_symbol(symbol_name: str) -> None:
    """ipc.py must not import individual moved symbols to re-export them."""
    source = _IPC_PY.read_text(encoding="utf-8")
    modules = _get_import_from_modules(source, symbol_name)
    ipc_models_imports = [m for m in modules if "ipc_models" in m]
    assert not ipc_models_imports, (
        f"ipc.py re-exports '{symbol_name}' from ipc_models (via: {ipc_models_imports}). "
        "No re-exports allowed per RUN-817."
    )


# ---------------------------------------------------------------------------
# 4. __init__.py imports GrantToken from ipc_models (not from ipc)
# ---------------------------------------------------------------------------


def test_init_imports_grant_token_from_ipc_models_not_ipc() -> None:
    """isolation/__init__.py must import GrantToken from ipc_models, not from ipc."""
    source = _INIT_PY.read_text(encoding="utf-8")
    modules = _get_import_from_modules(source, "GrantToken")

    # Must have at least one import of GrantToken
    assert modules, (
        "__init__.py does not import GrantToken at all — "
        "expected `from runsight_core.isolation.ipc_models import GrantToken`"
    )

    # Must not import from ipc
    ipc_direct_imports = [
        m for m in modules if m.endswith(".ipc") or m == "runsight_core.isolation.ipc"
    ]
    assert not ipc_direct_imports, (
        f"__init__.py still imports GrantToken from ipc ({ipc_direct_imports}). "
        "After RUN-817, it must import from ipc_models instead."
    )

    # Must import from ipc_models
    ipc_models_imports = [m for m in modules if "ipc_models" in m]
    assert ipc_models_imports, (
        f"__init__.py imports GrantToken from {modules} but not from ipc_models. "
        "Expected `from runsight_core.isolation.ipc_models import GrantToken`."
    )


# ---------------------------------------------------------------------------
# 5. IPCServer and IPCClient remain defined in ipc.py (not moved)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol_name", _STAY_IN_IPC)
def test_ipc_residents_still_defined_in_ipc_py(symbol_name: str) -> None:
    """IPCServer and IPCClient must remain as top-level definitions in ipc.py."""
    source = _IPC_PY.read_text(encoding="utf-8")
    defined_names = _top_level_definition_names(source)
    assert symbol_name in defined_names, (
        f"'{symbol_name}' is no longer defined in ipc.py — it must stay there."
    )


@pytest.mark.parametrize("symbol_name", _STAY_IN_IPC)
def test_ipc_residents_module_is_ipc_not_ipc_models(symbol_name: str) -> None:
    """IPCServer and IPCClient must be defined in the ipc module, not ipc_models."""
    ipc_module = importlib.import_module("runsight_core.isolation.ipc")
    obj = getattr(ipc_module, symbol_name, None)
    assert obj is not None, f"runsight_core.isolation.ipc is missing '{symbol_name}'"
    # The class's defining module must be ipc, not ipc_models
    defining_module = getattr(obj, "__module__", "") or ""
    assert "ipc_models" not in defining_module, (
        f"'{symbol_name}' reports __module__={defining_module!r}, "
        "suggesting it was moved to ipc_models. It must stay in ipc."
    )
    assert defining_module.endswith(".ipc") or defining_module == "runsight_core.isolation.ipc", (
        f"'{symbol_name}' has unexpected __module__={defining_module!r}"
    )
