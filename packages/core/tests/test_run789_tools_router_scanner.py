from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_API_SRC = _ROOT / "apps" / "api" / "src" / "runsight_api"

for module_name, module_path in {
    "runsight_api": _API_SRC,
    "runsight_api.core": _API_SRC / "core",
    "runsight_api.transport": _API_SRC / "transport",
    "runsight_api.transport.routers": _API_SRC / "transport" / "routers",
    "runsight_api.transport.schemas": _API_SRC / "transport" / "schemas",
    "runsight_api.domain": _API_SRC / "domain",
}.items():
    if module_name not in sys.modules:
        module = ModuleType(module_name)
        module.__path__ = [str(module_path)]
        sys.modules[module_name] = module

if "runsight_api.core.config" not in sys.modules:
    config_module = ModuleType("runsight_api.core.config")
    config_module.settings = SimpleNamespace(base_path=".")
    sys.modules["runsight_api.core.config"] = config_module

if "runsight_api.domain.errors" not in sys.modules:
    errors_module = ModuleType("runsight_api.domain.errors")

    class InputValidationError(Exception):
        pass

    errors_module.InputValidationError = InputValidationError
    sys.modules["runsight_api.domain.errors"] = errors_module

if "fastapi" not in sys.modules:
    fastapi_module = ModuleType("fastapi")

    class _APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    fastapi_module.APIRouter = _APIRouter
    sys.modules["fastapi"] = fastapi_module

tools_router = importlib.import_module("runsight_api.transport.routers.tools")


@pytest.mark.asyncio
async def test_list_tools_uses_tool_scanner(tmp_path):
    tools_router.settings.base_path = str(tmp_path)

    with patch("runsight_api.transport.routers.tools.ToolScanner") as mock_scanner:
        mock_scanner.return_value.scan.return_value.stems.return_value = {
            "lookup_profile": SimpleNamespace(
                name="Lookup Profile",
                description="Look up a profile.",
                executor="python",
            )
        }

        items = await tools_router.list_tools()

    assert any(item.id == "lookup_profile" for item in items)
    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.stems.assert_called_once()
