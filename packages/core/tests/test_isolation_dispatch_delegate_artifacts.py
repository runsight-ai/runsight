"""Dispatch delegate artifact routing behavior."""

import asyncio
from unittest.mock import AsyncMock

import pytest

# Shared fixtures
from isolation_dispatch_delegate_helpers import (
    _execute_wrapper,
    _make_result_envelope,
    _make_soul,
    _make_state,
    _make_wrapped_dispatch,
)
from runsight_core.blocks.dispatch import DispatchBranch
from runsight_core.isolation.envelope import DelegateArtifact
from runsight_core.state import BlockResult

pytestmark = pytest.mark.real_subprocess_isolation


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
