"""Subprocess entry point for process-isolated block execution (ISO-004).

Reads a ContextEnvelope from stdin, executes the block, and writes a
ResultEnvelope to stdout. Heartbeat JSON lines are emitted on stderr.

Import boundary: this module must only import from isolation, primitives,
runner, llm, memory, state, and blocks sub-packages.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone
from typing import Any

from runsight_core.block_io import BlockContext, BlockOutput, build_block_context
from runsight_core.isolation import ipc as isolation_ipc
from runsight_core.isolation import worker_proxies as _proxies
from runsight_core.isolation import worker_support as _support
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    DelegateArtifact,
    HeartbeatMessage,
    ResultEnvelope,
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


async def _close_ipc_client(ipc_client: Any) -> None:
    close = getattr(ipc_client, "close", None)
    if close is None:
        return
    result = close()
    if hasattr(result, "__await__"):
        await result


def _build_delegate_artifacts_from_output(
    *,
    block_id: str,
    block_type: str,
    output: BlockOutput,
) -> dict[str, DelegateArtifact]:
    if block_type != "dispatch":
        return {}

    artifacts: dict[str, DelegateArtifact] = {}
    if output.extra_results:
        prefix = f"{block_id}."
        for result_key, block_result in output.extra_results.items():
            if not result_key.startswith(prefix):
                continue
            port = result_key.removeprefix(prefix)
            from runsight_core.state import BlockResult

            artifact_output = (
                block_result.output if isinstance(block_result, BlockResult) else str(block_result)
            )
            artifacts[port] = DelegateArtifact(prompt=artifact_output)
    return artifacts


async def _execute_envelope(
    *,
    envelope: ContextEnvelope,
    ipc_socket: str,
) -> tuple[ResultEnvelope, int]:
    global _heartbeat_phase

    block_id = envelope.block_id
    ipc_client = isolation_ipc.IPCClient(socket_path=ipc_socket)

    try:
        capability = await ipc_client.connect()
        accepted = (
            capability.get("accepted") if isinstance(capability, dict) else capability.accepted
        )
        capability_error = (
            capability.get("error") if isinstance(capability, dict) else capability.error
        )
        if not accepted:
            return (
                _error_result(
                    block_id,
                    f"IPC auth failed: {capability_error or 'capability negotiation rejected'}",
                    "PermissionError",
                ),
                1,
            )

        resolved_tools = _proxies.create_tool_stubs(envelope.tools, ipc_client=ipc_client)
        soul = _support.reconstruct_soul(envelope.soul, resolved_tools=resolved_tools)
        runner = _proxies.create_runner(model_name=envelope.soul.model_name, ipc_client=ipc_client)

        state = _support.build_scoped_state(envelope)

        model = envelope.soul.model_name
        history_key = f"{envelope.block_id}_{envelope.soul.id}"
        history = state.conversation_histories.get(history_key, [])
        budgeted_history = history
        if history:
            budgeted_history = _support.build_budgeted_history(
                model=model,
                system_prompt=soul.system_prompt,
                instruction=envelope.prompt.instruction,
                conversation_history=history,
            )

        _heartbeat_phase = "executing"
        block = _support._create_block(envelope, soul, runner)

        # Build BlockContext from the reconstructed block and scoped state.
        # For LLM blocks (gate, synthesize, dispatch, linear), build_block_context
        # derives block-type-specific instruction/context (e.g. GateBlock reads
        # eval_key from scoped state; SynthesizeBlock combines inputs).
        # For assertion blocks (AssertionBlockAdapter), build a minimal context directly
        # since the adapter doesn't expose the standard .block_id interface.
        block_type = _support._BLOCK_TYPE_MAP.get(
            envelope.block_type.lower(), envelope.block_type.lower()
        )
        if block_type == "assertion":
            # AssertionBlockAdapter: minimal context — it reads everything from closure.
            raw_context = envelope.prompt.context
            context_text: str | None = None
            if isinstance(raw_context, dict):
                context_text = raw_context.get("text") or None
            elif isinstance(raw_context, str):
                context_text = raw_context or None
            ctx = BlockContext(
                block_id=block_id,
                instruction=envelope.prompt.instruction,
                context=context_text,
                inputs=dict(envelope.inputs),
                conversation_history=budgeted_history,
                soul=soul,
                model_name=model,
                state_snapshot=state,
            )
        else:
            # Use build_block_context to derive block-type-specific instruction and context.
            # Override conversation_history with the budget-trimmed history.
            base_ctx = build_block_context(block, state)
            merged_inputs = {**base_ctx.inputs, **dict(envelope.inputs)}
            ctx = BlockContext(
                block_id=base_ctx.block_id,
                instruction=base_ctx.instruction,
                context=base_ctx.context,
                inputs=merged_inputs,
                conversation_history=budgeted_history,
                soul=base_ctx.soul,
                model_name=base_ctx.model_name,
                artifact_store=base_ctx.artifact_store,
                state_snapshot=base_ctx.state_snapshot,
            )

        block_output: BlockOutput = await block.execute(ctx)

        _heartbeat_phase = "done"
        block_type = _support._BLOCK_TYPE_MAP.get(
            envelope.block_type.lower(), envelope.block_type.lower()
        )
        delegate_artifacts = _build_delegate_artifacts_from_output(
            block_id=block_id,
            block_type=block_type,
            output=block_output,
        )

        # Extract updated conversation history from BlockOutput
        output_history: list[dict[str, Any]] = []
        if block_output.conversation_updates and history_key in block_output.conversation_updates:
            output_history = list(budgeted_history) + block_output.conversation_updates[history_key]
        elif (
            block_output.conversation_replacements
            and history_key in block_output.conversation_replacements
        ):
            output_history = block_output.conversation_replacements[history_key]
        else:
            output_history = list(budgeted_history)

        return (
            ResultEnvelope(
                block_id=block_id,
                output=block_output.output if block_output.output else None,
                exit_handle=block_output.exit_handle or "done",
                cost_usd=block_output.cost_usd,
                total_tokens=block_output.total_tokens,
                tool_calls_made=len(delegate_artifacts),
                delegate_artifacts=delegate_artifacts,
                conversation_history=output_history,
                error=None,
                error_type=None,
            ),
            0,
        )
    finally:
        await _close_ipc_client(ipc_client)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Worker main loop: read envelope, execute block, write result."""
    import asyncio
    import io
    import os

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
            envelope = _support.parse_context_envelope(raw_input)
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

        # Reconstruct primitives and execute the block on one event loop so the
        # persistent IPC reader/writer stay loop-affine for all LLM/tool calls.
        _heartbeat_phase = "setup"
        result_env, exit_code = asyncio.run(
            _execute_envelope(envelope=envelope, ipc_socket=ipc_socket)
        )
        _write_result(result_env, exit_code=exit_code)

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


if __name__ == "__main__":
    main()
