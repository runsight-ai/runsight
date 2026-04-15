"""
Failing tests for RUN-391: conftest mock-at-boundary fix.

The current conftest patches IsolatedBlockWrapper.execute, bypassing the
isolation boundary entirely. The correct fix is to patch SubprocessHarness.run
so the wrapper's envelope construction and result mapping are exercised.

Tests verify four properties of the corrected conftest:

1. IsolatedBlockWrapper.execute is NOT patched — it must be the real method.
2. SubprocessHarness.run IS patched — the conftest patches at the harness level.
3. The patched SubprocessHarness.run receives a ContextEnvelope and returns a
   ResultEnvelope, proving the wrapper built the envelope before calling the
   harness.
4. Isolation-specific test files (test_iso_* etc.) are excluded from the mock
   and exercise the real SubprocessHarness.run path.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    ResultEnvelope,
)
from runsight_core.isolation.harness import SubprocessHarness
from runsight_core.isolation.wrapper import IsolatedBlockWrapper

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _real_wrapper_execute_source() -> str:
    """Return the source of the real IsolatedBlockWrapper.execute implementation."""
    return inspect.getsource(IsolatedBlockWrapper.execute)


def _make_mock_runner() -> MagicMock:
    """Return a minimal mock RunsightTeamRunner sufficient for LinearBlock construction."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    runner.model_name = "gpt-4o-mini"
    return runner


def _make_result_envelope(block_id: str = "block-1") -> ResultEnvelope:
    return ResultEnvelope(
        block_id=block_id,
        output="mocked output",
        exit_handle="default",
        cost_usd=0.001,
        total_tokens=42,
        tool_calls_made=0,
        delegate_artifacts={},
        conversation_history=[],
        error=None,
        error_type=None,
    )


# ---------------------------------------------------------------------------
# AC1: IsolatedBlockWrapper.execute is NOT patched
# ---------------------------------------------------------------------------


class TestWrapperExecuteIsNotPatched:
    """The conftest must leave IsolatedBlockWrapper.execute untouched."""

    def test_execute_is_the_real_implementation(self):
        """IsolatedBlockWrapper.execute must be the genuine coroutine from wrapper.py."""
        # The real execute is defined directly on the class and contains the
        # ContextEnvelope construction logic.  A monkeypatch replacement would
        # either be a plain function without that logic or would be the
        # _in_process function defined inline in conftest.
        method = IsolatedBlockWrapper.execute
        source = inspect.getsource(method)
        # The real implementation builds a ContextEnvelope and calls
        # _run_in_subprocess.  If the conftest is still patching execute, the
        # source will be the short two-line bypass instead.
        assert "ContextEnvelope" in source, (
            "IsolatedBlockWrapper.execute appears to be patched by conftest — "
            "it does not contain the real ContextEnvelope construction logic. "
            "The conftest must patch SubprocessHarness.run instead."
        )

    def test_execute_calls_run_in_subprocess(self):
        """The real IsolatedBlockWrapper.execute must call _run_in_subprocess."""
        source = inspect.getsource(IsolatedBlockWrapper.execute)
        assert "_run_in_subprocess" in source, (
            "IsolatedBlockWrapper.execute has been replaced; the real method "
            "delegates to _run_in_subprocess which calls harness.run."
        )

    def test_execute_is_defined_on_isolated_block_wrapper_class(self):
        """execute must be defined on IsolatedBlockWrapper, not injected from outside.

        BaseBlock.__init_subclass__ installs a compatibility shim (defined in
        base.py) that wraps the original execute with functools.wraps.  The shim
        preserves the original via __wrapped__, so we inspect that to verify the
        real implementation lives in wrapper.py — not in conftest.py or elsewhere.
        """
        execute_fn = IsolatedBlockWrapper.execute
        # The shim preserves the original via functools.wraps.__wrapped__
        original_fn = getattr(execute_fn, "__wrapped__", execute_fn)
        source_file = inspect.getfile(original_fn)
        assert source_file.endswith("wrapper.py"), (
            f"IsolatedBlockWrapper.execute (original) is defined in '{source_file}', "
            "expected 'wrapper.py'. The conftest has replaced it."
        )


