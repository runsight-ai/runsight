"""
Tests for the conftest mock-at-boundary isolation contract.

The conftest must patch UnixLocalHarness.run rather than IsolatedBlockWrapper.execute
so the wrapper's request construction and result mapping are exercised.

Tests verify four properties of the corrected conftest:

1. IsolatedBlockWrapper.execute is NOT patched — it must be the real method.
2. UnixLocalHarness.run IS patched — the conftest patches at the workspace
   harness level.
3. The patched UnixLocalHarness.run receives a WorkspaceRunRequest and returns
   a ResultEnvelope, proving the wrapper built the request before calling the
   harness.
4. Tests marked real_subprocess_isolation are excluded from the mock and
   exercise the real worker path. Filename prefixes are not the
   exclusion contract.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.block_io import BlockContext, BlockOutput, build_block_context
from runsight_core.isolation.envelope import (
    ResultEnvelope,
)
from runsight_core.isolation.workspace import UnixLocalHarness, WorkspaceRunRequest
from runsight_core.isolation.wrapper import IsolatedBlockWrapper


def _make_ctx(wrapper: IsolatedBlockWrapper, state) -> BlockContext:
    """Build a BlockContext from a wrapper and WorkflowState for test call sites."""
    return build_block_context(wrapper, state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _real_wrapper_execute_source() -> str:
    """Return the source of the real IsolatedBlockWrapper.execute implementation."""
    return inspect.getsource(IsolatedBlockWrapper.execute)


def _make_mock_runner() -> MagicMock:
    """Return a minimal mock RunsightTeamRunner sufficient for LinearBlock construction."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o-mini"
    return runner


def _make_result_envelope(block_id: str = "mock_envelope_block") -> ResultEnvelope:
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
# Wrapper execute remains the real implementation
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
            "The conftest must patch UnixLocalHarness.run instead."
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
# UnixLocalHarness.run is patched in normal test context
# ---------------------------------------------------------------------------


class TestWorkspaceHarnessRunIsPatched:
    """The conftest must monkeypatch UnixLocalHarness.run to an in-process executor."""

    def test_harness_run_is_not_the_real_subprocess_spawner(self):
        """UnixLocalHarness.run must be patched to avoid spawning real workers.

        The real run() creates workspace sessions and spawns workers.  In a
        patched state it should be an AsyncMock or a simple coroutine that does
        not launch a worker process.
        """
        run_method = UnixLocalHarness.run
        source = inspect.getsource(run_method)
        assert "worker_launcher" not in source or "AsyncMock" in str(type(run_method)), (
            "UnixLocalHarness.run does not appear to be patched. "
            "The conftest must replace it with an in-process executor so that "
            "litellm mocks are visible and no real workers are spawned."
        )

    def test_harness_run_is_a_coroutine_function(self):
        """The patched UnixLocalHarness.run must still be awaitable."""
        run_method = UnixLocalHarness.run
        # Either the class-level method is still the original (and thus a
        # coroutine function), or it has been patched to an AsyncMock.  Either
        # way it must be awaitable.  If the conftest patches at the harness
        # instance level during wrapper.execute, the class-level method is
        # still the real one here — that is fine for this check.
        assert inspect.iscoroutinefunction(run_method) or isinstance(run_method, AsyncMock), (
            "UnixLocalHarness.run must be a coroutine function (or AsyncMock). "
            "Found: %s" % type(run_method)
        )


# ---------------------------------------------------------------------------
# Wrapper builds WorkspaceRunRequest and passes it to harness.run
# ---------------------------------------------------------------------------


