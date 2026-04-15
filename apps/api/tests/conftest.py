"""Pytest configuration for API tests."""

import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Test DB: temp-file SQLite so all connections share the same database.
# :memory: gives each connection its own isolated DB — tables created by
# Alembic or create_all() are invisible to other connections.
# ---------------------------------------------------------------------------
_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), f"runsight_test_{os.getpid()}.db")
os.environ["RUNSIGHT_DB_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["RUNSIGHT_BASE_PATH"] = os.environ.get("RUNSIGHT_BASE_PATH", tempfile.gettempdir())


@pytest.fixture(scope="session", autouse=True)
def _create_test_tables():
    """Create all DB tables once per session, tear down after."""
    from sqlmodel import SQLModel

    from runsight_api.core.di import engine
    from runsight_api.domain import entities as _entities  # noqa: F401 — register models

    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)
    # Remove the temp DB file
    try:
        os.unlink(_TEST_DB_PATH)
    except OSError:
        pass


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

    API tests mock litellm and run Workflow.run(). Without this bypass,
    IsolatedBlockWrapper spawns a real subprocess where mocks are invisible.

    Patches SubprocessHarness.run so the wrapper's real execute() path
    (envelope construction, result mapping) is exercised while the
    subprocess spawn is replaced with an in-process call to the inner block.
    """
    from types import SimpleNamespace

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
        the real socket/subprocess implementation.
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
        """Execute in-process when harness is real, forward when harness is a test mock."""
        if self.harness is None:
            if self._harness_factory is None:
                raise NotImplementedError(
                    "SubprocessHarness is not configured on IsolatedBlockWrapper"
                )
            self.harness = self._harness_factory()

        if type(self.harness).__name__ in ("MagicMock", "AsyncMock"):
            return await self.harness.run(envelope)

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

        result_state = await self.inner_block.execute(state)

        block_result = result_state.results.get(self.inner_block.block_id, BlockResult(output=""))

        delegate_artifacts: dict[str, DelegateArtifact] = {}
        port_prefix = f"{self.inner_block.block_id}."
        for key, val in result_state.results.items():
            if key.startswith(port_prefix):
                port = key[len(port_prefix) :]
                output_text = val.output if isinstance(val, BlockResult) else str(val)
                delegate_artifacts[port] = DelegateArtifact(task=output_text)

        return SimpleNamespace(
            block_id=envelope.block_id,
            output=block_result.output,
            exit_handle=block_result.exit_handle,
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
