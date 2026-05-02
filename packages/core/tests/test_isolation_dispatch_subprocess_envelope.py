"""Dispatch subprocess envelope behavior."""

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

pytestmark = pytest.mark.real_subprocess_isolation


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
