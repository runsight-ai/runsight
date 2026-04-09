"""
Shared test infrastructure for runsight_core tests.
"""

import asyncio
import importlib
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
from runsight_core.primitives import Soul


# Python 3.14 removed the implicit event-loop creation in get_event_loop().
# Ensure a loop exists so legacy sync tests that call
# ``asyncio.get_event_loop().run_until_complete(...)`` still work.
@pytest.fixture(autouse=True)
def _ensure_event_loop():
    """Guarantee an asyncio event loop is set for every test."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def make_test_yaml(steps_yaml: str) -> str:
    """Wrap step YAML with a standard souls section containing a 'test' soul.

    Args:
        steps_yaml: Block definitions YAML (indented with 2 spaces per block).

    Returns:
        Full workflow YAML string that includes a 'test' soul definition,
        so that ``parse_workflow_yaml`` can resolve ``soul_ref: test``.
    """
    # Extract block names from the steps_yaml for transitions
    import re

    block_names = re.findall(r"^  (\w+):", steps_yaml, re.MULTILINE)
    entry = block_names[0] if block_names else "my_block"

    # Build transitions: chain blocks linearly, last one is terminal
    transitions = ""
    for i, name in enumerate(block_names):
        if i < len(block_names) - 1:
            transitions += f"    - from: {name}\n      to: {block_names[i + 1]}\n"
        else:
            transitions += f"    - from: {name}\n      to: null\n"

    return f"""\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
{steps_yaml}
workflow:
  name: test_workflow
  entry: {entry}
  transitions:
{transitions}"""


@pytest.fixture
def tmp_path(request):
    """Override tmp_path with a shorter base to avoid AF_UNIX path length limits on macOS."""
    with tempfile.TemporaryDirectory(prefix="rs_") as d:
        yield Path(d)


@pytest.fixture
def test_souls_map():
    """Provide a souls map with a 'test' Soul for tests that construct blocks directly."""
    return {
        "test": Soul(
            id="test_1",
            role="Tester",
            system_prompt="You test things.",
        )
    }


def _workflow_repo_import_stubs() -> dict[str, ModuleType]:
    """Return temporary module stubs for API-adjacent core tests.

    These tests import ``workflow_repo`` from source even when the full API
    dependency set is not installed. The stubs keep those imports local to the
    test so they do not poison the wider session.
    """

    api_src = Path(__file__).resolve().parents[3] / "apps" / "api" / "src" / "runsight_api"
    stubs: dict[str, ModuleType] = {}

    for module_name, module_path in {
        "runsight_api": api_src,
        "runsight_api.core": api_src / "core",
        "runsight_api.data": api_src / "data",
        "runsight_api.data.filesystem": api_src / "data" / "filesystem",
        "runsight_api.domain": api_src / "domain",
    }.items():
        module = ModuleType(module_name)
        module.__path__ = [str(module_path)]
        stubs[module_name] = module

    structlog_stub = ModuleType("structlog")
    structlog_stub.contextvars = SimpleNamespace(
        bind_contextvars=lambda **_: None,
        unbind_contextvars=lambda *_, **__: None,
    )
    stubs["structlog"] = structlog_stub

    ruamel_stub = ModuleType("ruamel")
    ruamel_yaml_stub = ModuleType("ruamel.yaml")

    class _YAML:
        pass

    ruamel_yaml_stub.YAML = _YAML
    ruamel_stub.yaml = ruamel_yaml_stub
    stubs["ruamel"] = ruamel_stub
    stubs["ruamel.yaml"] = ruamel_yaml_stub

    sqlmodel_stub = ModuleType("sqlmodel")

    class _SQLModel:
        metadata = SimpleNamespace(
            create_all=lambda *_args, **_kwargs: None,
            drop_all=lambda *_args, **_kwargs: None,
        )

    class _Session:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    sqlmodel_stub.SQLModel = _SQLModel
    sqlmodel_stub.Session = _Session
    sqlmodel_stub.Field = lambda *args, **kwargs: None
    sqlmodel_stub.Relationship = lambda *args, **kwargs: None
    sqlmodel_stub.create_engine = lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs)
    stubs["sqlmodel"] = sqlmodel_stub

    return stubs


@pytest.fixture
def workflow_repo_module():
    """Load ``workflow_repo`` with temporary stubs that are cleaned up per test."""

    @contextmanager
    def _load():
        with patch.dict(sys.modules, _workflow_repo_import_stubs()):
            sys.modules.pop("runsight_api.domain.errors", None)
            sys.modules.pop("runsight_api.domain.value_objects", None)
            sys.modules.pop("runsight_api.data.filesystem.workflow_repo", None)
            importlib.invalidate_caches()
            module = importlib.import_module("runsight_api.data.filesystem.workflow_repo")
            try:
                yield module
            finally:
                sys.modules.pop("runsight_api.domain.errors", None)
                sys.modules.pop("runsight_api.domain.value_objects", None)
                sys.modules.pop("runsight_api.data.filesystem.workflow_repo", None)

    return _load


def _tools_router_import_stubs() -> dict[str, ModuleType]:
    """Return temporary module stubs for the tools router scanner test."""

    root = Path(__file__).resolve().parents[3]
    api_src = root / "apps" / "api" / "src" / "runsight_api"
    stubs: dict[str, ModuleType] = {}

    for module_name, module_path in {
        "runsight_api": api_src,
        "runsight_api.core": api_src / "core",
        "runsight_api.transport": api_src / "transport",
        "runsight_api.transport.routers": api_src / "transport" / "routers",
        "runsight_api.transport.schemas": api_src / "transport" / "schemas",
        "runsight_api.domain": api_src / "domain",
    }.items():
        module = ModuleType(module_name)
        module.__path__ = [str(module_path)]
        stubs[module_name] = module

    config_module = ModuleType("runsight_api.core.config")
    config_module.settings = SimpleNamespace(base_path=".")
    stubs["runsight_api.core.config"] = config_module

    errors_module = ModuleType("runsight_api.domain.errors")

    class InputValidationError(Exception):
        pass

    errors_module.InputValidationError = InputValidationError
    stubs["runsight_api.domain.errors"] = errors_module

    fastapi_module = ModuleType("fastapi")

    class _APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    fastapi_module.APIRouter = _APIRouter
    stubs["fastapi"] = fastapi_module

    return stubs


@pytest.fixture
def tools_router_module():
    """Load the tools router with temporary stubs that are cleaned up per test."""

    @contextmanager
    def _load():
        with patch.dict(sys.modules, _tools_router_import_stubs()):
            sys.modules.pop("runsight_api.transport.routers.tools", None)
            importlib.invalidate_caches()
            module = importlib.import_module("runsight_api.transport.routers.tools")
            try:
                yield module
            finally:
                sys.modules.pop("runsight_api.transport.routers.tools", None)

    return _load
