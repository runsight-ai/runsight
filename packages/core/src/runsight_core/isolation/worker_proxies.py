"""Proxied LLM/runner/tool factories for subprocess workers (RUN-819).

These symbols live here — not in worker.py — so that callers who need
only the proxy layer can import a lightweight module without pulling in
the full worker entry-point machinery.
"""

from __future__ import annotations

from typing import Any

from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.isolation.envelope import ToolDefEnvelope
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner
from runsight_core.tools import ToolInstance

# ---------------------------------------------------------------------------
# Proxied LLM client
# ---------------------------------------------------------------------------


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
        except BudgetKilledException:
            raise
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


# ---------------------------------------------------------------------------
# Proxied runner
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


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
            except BudgetKilledException:
                raise
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
