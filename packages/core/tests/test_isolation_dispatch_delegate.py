"""DispatchBlock isolation and delegate artifact routing tests.

The suite verifies one subprocess envelope is used for dispatch coordination,
delegate artifacts are routed to per-port state results, missing ports are
skipped, collapsed artifact values are routed, and the subprocess pool
concurrency limit is enforced.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.isolation.envelope import DelegateArtifact, ResultEnvelope
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState

# Shared fixtures


def _make_soul(soul_id: str = "coordinator") -> Soul:
    return Soul(
        id=soul_id if len(soul_id) >= 3 else f"soul-{soul_id}",
        kind="soul",
        name="Coordinator",
        role="Coordinator",
        system_prompt="You coordinate parallel dispatch tasks.",
        model_name="gpt-4o-mini",
    )


def _make_state(task_instruction: str = "Coordinate work") -> WorkflowState:
    return WorkflowState()


def _make_result_envelope(
    block_id: str = "research_dispatch",
    delegate_artifacts: dict | None = None,
    output: str = "coordination complete",
    exit_handle: str = "done",
) -> ResultEnvelope:
    return ResultEnvelope(
        block_id=block_id,
        output=output,
        exit_handle=exit_handle,
        cost_usd=0.005,
        total_tokens=200,
        tool_calls_made=len(delegate_artifacts) if delegate_artifacts else 0,
        delegate_artifacts=delegate_artifacts or {},
        conversation_history=[],
        error=None,
        error_type=None,
    )


def _execute_wrapper(wrapper, state):
    """Run wrapper.execute synchronously."""

    async def _run():
        ctx = build_block_context(wrapper, state)
        output = await wrapper.execute(ctx)
        return apply_block_output(state, wrapper.block_id, output)

    return asyncio.get_event_loop().run_until_complete(_run())


def _make_wrapped_dispatch(branches):
    """Create a DispatchBlock wrapped in IsolatedBlockWrapper."""
    from runsight_core.isolation.wrapper import IsolatedBlockWrapper

    runner = MagicMock()
    inner = DispatchBlock("research_dispatch", branches, runner)
    return IsolatedBlockWrapper("research_dispatch", inner)


# ==============================================================================
# Dispatch sends one subprocess envelope with all branch metadata
# ==============================================================================


class TestDispatchSingleSubprocess:
    """Dispatch executes with one subprocess envelope, not one per branch."""

    def test_dispatch_context_envelope_contains_all_branch_info(self):
        """The single ContextEnvelope sent to the subprocess must carry
        information about all branches so the coordinator can delegate."""
        branches = [
            DispatchBranch(
                exit_id="research",
                label="Research",
                soul=_make_soul("researcher"),
                task_instruction="research topic",
            ),
            DispatchBranch(
                exit_id="write",
                label="Write",
                soul=_make_soul("writer"),
                task_instruction="write draft",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        captured_envelope = None

        async def capture_envelope(env):
            nonlocal captured_envelope
            captured_envelope = env
            return _make_result_envelope(
                delegate_artifacts={
                    "research": DelegateArtifact(prompt="research topic"),
                    "write": DelegateArtifact(prompt="write draft"),
                }
            )

        wrapper._run_in_subprocess = capture_envelope

        _execute_wrapper(wrapper, _make_state())

        assert captured_envelope is not None
        # Branch info should be in block_config so coordinator knows what ports exist
        assert "branches" in captured_envelope.block_config, (
            "ContextEnvelope.block_config must contain 'branches' with port metadata"
        )
        branch_ports = [b["exit_id"] for b in captured_envelope.block_config["branches"]]
        assert "research" in branch_ports
        assert "write" in branch_ports

    def test_dispatch_envelope_branches_carry_task_instructions(self):
        """Each branch in the envelope must carry its task_instruction
        so the coordinator knows what to delegate."""
        branches = [
            DispatchBranch(
                exit_id="alpha",
                label="Alpha",
                soul=_make_soul("analyst"),
                task_instruction="do alpha work",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        captured_envelope = None

        async def capture_envelope(env):
            nonlocal captured_envelope
            captured_envelope = env
            return _make_result_envelope(
                delegate_artifacts={"alpha": DelegateArtifact(prompt="do alpha work")}
            )

        wrapper._run_in_subprocess = capture_envelope

        _execute_wrapper(wrapper, _make_state())

        assert captured_envelope is not None
        branch_data = captured_envelope.block_config["branches"]
        assert branch_data[0]["task_instruction"] == "do alpha work"


# ==============================================================================
# Coordinator delegate tool captures per-port artifacts
# ==============================================================================


class TestCoordinatorDelegateArtifacts:
    """The delegate tool for Dispatch must accept both port and task arguments."""

    def test_delegate_tool_accepts_port_and_task(self):
        """The delegate tool parameters must include 'task' alongside 'port'."""
        from runsight_core.tools.delegate import create_delegate_tool
        from runsight_core.yaml.schema import ExitDef

        exits = [
            ExitDef(id="summarize", label="Summarize"),
            ExitDef(id="review", label="Review"),
        ]
        tool = create_delegate_tool(exits)

        props = tool.parameters["properties"]
        assert "port" in props
        assert "task" in props, "delegate tool must accept a 'task' parameter for artifact routing"

    def test_delegate_tool_task_in_required_fields(self):
        """The 'task' parameter must be required, not optional."""
        from runsight_core.tools.delegate import create_delegate_tool
        from runsight_core.yaml.schema import ExitDef

        exits = [ExitDef(id="summarize", label="Summarize")]
        tool = create_delegate_tool(exits)

        required = tool.parameters.get("required", [])
        assert "task" in required, "delegate tool 'task' must be a required parameter"

    def test_delegate_tool_returns_artifact_with_task(self):
        """When delegate tool is called with port + task, the result should
        capture the task string for downstream routing."""
        from runsight_core.tools.delegate import create_delegate_tool
        from runsight_core.yaml.schema import ExitDef

        exits = [ExitDef(id="summarize", label="Summarize")]
        tool = create_delegate_tool(exits)

        result = asyncio.get_event_loop().run_until_complete(
            tool.execute({"port": "summarize", "task": "summarize the quarterly report"})
        )
        # Result must include the task text so it can be captured as a DelegateArtifact
        assert "summarize the quarterly report" in str(result)


# ==============================================================================
# Wrapper routes delegate_artifacts to per-port state results
# ==============================================================================


class TestWrapperRoutesDelegateArtifacts:
    """IsolatedBlockWrapper must route delegate_artifacts to per-port state results."""

    def test_per_port_results_written_to_state(self):
        """state.results['{block_id}.{port}'] = BlockResult(output=artifact.task, exit_handle=port)
        for each delegate artifact in the ResultEnvelope."""
        branches = [
            DispatchBranch(
                exit_id="analysis",
                label="Analysis",
                soul=_make_soul("analyst"),
                task_instruction="analyze source data",
            ),
            DispatchBranch(
                exit_id="summary",
                label="Summary",
                soul=_make_soul("summarizer"),
                task_instruction="summarize findings",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        result_env = _make_result_envelope(
            delegate_artifacts={
                "analysis": DelegateArtifact(prompt="analyze the data"),
                "summary": DelegateArtifact(prompt="write the summary"),
            }
        )
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)

        new_state = _execute_wrapper(wrapper, _make_state())

        # Per-port results must exist
        assert "research_dispatch.analysis" in new_state.results, (
            "Wrapper must write per-port results from delegate_artifacts"
        )
        assert "research_dispatch.summary" in new_state.results

        # Each per-port result has the delegate task as output
        assert new_state.results["research_dispatch.analysis"].output == "analyze the data"
        assert new_state.results["research_dispatch.analysis"].exit_handle == "analysis"

        assert new_state.results["research_dispatch.summary"].output == "write the summary"
        assert new_state.results["research_dispatch.summary"].exit_handle == "summary"

    def test_per_port_results_are_block_result_instances(self):
        """Each per-port result must be a BlockResult, not a raw dict."""
        branches = [
            DispatchBranch(
                exit_id="research", label="Research", soul=_make_soul(), task_instruction="research"
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        result_env = _make_result_envelope(
            delegate_artifacts={"research": DelegateArtifact(prompt="research brief")}
        )
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)

        new_state = _execute_wrapper(wrapper, _make_state())

        assert "research_dispatch.research" in new_state.results, (
            "Wrapper must create per-port BlockResult from delegate_artifacts"
        )
        assert isinstance(new_state.results["research_dispatch.research"], BlockResult)

    def test_block_level_result_also_present(self):
        """state.results[block_id] should also exist alongside per-port results."""
        branches = [
            DispatchBranch(
                exit_id="research",
                label="Research",
                soul=_make_soul(),
                task_instruction="research topic",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        result_env = _make_result_envelope(
            delegate_artifacts={"research": DelegateArtifact(prompt="research topic")}
        )
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)

        new_state = _execute_wrapper(wrapper, _make_state())

        # Both block-level AND per-port results must exist
        assert "research_dispatch" in new_state.results
        assert "research_dispatch.research" in new_state.results


# ==============================================================================
# Downstream blocks receive delegate task as their instruction
# ==============================================================================


class TestDownstreamReceivesDelegateTask:
    """Downstream blocks connected to ports get the delegate task as instruction."""

    def test_downstream_block_instruction_is_delegate_task(self):
        """The per-port result output IS the delegate task string, which
        downstream blocks read as their instruction."""
        branches = [
            DispatchBranch(
                exit_id="analyze", label="Analyze", soul=_make_soul(), task_instruction="analyze"
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        delegate_task = "Analyze quarterly revenue trends and identify anomalies"
        result_env = _make_result_envelope(
            delegate_artifacts={"analyze": DelegateArtifact(prompt=delegate_task)}
        )
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)

        new_state = _execute_wrapper(wrapper, _make_state())

        port_result = new_state.results["research_dispatch.analyze"]
        assert port_result.output == delegate_task
        assert port_result.exit_handle == "analyze"

    def test_multiple_downstream_blocks_get_different_tasks(self):
        """Each port's downstream block gets its own distinct delegate task."""
        branches = [
            DispatchBranch(
                exit_id="research",
                label="Research",
                soul=_make_soul("researcher"),
                task_instruction="research source material",
            ),
            DispatchBranch(
                exit_id="draft",
                label="Draft",
                soul=_make_soul("drafter"),
                task_instruction="draft introduction",
            ),
            DispatchBranch(
                exit_id="review",
                label="Review",
                soul=_make_soul("reviewer"),
                task_instruction="review factual claims",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        result_env = _make_result_envelope(
            delegate_artifacts={
                "research": DelegateArtifact(prompt="Find papers on quantum computing"),
                "draft": DelegateArtifact(prompt="Write introduction section"),
                "review": DelegateArtifact(prompt="Check for factual errors"),
            }
        )
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)

        new_state = _execute_wrapper(wrapper, _make_state())

        assert (
            new_state.results["research_dispatch.research"].output
            == "Find papers on quantum computing"
        )
        assert new_state.results["research_dispatch.draft"].output == "Write introduction section"
        assert new_state.results["research_dispatch.review"].output == "Check for factual errors"


# ==============================================================================
# Missing ports are skipped without error
# ==============================================================================


class TestMissingPortSkipped:
    """If coordinator does not delegate to a port, downstream block is skipped."""

    def test_missing_port_not_in_state_results(self):
        """A port that the coordinator did not delegate to should not appear in results."""
        branches = [
            DispatchBranch(
                exit_id="outline",
                label="Outline",
                soul=_make_soul("outliner"),
                task_instruction="outline report",
            ),
            DispatchBranch(
                exit_id="draft",
                label="Draft",
                soul=_make_soul("drafter"),
                task_instruction="draft report",
            ),
            DispatchBranch(
                exit_id="review",
                label="Review",
                soul=_make_soul("reviewer"),
                task_instruction="review report",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        # Coordinator only delegates to outline and review, skips draft.
        result_env = _make_result_envelope(
            delegate_artifacts={
                "outline": DelegateArtifact(prompt="outline the report"),
                "review": DelegateArtifact(prompt="review the report"),
            }
        )
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)

        new_state = _execute_wrapper(wrapper, _make_state())

        # Delegated ports have per-port results.
        assert "research_dispatch.outline" in new_state.results
        assert "research_dispatch.review" in new_state.results

        # The missing port does not appear as a per-port result.
        assert "research_dispatch.draft" not in new_state.results

    def test_empty_delegate_artifacts_produces_no_per_port_results(self):
        """When coordinator delegates to no ports, no per-port results are created,
        but the block-level result still exists and includes delegation metadata."""
        branches = [
            DispatchBranch(
                exit_id="only_port",
                label="Only",
                soul=_make_soul(),
                task_instruction="handle primary port",
            ),
            DispatchBranch(
                exit_id="other_port",
                label="Other",
                soul=_make_soul("other"),
                task_instruction="handle secondary port",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        result_env = _make_result_envelope(delegate_artifacts={})
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)
        new_state = _execute_wrapper(wrapper, _make_state())

        assert "research_dispatch" in new_state.results
        assert "research_dispatch.only_port" not in new_state.results
        assert "research_dispatch.other_port" not in new_state.results


# ==============================================================================
# Already-collapsed delegate artifacts route their final per-port value
# ==============================================================================


class TestCollapsedPortArtifactRouting:
    """The wrapper routes the final artifact value present in a ResultEnvelope."""

    def test_collapsed_port_artifact_routed_to_state(self):
        """When the ResultEnvelope contains one value for a port, the wrapper routes it."""
        branches = [
            DispatchBranch(
                exit_id="analysis",
                label="Analysis",
                soul=_make_soul(),
                task_instruction="analyze source data",
            ),
        ]
        wrapper = _make_wrapped_dispatch(branches)

        result_env = _make_result_envelope(
            delegate_artifacts={
                "analysis": DelegateArtifact(prompt="final delegate task"),
            }
        )
        wrapper._run_in_subprocess = AsyncMock(return_value=result_env)

        new_state = _execute_wrapper(wrapper, _make_state())

        # The per-port result must reflect the final delegate task
        assert "research_dispatch.analysis" in new_state.results, (
            "Wrapper must route delegate_artifacts to per-port results"
        )
        assert new_state.results["research_dispatch.analysis"].output == "final delegate task"


# ==============================================================================
# Subprocess pool semaphore controls concurrent execution
# ==============================================================================


class TestSubprocessPoolSemaphore:
    """A semaphore limits concurrent subprocess execution for downstream blocks."""

    def test_pool_importable(self):
        """SubprocessPool is importable from runsight_core.isolation.pool."""
        from runsight_core.isolation.pool import SubprocessPool

        assert SubprocessPool is not None

    def test_default_max_concurrent_subprocesses_is_10(self):
        """The subprocess pool semaphore defaults to max_concurrent_subprocesses=10."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool()
        assert pool.max_concurrent_subprocesses == 10

    def test_custom_max_concurrent_subprocesses(self):
        """The semaphore limit can be configured."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool(max_concurrent_subprocesses=5)
        assert pool.max_concurrent_subprocesses == 5

    def test_semaphore_limits_concurrent_execution(self):
        """When max_concurrent_subprocesses=2 and 4 blocks try to run,
        at most 2 execute concurrently."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool(max_concurrent_subprocesses=2)
        max_concurrent_seen = 0
        current_concurrent = 0

        async def fake_run(block_id: str):
            nonlocal max_concurrent_seen, current_concurrent
            current_concurrent += 1
            if current_concurrent > max_concurrent_seen:
                max_concurrent_seen = current_concurrent
            await asyncio.sleep(0.05)
            current_concurrent -= 1
            return _make_result_envelope(block_id=block_id)

        async def run_test():
            worker_ids = [
                "analysis_worker",
                "summary_worker",
                "review_worker",
                "publish_worker",
            ]
            tasks = [pool.submit(fake_run, worker_id) for worker_id in worker_ids]
            await asyncio.gather(*tasks)

        asyncio.get_event_loop().run_until_complete(run_test())
        assert max_concurrent_seen <= 2, f"Expected at most 2 concurrent, saw {max_concurrent_seen}"

    def test_pool_has_submit_method(self):
        """SubprocessPool must have a submit method for downstream block execution."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool(max_concurrent_subprocesses=10)
        assert hasattr(pool, "submit"), (
            "SubprocessPool must have a submit method for downstream blocks"
        )
