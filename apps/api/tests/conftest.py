"""Pytest configuration for API tests."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Test runtime root: force a pytest-owned workspace regardless of developer env.
#
# API tests must never inherit a real RUNSIGHT_BASE_PATH or place runsight.db in
# a shared temp root. They also must not inherit shell credentials, because API
# key resolution checks os.environ before .runsight/secrets.env. Keep runtime
# workspace, DB state, and provider credentials isolated by default.
#
# Test DB: temp-file SQLite so all connections share the same database.
# :memory: gives each connection its own isolated DB — tables created by
# Alembic or create_all() are invisible to other connections.
# ---------------------------------------------------------------------------
_SECRET_ENV_FRAGMENTS = (
    "API_KEY",
    "ACCESS_KEY",
    "CREDENTIAL",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
)
_RUNSIGHT_ENV_ALLOWLIST = {"RUNSIGHT_BASE_PATH", "RUNSIGHT_DB_URL"}
_TEST_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "main")
_TEST_RUNTIME_ROOT = Path(
    tempfile.mkdtemp(prefix=f"runsight-api-pytest-{_TEST_WORKER_ID}-{os.getpid()}-")
).resolve()
_TEST_RUNSIGHT_DIR = _TEST_RUNTIME_ROOT / ".runsight"
_TEST_RUNSIGHT_DIR.mkdir(parents=True, exist_ok=True)
_TEST_DB_PATH = _TEST_RUNSIGHT_DIR / "runsight.db"
_TEST_WORKSPACE_API_KEYS = {
    "anthropic": "dummy-test-api-key",
    "azure": "dummy-test-api-key",
    "gemini": "dummy-test-api-key",
    "google": "dummy-test-api-key",
    "groq": "dummy-test-api-key",
    "mistral": "dummy-test-api-key",
    "openai": "dummy-test-api-key",
    "openrouter": "dummy-test-api-key",
}


def _scrub_inherited_runtime_env() -> None:
    for name in tuple(os.environ):
        if name.startswith("RUNSIGHT_") and name not in _RUNSIGHT_ENV_ALLOWLIST:
            os.environ.pop(name, None)
            continue
        if any(fragment in name for fragment in _SECRET_ENV_FRAGMENTS):
            os.environ.pop(name, None)


_scrub_inherited_runtime_env()
os.environ["RUNSIGHT_BASE_PATH"] = str(_TEST_RUNTIME_ROOT)
os.environ["RUNSIGHT_DB_URL"] = f"sqlite:///{_TEST_DB_PATH}"


@pytest.fixture(scope="session", autouse=True)
def _create_test_tables():
    """Create all DB tables once per session, tear down after."""
    from sqlmodel import SQLModel

    from runsight_api.core.di import engine
    from runsight_api.domain import entities as _entities  # noqa: F401 — register models

    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)
    try:
        os.unlink(_TEST_DB_PATH)
    except OSError:
        pass
    shutil.rmtree(_TEST_RUNTIME_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clear_context_vars():
    """Reset all context vars after each test to prevent cross-test pollution."""
    yield
    from runsight_api.core.context import clear_execution_context, request_id

    clear_execution_context()
    request_id.set("")


@pytest.fixture(autouse=True)
def _bypass_subprocess_isolation(monkeypatch):
    """Keep block execution in-process so litellm mocks are visible.

    API tests mock litellm and run Workflow.run(). Without this bypass, the
    workspace harness launches a real worker where mocks are invisible.

    Patches UnixLocalHarness.run so the wrapper's real execute() path (request
    construction, result mapping) is exercised while the worker launch is
    replaced with an in-process worker simulation at the harness boundary.
    """
    try:
        from runsight_core.isolation.envelope import (
            DelegateArtifact,
            ResultEnvelope,
        )
        from runsight_core.isolation.workspace import (
            UnixLocalHarness,
            WorkspaceHostBindings,
            WorkspaceMaterializer,
            WorkspaceRunRequest,
        )
    except ImportError:
        return

    class _InProcessIPCClient:
        """Tiny IPC client facade backed by the harness's host-side handlers."""

        def __init__(self, handlers):
            self._handlers = handlers

        async def request(self, name, payload):
            handler = self._handlers[name]
            result = handler(payload)
            if hasattr(result, "__await__"):
                return await result
            return result

        async def request_stream(self, name, payload):
            handler = self._handlers[name]
            stream = handler(payload)
            if hasattr(stream, "__await__"):
                stream = await stream
            async for chunk in stream:
                yield chunk

        async def connect(self):
            return {"accepted": True, "error": None}

        async def close(self):
            return None

    def _with_test_api_keys(request: WorkspaceRunRequest) -> WorkspaceRunRequest:
        host_bindings = request.host_bindings or WorkspaceHostBindings()
        if host_bindings.api_keys:
            return request

        return request.model_copy(
            update={
                "host_bindings": host_bindings.model_copy(
                    update={"api_keys": dict(_TEST_WORKSPACE_API_KEYS)}
                )
            }
        )

    async def _in_process_workspace_run(
        self: UnixLocalHarness, request: WorkspaceRunRequest
    ) -> ResultEnvelope:
        """Run the worker logic in-process at the workspace harness boundary."""
        from runsight_core.block_io import BlockContext, BlockOutput, build_block_context
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import worker_proxies as _proxies
        from runsight_core.isolation import worker_support as _support

        from runsight_core.state import BlockResult

        request = _with_test_api_keys(request)
        session = self._session_factory.create(request.manifest, request.policy)
        session = WorkspaceMaterializer(session).materialize(
            request.manifest,
            policy=request.policy,
        )
        envelope = self._worker_envelope(request)
        ipc_client = _InProcessIPCClient(self._build_ipc_handlers(request=request, session=session))

        try:
            resolved_tools = _proxies.create_tool_stubs(envelope.tools, ipc_client=ipc_client)
            soul = _support.reconstruct_soul(envelope.soul, resolved_tools=resolved_tools)
            runner = _proxies.create_runner(
                model_name=envelope.soul.model_name,
                ipc_client=ipc_client,
            )
            state = _support.build_scoped_state(envelope)

            history_key = f"{envelope.block_id}_{envelope.soul.id}"
            history = state.conversation_histories.get(history_key, [])
            budgeted_history = history
            if history:
                budgeted_history = _support.build_budgeted_history(
                    model=envelope.soul.model_name,
                    system_prompt=soul.system_prompt,
                    instruction=envelope.prompt.instruction,
                    conversation_history=history,
                )

            active_budget = _active_budget.get(None)
            if isinstance(active_budget, BudgetSession):
                active_budget.check_or_raise(block_id=envelope.block_id)

            budget_token = _active_budget.set(None)
            try:
                block = _support._create_block(envelope, soul, runner)
                block_type = _support._BLOCK_TYPE_MAP.get(
                    envelope.block_type.lower(),
                    envelope.block_type.lower(),
                )
                if block_type == "assertion":
                    raw_context = envelope.prompt.context
                    context_text = None
                    if isinstance(raw_context, dict):
                        context_text = raw_context.get("text") or None
                    elif isinstance(raw_context, str):
                        context_text = raw_context or None
                    block_ctx = BlockContext(
                        block_id=envelope.block_id,
                        instruction=envelope.prompt.instruction,
                        context=context_text,
                        inputs=dict(envelope.inputs),
                        conversation_history=budgeted_history,
                        soul=soul,
                        model_name=envelope.soul.model_name,
                        state_snapshot=state,
                    )
                else:
                    base_ctx = build_block_context(block, state)
                    block_ctx = base_ctx.model_copy(
                        update={
                            "inputs": {**base_ctx.inputs, **dict(envelope.inputs)},
                            "conversation_history": budgeted_history,
                        }
                    )
                block_output = await block.execute(block_ctx)
            finally:
                _active_budget.reset(budget_token)

            if not isinstance(block_output, BlockOutput):
                return ResultEnvelope(
                    block_id=envelope.block_id,
                    output=None,
                    exit_handle="error",
                    cost_usd=0.0,
                    total_tokens=0,
                    tool_calls_made=0,
                    delegate_artifacts={},
                    conversation_history=[],
                    error=f"worker block returned {type(block_output).__name__}",
                    error_type="TypeError",
                )

            if isinstance(active_budget, BudgetSession):
                active_budget.accrue(
                    cost_usd=block_output.cost_usd,
                    tokens=block_output.total_tokens,
                )

            delegate_artifacts: dict[str, DelegateArtifact] = {}
            if block_type == "dispatch" and block_output.extra_results:
                port_prefix = f"{envelope.block_id}."
                for key, val in block_output.extra_results.items():
                    if key.startswith(port_prefix):
                        port = key[len(port_prefix) :]
                        output_text = val.output if isinstance(val, BlockResult) else str(val)
                        delegate_artifacts[port] = DelegateArtifact(prompt=output_text)

            conversation_history = list(budgeted_history)
            if (
                block_output.conversation_updates
                and history_key in block_output.conversation_updates
            ):
                conversation_history += block_output.conversation_updates[history_key]
            elif (
                block_output.conversation_replacements
                and history_key in block_output.conversation_replacements
            ):
                conversation_history = block_output.conversation_replacements[history_key]

            return ResultEnvelope(
                block_id=envelope.block_id,
                output=block_output.output if block_output.output else None,
                exit_handle=block_output.exit_handle or "done",
                cost_usd=block_output.cost_usd,
                total_tokens=block_output.total_tokens,
                tool_calls_made=len(delegate_artifacts),
                delegate_artifacts=delegate_artifacts,
                conversation_history=conversation_history,
                error=None,
                error_type=None,
            )
        finally:
            if self._should_cleanup(succeeded=True):
                shutil.rmtree(session.host_root, ignore_errors=True)
                self._cleanup_owned_session_base_root()

    monkeypatch.setattr(UnixLocalHarness, "run", _in_process_workspace_run)