# ---------------------------------------------------------------------------
# AC2: SubprocessHarness.run IS patched in normal test context
# ---------------------------------------------------------------------------


class TestSubprocessHarnessRunIsPatched:
    """The conftest must monkeypatch SubprocessHarness.run to an in-process executor."""

    def test_harness_run_is_not_the_real_subprocess_spawner(self):
        """SubprocessHarness.run must be patched to avoid spawning real subprocesses.

        The real run() creates Unix sockets and spawns subprocesses.  In a
        patched state it should be an AsyncMock or a simple coroutine that does
        not create sockets.
        """
        run_method = SubprocessHarness.run
        source = inspect.getsource(run_method)
        # The real implementation calls create_socket and
        # asyncio.create_subprocess_exec.  If still unpatched these will appear
        # in its source.
        assert "create_socket" not in source or "AsyncMock" in str(type(run_method)), (
            "SubprocessHarness.run does not appear to be patched. "
            "The conftest must replace it with an in-process executor so that "
            "litellm mocks are visible and no real subprocesses are spawned."
        )

    def test_harness_run_is_a_coroutine_function(self):
        """The patched SubprocessHarness.run must still be awaitable."""
        run_method = SubprocessHarness.run
        # Either the class-level method is still the original (and thus a
        # coroutine function), or it has been patched to an AsyncMock.  Either
        # way it must be awaitable.  If the conftest patches at the harness
        # instance level during wrapper.execute, the class-level method is
        # still the real one here — that is fine for this check.
        assert inspect.iscoroutinefunction(run_method) or isinstance(run_method, AsyncMock), (
            "SubprocessHarness.run must be a coroutine function (or AsyncMock). "
            "Found: %s" % type(run_method)
        )


# ---------------------------------------------------------------------------
# AC3: Wrapper builds ContextEnvelope and passes it to harness.run
# ---------------------------------------------------------------------------


