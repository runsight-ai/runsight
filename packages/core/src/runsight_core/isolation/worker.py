"""Subprocess entry point for process-isolated block execution (ISO-004).

Reads a ContextEnvelope from stdin, executes the block, and writes a
ResultEnvelope to stdout. Heartbeat JSON lines are emitted on stderr.

Import boundary: this module must only import from isolation, primitives,
runner, llm, memory, state, and blocks sub-packages.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any

from runsight_core.isolation import ipc as isolation_ipc
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    HeartbeatMessage,
    ResultEnvelope,
    SoulEnvelope,
    ToolDefEnvelope,
)
from runsight_core.llm.client import LiteLLMClient
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner, _detect_provider
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.tools import ToolInstance

# ---------------------------------------------------------------------------
# Public helper functions (importable by tests)
# ---------------------------------------------------------------------------


def parse_context_envelope(json_str: str) -> ContextEnvelope:
    """Parse a JSON string into a ContextEnvelope."""
    return ContextEnvelope.model_validate_json(json_str)


def reconstruct_soul(
    soul_envelope: SoulEnvelope,
    *,
    resolved_tools: list[ToolInstance] | None = None,
) -> Soul:
    """Convert a SoulEnvelope into a runsight_core.primitives.Soul."""
    return Soul(
        id=soul_envelope.id,
        role=soul_envelope.role,
        system_prompt=soul_envelope.system_prompt,
        model_name=soul_envelope.model_name,
        provider=soul_envelope.provider or None,
        temperature=soul_envelope.temperature,
        max_tokens=soul_envelope.max_tokens,
        required_tool_calls=list(soul_envelope.required_tool_calls),
        max_tool_iterations=soul_envelope.max_tool_iterations,
        resolved_tools=resolved_tools,
    )


def create_llm_client(model_name: str, api_key: str) -> LiteLLMClient:
    """Create a LiteLLMClient with the given API key."""
    return LiteLLMClient(model_name=model_name, api_key=api_key)


def create_runner(model_name: str, api_key: str) -> RunsightTeamRunner:
    """Create a RunsightTeamRunner from a single worker key using the canonical provider-key shape."""
    provider = _detect_provider(model_name)
    return RunsightTeamRunner(model_name=model_name, api_keys={provider: api_key})


def create_tool_stubs(
    tool_envelopes: list[ToolDefEnvelope],
    socket_path: str,
    grant_token: str,
) -> list[ToolInstance]:
    """Convert ToolDefEnvelope list into IPC-backed callable tool stubs."""
    stubs: list[ToolInstance] = []
    client: isolation_ipc.IPCClient | None = None
    authenticated = False

    async def _get_authenticated_client() -> isolation_ipc.IPCClient:
        nonlocal client, authenticated
        if client is None:
            client = isolation_ipc.IPCClient(socket_path=socket_path)
            await client.connect()
        if not authenticated:
            auth_result = await client.request(
                "capability_negotiation",
                {"grant_token": grant_token},
            )
            if isinstance(auth_result, dict) and "error" in auth_result:
                raise PermissionError(f"IPC auth failed: {auth_result['error']}")
            authenticated = True
        return client

    for tool_def in tool_envelopes:

        async def _execute(args: dict[str, Any], *, td: ToolDefEnvelope = tool_def) -> str:
            try:
                active_client = await _get_authenticated_client()
                result = await active_client.request(
                    "tool_call",
                    {"name": td.name, "arguments": args},
                )
            except Exception as exc:
                return f"Error: {exc}"
            if "error" in result:
                return f"Error: {result['error']}"
            return str(result.get("output", ""))

        stubs.append(
            ToolInstance(
                name=tool_def.name,
                description=tool_def.description,
                parameters=tool_def.parameters,
                execute=_execute,
            )
        )
    return stubs


def build_budgeted_history(
    model: str,
    system_prompt: str,
    instruction: str,
    conversation_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply fit_to_budget locally to trim conversation history.

    Uses a conservative budget_ratio (0.5) to leave room for the block's
    own output, tool calls, and instruction within the worker subprocess.
    """
    budgeted = fit_to_budget(
        ContextBudgetRequest(
            model=model,
            system_prompt=system_prompt,
            instruction=instruction,
            context="",
            conversation_history=conversation_history,
            budget_ratio=0.5,
        ),
        counter=litellm_token_counter,
    )
    return budgeted.messages


def build_scoped_state(envelope: ContextEnvelope) -> WorkflowState:
    """Construct a scoped WorkflowState from envelope data."""
    results: dict[str, BlockResult] = {}
    for block_id, result_data in envelope.scoped_results.items():
        if isinstance(result_data, dict):
            results[block_id] = BlockResult(**result_data)
        else:
            results[block_id] = BlockResult(output=str(result_data))

    task = Task(
        id=envelope.task.id,
        instruction=envelope.task.instruction,
        context=json.dumps(envelope.task.context) if envelope.task.context else None,
    )

    history_key = f"{envelope.block_id}_{envelope.soul.id}"

    return WorkflowState(
        shared_memory=dict(envelope.scoped_shared_memory),
        current_task=task,
        results=results,
        conversation_histories={history_key: list(envelope.conversation_history)},
    )


# ---------------------------------------------------------------------------
# Heartbeat thread
# ---------------------------------------------------------------------------

_heartbeat_counter = 0
_heartbeat_phase = "init"
_heartbeat_stop = threading.Event()


