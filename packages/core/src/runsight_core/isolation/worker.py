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
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner
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


class ProxiedLLMClient:
    """Subprocess-side LLM client that proxies completions over IPC."""

    def __init__(self, model_name: str, ipc_client: Any) -> None:
        self.model_name = model_name
        self._ipc_client = ipc_client

    async def achat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        payload.update(kwargs)

        last_chunk: dict[str, Any] | None = None
        try:
            async for chunk in self._ipc_client.request_stream("llm_call", payload):
                if not isinstance(chunk, dict):
                    raise ValueError("invalid llm_call chunk payload")
                if chunk.get("error") is not None:
                    raise RuntimeError(str(chunk["error"]))
                last_chunk = chunk
        except Exception as exc:
            raise RuntimeError(f"llm_call failed: {exc}") from exc

        if last_chunk is None:
            raise RuntimeError("llm_call returned no payload chunks")

        prompt_tokens = int(last_chunk.get("prompt_tokens", 0) or 0)
        completion_tokens = int(last_chunk.get("completion_tokens", 0) or 0)
        total_tokens = int(last_chunk.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        tool_calls_raw = last_chunk.get("tool_calls")
        tool_calls = tool_calls_raw if isinstance(tool_calls_raw, list) else []

        response: dict[str, Any] = {
            "content": str(last_chunk.get("content", "")),
            "cost_usd": float(last_chunk.get("cost_usd", 0.0) or 0.0),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "tool_calls": tool_calls,
            "finish_reason": str(last_chunk.get("finish_reason", "stop") or "stop"),
        }
        raw_message = last_chunk.get("raw_message")
        if isinstance(raw_message, dict):
            response["raw_message"] = raw_message
        elif tool_calls:
            response["raw_message"] = {
                "role": "assistant",
                "content": response["content"],
                "tool_calls": tool_calls,
            }
        return response


class ProxiedRunsightTeamRunner(RunsightTeamRunner):
    """Runsight runner variant that always resolves LLM clients through IPC proxying."""

    def __init__(self, *, model_name: str, ipc_client: Any) -> None:
        self.model_name = model_name
        self.api_keys = None
        self.fallback_routes = {}
        self._ipc_client = ipc_client
        self._clients: dict[str, ProxiedLLMClient] = {}

        default_client = ProxiedLLMClient(model_name=model_name, ipc_client=ipc_client)
        self.llm_client = default_client
        self._clients[model_name] = default_client

    def _get_client(self, soul: Soul) -> ProxiedLLMClient:
        explicit_model_name = self._resolve_runtime_model_name(soul)
        cached_client = self._clients.get(explicit_model_name)
        if cached_client is None:
            cached_client = ProxiedLLMClient(
                model_name=explicit_model_name,
                ipc_client=self._ipc_client,
            )
            self._clients[explicit_model_name] = cached_client
        return cached_client


def create_llm_client(model_name: str, *, ipc_client: Any) -> ProxiedLLMClient:
    """Create a ProxiedLLMClient bound to a shared IPC client."""
    return ProxiedLLMClient(model_name=model_name, ipc_client=ipc_client)


def create_runner(model_name: str, *, ipc_client: Any) -> RunsightTeamRunner:
    """Create a RunsightTeamRunner whose LLM path is fully proxied over IPC."""
    return ProxiedRunsightTeamRunner(model_name=model_name, ipc_client=ipc_client)


def create_tool_stubs(
    tool_envelopes: list[ToolDefEnvelope],
    *,
    ipc_client: Any,
) -> list[ToolInstance]:
    """Convert ToolDefEnvelope list into IPC-backed callable tool stubs using shared IPC."""
    stubs: list[ToolInstance] = []

    for tool_def in tool_envelopes:

        async def _execute(args: dict[str, Any], *, td: ToolDefEnvelope = tool_def) -> str:
            try:
                result = await ipc_client.request(
                    "tool_call",
                    {"name": td.name, "arguments": args},
                )
            except Exception as exc:
                return f"Error: {exc}"
            if isinstance(result, dict) and "error" in result:
                return f"Error: {result['error']}"
            if isinstance(result, dict):
                return str(result.get("output", ""))
            return str(result)

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
        ipc_client = isolation_ipc.IPCClient(socket_path=ipc_socket)
        capability = asyncio.run(ipc_client.connect())
        accepted = (
            capability.get("accepted") if isinstance(capability, dict) else capability.accepted
        )
        capability_error = (
            capability.get("error") if isinstance(capability, dict) else capability.error
        )
        if not accepted:
            _write_result(
                _error_result(
                    block_id,
                    f"IPC auth failed: {capability_error or 'capability negotiation rejected'}",
                    "PermissionError",
                ),
                exit_code=1,
            )

        resolved_tools = create_tool_stubs(envelope.tools, ipc_client=ipc_client)
        soul = reconstruct_soul(envelope.soul, resolved_tools=resolved_tools)
        runner = create_runner(model_name=envelope.soul.model_name, ipc_client=ipc_client)

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


_BLOCK_TYPE_MAP = {
    "linear": "linear",
    "linearblock": "linear",
    "gate": "gate",
    "gateblock": "gate",
    "synthesize": "synthesize",
    "synthesizeblock": "synthesize",
    "dispatch": "dispatch",
    "dispatchblock": "dispatch",
}


def _resolve_block_soul(block_soul: Any, fallback_soul: Soul) -> Soul:
    if not isinstance(block_soul, dict):
        return fallback_soul
    payload = fallback_soul.model_dump(exclude={"resolved_tools"})
    payload.update(block_soul)
    payload.setdefault("required_tool_calls", fallback_soul.required_tool_calls or [])
    payload.setdefault("max_tool_iterations", fallback_soul.max_tool_iterations)
    payload["resolved_tools"] = fallback_soul.resolved_tools
    return Soul.model_validate(payload)


def _create_block(envelope: ContextEnvelope, soul: Soul, runner: RunsightTeamRunner):
    """Instantiate the correct block based on envelope.block_type."""
    block_type = _BLOCK_TYPE_MAP.get(envelope.block_type.lower(), envelope.block_type.lower())

    if block_type == "linear":
        from runsight_core.blocks.linear import LinearBlock

        block = LinearBlock(
            block_id=envelope.block_id,
            soul=soul,
            runner=runner,
        )
        block.stateful = True
        return block

    if block_type == "gate":
        from runsight_core.blocks.gate import GateBlock

        gate_soul = _resolve_block_soul(envelope.block_config.get("gate_soul"), soul)
        block = GateBlock(
            block_id=envelope.block_id,
            gate_soul=gate_soul,
            eval_key=str(envelope.block_config.get("eval_key", "")),
            extract_field=envelope.block_config.get("extract_field"),
            runner=runner,
        )
        block.stateful = True
        return block

    if block_type == "synthesize":
        from runsight_core.blocks.synthesize import SynthesizeBlock

        synthesizer_soul = _resolve_block_soul(envelope.block_config.get("synthesizer_soul"), soul)
        input_block_ids = list(envelope.block_config.get("input_block_ids", []))
        block = SynthesizeBlock(
            block_id=envelope.block_id,
            input_block_ids=input_block_ids,
            synthesizer_soul=synthesizer_soul,
            runner=runner,
        )
        block.stateful = True
        return block

    if block_type == "dispatch":
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        raw_branches = list(envelope.block_config.get("branches", []))
        branches = [
            DispatchBranch(
                exit_id=str(branch.get("exit_id", "")),
                label=str(branch.get("label", "")),
                soul=_resolve_block_soul(branch.get("soul"), soul),
                task_instruction=str(branch.get("task_instruction", "")),
            )
            for branch in raw_branches
            if isinstance(branch, dict)
        ]
        block = DispatchBlock(block_id=envelope.block_id, branches=branches, runner=runner)
        block.stateful = True
        return block

    raise ValueError(f"Unsupported block_type: {block_type!r}")


if __name__ == "__main__":
    main()