class TestWrapperBuildsRequestBeforeCallingHarness:
    """IsolatedBlockWrapper.execute must construct a WorkspaceRunRequest and pass it
    to harness.run, proving the request construction path is exercised."""

    @pytest.mark.asyncio
    async def test_harness_run_receives_workspace_run_request(self, helper_souls_map):
        """harness.run must be called with a WorkspaceRunRequest instance."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import WorkflowState

        soul = helper_souls_map["helper_analyst"]

        inner_block = LinearBlock(
            block_id="enveloped_analysis_block",
            soul=soul,
            runner=_make_mock_runner(),
        )

        received_requests: list[Any] = []

        async def _capture_run(request: WorkspaceRunRequest) -> ResultEnvelope:
            received_requests.append(request)
            return _make_result_envelope(block_id=request.envelope.block_id)

        harness_mock = AsyncMock(spec=UnixLocalHarness)
        harness_mock.run.side_effect = _capture_run

        wrapper = IsolatedBlockWrapper(
            block_id="enveloped_analysis_block",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState()

        await wrapper.execute(_make_ctx(wrapper, state))

        assert len(received_requests) == 1, (
            "harness.run was not called exactly once. "
            "IsolatedBlockWrapper.execute may have been patched by conftest, "
            "bypassing the request construction."
        )
        assert isinstance(received_requests[0], WorkspaceRunRequest), (
            "harness.run was not called with a WorkspaceRunRequest. "
            "Got: %s" % type(received_requests[0])
        )

    @pytest.mark.asyncio
    async def test_workspace_request_envelope_contains_block_id(self, helper_souls_map):
        """The WorkspaceRunRequest passed to harness.run must have the correct block_id."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import WorkflowState

        soul = helper_souls_map["helper_analyst"]
        inner_block = LinearBlock(
            block_id="context_envelope_block",
            soul=soul,
            runner=_make_mock_runner(),
        )

        received: list[WorkspaceRunRequest] = []

        async def _capture(request: WorkspaceRunRequest) -> ResultEnvelope:
            received.append(request)
            return _make_result_envelope(block_id=request.envelope.block_id)

        harness_mock = AsyncMock(spec=UnixLocalHarness)
        harness_mock.run.side_effect = _capture

        wrapper = IsolatedBlockWrapper(
            block_id="context_envelope_block",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState()
        await wrapper.execute(_make_ctx(wrapper, state))

        assert received[0].envelope.block_id == "context_envelope_block", (
            "WorkspaceRunRequest.envelope.block_id is '%s', expected 'context_envelope_block'. "
            "The wrapper execute path may be patched." % received[0].envelope.block_id
        )


# ---------------------------------------------------------------------------
# The mock returns a valid ResultEnvelope
# ---------------------------------------------------------------------------


class TestMockReturnsValidResultEnvelope:
    """When patched at the harness level, UnixLocalHarness.run must return
    a ResultEnvelope with all required fields populated."""

    @pytest.mark.asyncio
    async def test_result_envelope_is_mapped_to_workflow_state(self, helper_souls_map):
        """IsolatedBlockWrapper.execute must map ResultEnvelope back to BlockOutput."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import WorkflowState

        soul = helper_souls_map["helper_analyst"]
        inner_block = LinearBlock(
            block_id="result_mapping_block",
            soul=soul,
            runner=_make_mock_runner(),
        )

        expected_output = "the answer is 42"

        async def _harness_run(request: WorkspaceRunRequest) -> ResultEnvelope:
            envelope = request.envelope
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

        harness_mock = AsyncMock(spec=UnixLocalHarness)
        harness_mock.run.side_effect = _harness_run

        wrapper = IsolatedBlockWrapper(
            block_id="result_mapping_block",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState()
        block_output = await wrapper.execute(_make_ctx(wrapper, state))

        assert isinstance(block_output, BlockOutput), (
            "Expected BlockOutput from wrapper.execute, got %s. "
            "Wrapper may have been patched and is not mapping ResultEnvelope." % type(block_output)
        )
        assert block_output.output == expected_output, (
            "Expected output '%s', got '%s'. "
            "ResultEnvelope was not mapped correctly." % (expected_output, block_output.output)
        )

    @pytest.mark.asyncio
    async def test_cost_and_tokens_accumulated_from_result_envelope(self, helper_souls_map):
        """cost_usd and total_tokens from ResultEnvelope must be added to WorkflowState."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import WorkflowState

        soul = helper_souls_map["helper_analyst"]
        inner_block = LinearBlock(
            block_id="cost_mapping_block",
            soul=soul,
            runner=_make_mock_runner(),
        )

        async def _harness_run(request: WorkspaceRunRequest) -> ResultEnvelope:
            envelope = request.envelope
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

        harness_mock = AsyncMock(spec=UnixLocalHarness)
        harness_mock.run.side_effect = _harness_run

        wrapper = IsolatedBlockWrapper(
            block_id="cost_mapping_block",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState()
        block_output = await wrapper.execute(_make_ctx(wrapper, state))

        assert block_output.cost_usd == pytest.approx(0.012), (
            "cost_usd was not returned from ResultEnvelope. Got: %s" % block_output.cost_usd
        )
        assert block_output.total_tokens == 256, (
            "total_tokens was not returned from ResultEnvelope. Got: %s" % block_output.total_tokens
        )

    @pytest.mark.asyncio
    async def test_result_envelope_exit_handle_preserved(self, helper_souls_map):
        """exit_handle from ResultEnvelope must be set on the BlockResult."""
        from runsight_core.blocks.linear import LinearBlock
        from runsight_core.state import WorkflowState

        soul = helper_souls_map["helper_analyst"]
        inner_block = LinearBlock(
            block_id="exit_mapping_block",
            soul=soul,
            runner=_make_mock_runner(),
        )

        async def _harness_run(request: WorkspaceRunRequest) -> ResultEnvelope:
            envelope = request.envelope
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

        harness_mock = AsyncMock(spec=UnixLocalHarness)
        harness_mock.run.side_effect = _harness_run

        wrapper = IsolatedBlockWrapper(
            block_id="exit_mapping_block",
            inner_block=inner_block,
            harness=harness_mock,
        )

        state = WorkflowState()
        block_output = await wrapper.execute(_make_ctx(wrapper, state))

        assert block_output.exit_handle == "branch_a", (
            "exit_handle 'branch_a' was not preserved. "
            "Got: %s. Wrapper may be bypassed." % block_output.exit_handle
        )


# ---------------------------------------------------------------------------
# Real subprocess tests are excluded from the mock by marker
# ---------------------------------------------------------------------------


class TestRealSubprocessMarkerContract:
    """Only tests marked real_subprocess_isolation opt out of the subprocess mock."""

    @staticmethod
    def _load_conftest_module():
        import importlib.util
        from pathlib import Path

        conftest_path = Path(__file__).parent / "conftest.py"
        spec = importlib.util.spec_from_file_location("conftest_module", conftest_path)
        conftest_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conftest_mod)
        return conftest_mod

    @staticmethod
    def _make_request(marker):
        class _Node:
            def get_closest_marker(self, name: str):
                if name == "real_subprocess_isolation":
                    return marker
                return None

        class _Request:
            node = _Node()

        return _Request()

    def test_marker_constant_names_real_subprocess_isolation(self):
        """The explicit opt-out contract is the real_subprocess_isolation marker."""
        conftest_mod = self._load_conftest_module()

        marker_name = getattr(conftest_mod, "_REAL_SUBPROCESS_ISOLATION_MARKER", None)

        assert marker_name == "real_subprocess_isolation", (
            "conftest must expose the explicit real_subprocess_isolation marker "
            "as the subprocess bypass opt-out contract."
        )

    def test_marker_opt_out_helper_honors_marker_presence(self):
        """A test with the marker must skip the in-process subprocess bypass."""
        conftest_mod = self._load_conftest_module()
        helper = conftest_mod._uses_real_subprocess_isolation
        marker = object()

        assert helper(self._make_request(marker)) is True

    def test_marker_opt_out_helper_defaults_to_bypass_for_unmarked_tests(self):
        """An unmarked test must keep the global in-process subprocess bypass."""
        conftest_mod = self._load_conftest_module()
        helper = conftest_mod._uses_real_subprocess_isolation

        assert helper(self._make_request(None)) is False

    def test_filename_prefixes_are_not_the_exclusion_contract(self):
        """The bypass fixture must not inspect test filenames or prefix allowlists."""
        conftest_mod = self._load_conftest_module()

        assert not hasattr(conftest_mod, "_ISOLATION_TEST_PREFIXES"), (
            "filename-prefix subprocess bypass exclusions are obsolete; "
            "tests must opt out with @pytest.mark.real_subprocess_isolation."
        )

        source = inspect.getsource(conftest_mod._bypass_subprocess_isolation)
        assert "request.fspath" not in source
        assert "basename.startswith" not in source
        assert "_ISOLATION_TEST_PREFIXES" not in source

    def test_bypass_fixture_patches_harness_run_not_wrapper_execute(self):
        """The _bypass_subprocess_isolation fixture must patch UnixLocalHarness.run,
        NOT IsolatedBlockWrapper.execute.

        This protects the core invariant: conftest must patch the workspace
        harness boundary, never wrapper.execute.
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
            "It must patch UnixLocalHarness.run instead."
        )
        assert "SubprocessHarness.run" not in source, (
            "conftest still refers to SubprocessHarness.run. "
            "The _bypass_subprocess_isolation fixture must patch UnixLocalHarness.run."
        )
        assert "UnixLocalHarness" in source and '"run"' in source, (
            "conftest does not appear to patch UnixLocalHarness.run. "
            "The _bypass_subprocess_isolation fixture must monkeypatch "
            "UnixLocalHarness.run to an in-process executor."
        )