def _emit_heartbeat(phase: str, detail: str = "") -> None:
    """Write a single heartbeat JSON line to stderr."""
    global _heartbeat_counter
    _heartbeat_counter += 1
    hb = HeartbeatMessage(
        heartbeat=_heartbeat_counter,
        phase=phase,
        detail=detail,
        timestamp=datetime.now(timezone.utc),
    )
    sys.stderr.write(hb.model_dump_json() + "\n")
    sys.stderr.flush()


def _heartbeat_loop(interval: float = 5.0) -> None:
    """Background thread that emits heartbeats at a fixed interval."""
    while not _heartbeat_stop.is_set():
        _emit_heartbeat(_heartbeat_phase)
        _heartbeat_stop.wait(interval)


# ---------------------------------------------------------------------------
# Error result helper
# ---------------------------------------------------------------------------


def _error_result(
    block_id: str,
    error: str,
    error_type: str,
    conversation_history: list[dict[str, Any]] | None = None,
) -> ResultEnvelope:
    """Build an error ResultEnvelope."""
    return ResultEnvelope(
        block_id=block_id,
        output=None,
        exit_handle="error",
        cost_usd=0.0,
        total_tokens=0,
        tool_calls_made=0,
        delegate_artifacts={},
        conversation_history=conversation_history or [],
        error=error,
        error_type=error_type,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Worker main loop: read envelope, execute block, write result."""
    import asyncio
    import io

    global _heartbeat_phase

    block_id = "unknown"

    # Emit initial heartbeat immediately
    _emit_heartbeat("init", "worker starting")

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    heartbeat_thread.start()

    # Capture real stdout/stdin so we can write clean JSON at the end.
    # Libraries like litellm may print to stdout; we redirect to devnull.
    _real_stdout = sys.stdout
    _real_stdin = sys.stdin
    sys.stdout = io.StringIO()

    def _write_result(result_env: ResultEnvelope, exit_code: int) -> None:
        """Write ResultEnvelope to real stdout and exit."""
        sys.stdout = _real_stdout
        _real_stdout.write(result_env.model_dump_json() + "\n")
        _real_stdout.flush()
        sys.exit(exit_code)

    try:
        # Check required env vars
        grant_token = os.environ.get("RUNSIGHT_GRANT_TOKEN")
        ipc_socket = os.environ.get("RUNSIGHT_IPC_SOCKET")

        if not grant_token:
            _write_result(
                _error_result(
                    block_id,
                    "Missing required environment variable: RUNSIGHT_GRANT_TOKEN",
                    "EnvironmentError",
                ),
                exit_code=1,
            )

        if not ipc_socket:
            _write_result(
                _error_result(
                    block_id,
                    "Missing required environment variable: RUNSIGHT_IPC_SOCKET",
                    "EnvironmentError",
                ),
                exit_code=1,
            )

        # Read and parse envelope from stdin
        _heartbeat_phase = "parsing"
        raw_input = _real_stdin.read()
        try:
            envelope = parse_context_envelope(raw_input)
        except Exception as exc:
            _write_result(
                _error_result(
                    block_id,
                    f"Failed to parse ContextEnvelope: {exc}",
                    type(exc).__name__,
                ),
                exit_code=1,
            )

        block_id = envelope.block_id

        # Reconstruct primitives
        _heartbeat_phase = "setup"
        resolved_tools = create_tool_stubs(
            envelope.tools,
            socket_path=ipc_socket,
            grant_token=grant_token,
        )
        soul = reconstruct_soul(envelope.soul, resolved_tools=resolved_tools)
        runner = create_runner(
            model_name=envelope.soul.model_name,
            api_key="",
        )

        # Build scoped state
        state = build_scoped_state(envelope)

        # Apply budget to conversation history
        model = envelope.soul.model_name
        history_key = f"{envelope.block_id}_{envelope.soul.id}"
        history = state.conversation_histories.get(history_key, [])
        if history:
            budgeted_history = build_budgeted_history(
                model=model,
                system_prompt=soul.system_prompt,
                instruction=envelope.task.instruction,
                conversation_history=history,
            )
            state = state.model_copy(
                update={"conversation_histories": {history_key: budgeted_history}}
            )

        # Construct and execute the block
        _heartbeat_phase = "executing"
        block = _create_block(envelope, soul, runner)
        final_state = asyncio.run(block.execute(state))

        # Build success result
        _heartbeat_phase = "done"
        block_result = final_state.results.get(block_id)
        output_history = final_state.conversation_histories.get(history_key, [])

        _write_result(
            ResultEnvelope(
                block_id=block_id,
                output=block_result.output if block_result else None,
                exit_handle=block_result.exit_handle or "done" if block_result else "done",
                cost_usd=final_state.total_cost_usd,
                total_tokens=final_state.total_tokens,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=output_history,
                error=None,
                error_type=None,
            ),
            exit_code=0,
        )

    except SystemExit:
        raise
    except Exception as exc:
        _heartbeat_phase = "error"
        # Preserve conversation history from the envelope if available
        error_history: list[dict[str, Any]] = []
        try:
            error_history = list(envelope.conversation_history)
        except NameError:
            pass
        _write_result(
            _error_result(block_id, str(exc), type(exc).__name__, error_history),
            exit_code=1,
        )
    finally:
        _heartbeat_stop.set()


def _create_block(envelope: ContextEnvelope, soul: Soul, runner: RunsightTeamRunner):
    """Instantiate the correct block based on envelope.block_type."""
    block_type = envelope.block_type

    if block_type == "linear":
        from runsight_core.blocks.linear import LinearBlock

        block = LinearBlock(
            block_id=envelope.block_id,
            soul=soul,
            runner=runner,
        )
        block.stateful = True
        return block

    raise ValueError(f"Unsupported block_type: {block_type!r}")


if __name__ == "__main__":
    main()