class TestWrapperBuildsEnvelopeBeforeCallingHarness:
    """IsolatedBlockWrapper.execute must construct a ContextEnvelope and pass it
    to harness.run, proving the envelope construction path is exercised."""

    @pytest.mark.asyncio
    async def test_harness_run_receives_context_envelope(self, test_souls_map):
        """harness.run must be called with a ContextEnvelope instance."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import Task, WorkflowState

        soul = test_souls_map["test"]

        inner_block = LinearBlock(
            block_id="block-1",
            soul=soul,
            runner=_make_mock_runner(),
        )

        received_envelopes: list[Any] = []

        async def _capture_run(envelope: ContextEnvelope) -> ResultEnvelope:
            received_envelopes.append(envelope)
            return _make_result_envelope(block_id=envelope.block_id)

        harness_mock = AsyncMock(spec=SubprocessHarness)
        harness_mock.run.side_effect = _capture_run

        wrapper = IsolatedBlockWrapper(
            block_id="block-1",
            inner_block=inner_block,
            harness=harness_mock,
        )

        task = Task(id="t-1", instruction="Do something.")
        state = WorkflowState(current_task=task)

        await wrapper.execute(state)

        assert len(received_envelopes) == 1, (
            "harness.run was not called exactly once. "
            "IsolatedBlockWrapper.execute may have been patched by conftest, "
            "bypassing the envelope construction."
        )
        assert isinstance(received_envelopes[0], ContextEnvelope), (
            "harness.run was not called with a ContextEnvelope. "
            "Got: %s" % type(received_envelopes[0])
        )

    @pytest.mark.asyncio
    async def test_context_envelope_contains_block_id(self, test_souls_map):
        """The ContextEnvelope passed to harness.run must have the correct block_id."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import Task, WorkflowState

        soul = test_souls_map["test"]
        inner_block = LinearBlock(block_id="my-block", soul=soul, runner=_make_mock_runner())

        received: list[ContextEnvelope] = []

        async def _capture(envelope: ContextEnvelope) -> ResultEnvelope:
            received.append(envelope)
            return _make_result_envelope(block_id=envelope.block_id)

        harness_mock = AsyncMock(spec=SubprocessHarness)
        harness_mock.run.side_effect = _capture

        wrapper = IsolatedBlockWrapper(
            block_id="my-block",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState(current_task=Task(id="t-2", instruction="Check envelope."))
        await wrapper.execute(state)

        assert received[0].block_id == "my-block", (
            "ContextEnvelope.block_id is '%s', expected 'my-block'. "
            "The wrapper execute path may be patched." % received[0].block_id
        )


# ---------------------------------------------------------------------------
# AC4: The mock returns a valid ResultEnvelope
# ---------------------------------------------------------------------------


class TestMockReturnsValidResultEnvelope:
    """When patched at the harness level, SubprocessHarness.run must return
    a ResultEnvelope with all required fields populated."""

    @pytest.mark.asyncio
    async def test_result_envelope_is_mapped_to_workflow_state(self, test_souls_map):
        """IsolatedBlockWrapper.execute must map ResultEnvelope back to WorkflowState."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import BlockResult, Task, WorkflowState

        soul = test_souls_map["test"]
        inner_block = LinearBlock(block_id="block-out", soul=soul, runner=_make_mock_runner())

        expected_output = "the answer is 42"

        async def _harness_run(envelope: ContextEnvelope) -> ResultEnvelope:
            return ResultEnvelope(
                block_id=envelope.block_id,
                output=expected_output,
                exit_handle="default",
                cost_usd=0.005,
                total_tokens=100,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            )

        harness_mock = AsyncMock(spec=SubprocessHarness)
        harness_mock.run.side_effect = _harness_run

        wrapper = IsolatedBlockWrapper(
            block_id="block-out",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState(current_task=Task(id="t-3", instruction="Map result."))
        result_state = await wrapper.execute(state)

        assert "block-out" in result_state.results, (
            "block-out not found in results after execute. "
            "Wrapper may have been patched and is not mapping ResultEnvelope."
        )
        block_result = result_state.results["block-out"]
        assert isinstance(block_result, BlockResult), "Expected BlockResult, got %s" % type(
            block_result
        )
        assert block_result.output == expected_output, (
            "Expected output '%s', got '%s'. "
            "ResultEnvelope was not mapped correctly." % (expected_output, block_result.output)
        )

    @pytest.mark.asyncio
    async def test_cost_and_tokens_accumulated_from_result_envelope(self, test_souls_map):
        """cost_usd and total_tokens from ResultEnvelope must be added to WorkflowState."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import Task, WorkflowState

        soul = test_souls_map["test"]
        inner_block = LinearBlock(block_id="block-cost", soul=soul, runner=_make_mock_runner())

        async def _harness_run(envelope: ContextEnvelope) -> ResultEnvelope:
            return ResultEnvelope(
                block_id=envelope.block_id,
                output="done",
                exit_handle="default",
                cost_usd=0.012,
                total_tokens=256,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            )

        harness_mock = AsyncMock(spec=SubprocessHarness)
        harness_mock.run.side_effect = _harness_run

        wrapper = IsolatedBlockWrapper(
            block_id="block-cost",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState(current_task=Task(id="t-4", instruction="Check cost."))
        result_state = await wrapper.execute(state)

        assert result_state.total_cost_usd == pytest.approx(0.012), (
            "total_cost_usd was not updated from ResultEnvelope. "
            "Got: %s" % result_state.total_cost_usd
        )
        assert result_state.total_tokens == 256, (
            "total_tokens was not updated from ResultEnvelope. Got: %s" % result_state.total_tokens
        )

    @pytest.mark.asyncio
    async def test_result_envelope_exit_handle_preserved(self, test_souls_map):
        """exit_handle from ResultEnvelope must be set on the BlockResult."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import Task, WorkflowState

        soul = test_souls_map["test"]
        inner_block = LinearBlock(block_id="block-exit", soul=soul, runner=_make_mock_runner())

        async def _harness_run(envelope: ContextEnvelope) -> ResultEnvelope:
            return ResultEnvelope(
                block_id=envelope.block_id,
                output="branched",
                exit_handle="branch_a",
                cost_usd=0.0,
                total_tokens=0,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            )

        harness_mock = AsyncMock(spec=SubprocessHarness)
        harness_mock.run.side_effect = _harness_run

        wrapper = IsolatedBlockWrapper(
            block_id="block-exit",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState(current_task=Task(id="t-5", instruction="Check exit."))
        result_state = await wrapper.execute(state)

        block_result = result_state.results["block-exit"]
        assert block_result.exit_handle == "branch_a", (
            "exit_handle 'branch_a' was not preserved. "
            "Got: %s. Wrapper may be bypassed." % block_result.exit_handle
        )


# ---------------------------------------------------------------------------
# AC5: Isolation-specific test files are excluded from the mock
# ---------------------------------------------------------------------------


class TestIsolationFilesAreExcluded:
    """Files matching test_iso_* and related prefixes must NOT have
    SubprocessHarness.run patched — they exercise the real path."""

    def test_exclusion_prefixes_include_test_iso(self):
        """The conftest _ISOLATION_TEST_PREFIXES must include 'test_iso_'."""
        # Import conftest directly to inspect its constant.
        import importlib.util
        from pathlib import Path

        conftest_path = Path(__file__).parent / "conftest.py"
        spec = importlib.util.spec_from_file_location("conftest_module", conftest_path)
        conftest_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conftest_mod)

        prefixes = getattr(conftest_mod, "_ISOLATION_TEST_PREFIXES", None)
        assert prefixes is not None, (
            "_ISOLATION_TEST_PREFIXES is not defined in conftest. "
            "The fixture cannot selectively exclude isolation tests."
        )
        assert "test_iso_" in prefixes, (
            "'test_iso_' is not in _ISOLATION_TEST_PREFIXES. "
            "Isolation-specific tests will have harness patched incorrectly."
        )

    def test_exclusion_prefixes_include_harness_test_files(self):
        """_ISOLATION_TEST_PREFIXES must cover the known ISO test file prefixes."""
        import importlib.util
        from pathlib import Path

        conftest_path = Path(__file__).parent / "conftest.py"
        spec = importlib.util.spec_from_file_location("conftest_module", conftest_path)
        conftest_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conftest_mod)

        prefixes = getattr(conftest_mod, "_ISOLATION_TEST_PREFIXES", ())
        # test_run817–test_run820 are IPC extraction tests that rely on real harness
        for expected in ("test_run817", "test_run818", "test_run819", "test_run820"):
            assert expected in prefixes, (
                f"'{expected}' is not in _ISOLATION_TEST_PREFIXES. "
                "Those tests exercise real isolation and must not be patched."
            )

    def test_bypass_fixture_patches_harness_run_not_wrapper_execute(self):
        """The _bypass_subprocess_isolation fixture must patch SubprocessHarness.run,
        NOT IsolatedBlockWrapper.execute.

        This is the core invariant of RUN-391. The current (broken) conftest
        patches wrapper.execute; the fixed conftest must patch harness.run.
        """
        import importlib.util
        from pathlib import Path

        conftest_path = Path(__file__).parent / "conftest.py"
        spec = importlib.util.spec_from_file_location("conftest_module", conftest_path)
        conftest_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conftest_mod)

        # Read the raw source to check what is being patched
        source = conftest_path.read_text()

        assert 'IsolatedBlockWrapper, "execute"' not in source, (
            "conftest still patches IsolatedBlockWrapper.execute. "
            "RUN-391 requires patching SubprocessHarness.run instead."
        )
        assert "SubprocessHarness" in source and '"run"' in source, (
            "conftest does not appear to patch SubprocessHarness.run. "
            "The _bypass_subprocess_isolation fixture must monkeypatch "
            "SubprocessHarness.run to an in-process executor."
        )
