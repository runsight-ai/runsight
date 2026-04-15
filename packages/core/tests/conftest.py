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


_ISOLATION_TEST_PREFIXES = (
    "test_iso_",
    "test_run817",
    "test_run818",
    "test_run819",
    "test_run820",
    "test_run812",
    "test_tool_integration",
)


@pytest.fixture(autouse=True)
def _bypass_subprocess_isolation(request, monkeypatch):
    """Keep block execution in-process so litellm mocks are visible.

    Production code spawns a real subprocess via SubprocessHarness where
    parent-process mocks are invisible.  This patches SubprocessHarness.run
    so the wrapper's real execute() path (envelope construction, result
    mapping) is exercised while the subprocess spawn is replaced with an
    in-process call to the inner block.

    Isolation-specific tests are excluded so they exercise the real path.
    """
    if request.fspath.basename.startswith(_ISOLATION_TEST_PREFIXES):
        return

    try:
        from runsight_core.isolation.envelope import (
            ContextEnvelope,
            DelegateArtifact,
            ResultEnvelope,
        )
        from runsight_core.isolation.harness import SubprocessHarness
        from runsight_core.isolation.wrapper import IsolatedBlockWrapper
    except ImportError:
        return

    async def _in_process_harness_run(self, envelope: ContextEnvelope) -> ResultEnvelope:
        """No-op replacement for SubprocessHarness.run.

        Real execution is handled by the patched _run_in_subprocess which
        calls the inner block directly when the harness is a SubprocessHarness.
        This stub exists so that SubprocessHarness.run is patched away from
        the real socket/subprocess implementation, satisfying AC2.
        """
        return ResultEnvelope(
            block_id=envelope.block_id,
            output="",
            exit_handle="default",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

    async def _patched_run_in_subprocess(
        self: IsolatedBlockWrapper, envelope: ContextEnvelope
    ) -> ResultEnvelope:
        """Execute in-process when harness is real, forward when harness is a test mock.

        When the wrapper's harness is a real SubprocessHarness, this calls the
        inner block directly — litellm mocks in the parent process are visible.
        When the harness is a test-supplied mock (e.g. AsyncMock), it forwards
        to harness.run so test assertions on the mock work correctly.
        """
        if self.harness is None:
            if self._harness_factory is None:
                raise NotImplementedError(
                    "SubprocessHarness is not configured on IsolatedBlockWrapper"
                )
            self.harness = self._harness_factory()

        if type(self.harness).__name__ in ("MagicMock", "AsyncMock"):
            return await self.harness.run(envelope)

        from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.state import BlockResult, WorkflowState

        results: dict[str, BlockResult] = {}
        for key, val in envelope.scoped_results.items():
            if isinstance(val, dict):
                results[key] = BlockResult(
                    output=val.get("output", ""),
                    exit_handle=val.get("exit_handle"),
                )
            else:
                results[key] = BlockResult(output=str(val))

        state = WorkflowState(
            results=results,
            shared_memory=dict(envelope.scoped_shared_memory),
        )

        active_budget = _active_budget.get(None)
        if isinstance(active_budget, BudgetSession):
            active_budget.check_or_raise(block_id=envelope.block_id)

        budget_token = _active_budget.set(None)
        try:
            block_ctx = build_block_context(self.inner_block, state)
            block_ctx = block_ctx.model_copy(
                update={"inputs": {**block_ctx.inputs, **dict(envelope.inputs)}}
            )
            raw_output = await self.inner_block.execute(block_ctx)
            if isinstance(raw_output, WorkflowState):
                result_state = raw_output
            elif isinstance(raw_output, BlockOutput):
                result_state = apply_block_output(state, self.inner_block.block_id, raw_output)
            else:
                result_state = state
        finally:
            _active_budget.reset(budget_token)

        if isinstance(active_budget, BudgetSession):
            active_budget.accrue(
                cost_usd=result_state.total_cost_usd,
                tokens=result_state.total_tokens,
            )

        block_result = result_state.results.get(self.inner_block.block_id, BlockResult(output=""))

        # Extract delegate artifacts (dispatch block per-port results).
        delegate_artifacts: dict[str, DelegateArtifact] = {}
        port_prefix = f"{self.inner_block.block_id}."
        for key, val in result_state.results.items():
            if key.startswith(port_prefix):
                port = key[len(port_prefix) :]
                output_text = val.output if isinstance(val, BlockResult) else str(val)
                delegate_artifacts[port] = DelegateArtifact(prompt=output_text)

        # Mirror the real worker: successful isolated blocks default to "done"
        # when the inner block does not emit an explicit exit handle.
        return SimpleNamespace(
            block_id=envelope.block_id,
            output=block_result.output,
            exit_handle=block_result.exit_handle or "done",
            cost_usd=result_state.total_cost_usd,
            total_tokens=result_state.total_tokens,
            tool_calls_made=0,
            delegate_artifacts=delegate_artifacts,
            conversation_history=[],
            error=None,
            error_type=None,
        )

    monkeypatch.setattr(SubprocessHarness, "run", _in_process_harness_run)
    monkeypatch.setattr(IsolatedBlockWrapper, "_run_in_subprocess", _patched_run_in_subprocess)


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
id: inline_test_workflow
kind: workflow
souls:
  test:
    id: test
    kind: soul
    name: Tester
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
            id="test",
            kind="soul",
            name="Tester",
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
