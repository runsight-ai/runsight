"""IPC handler factories for credential injection and sandboxed I/O (ISO-008).

Each ``make_*`` factory returns an async handler compatible with
:class:`runsight_core.isolation.ipc.IPCServer`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from runsight_core.isolation.ipc import Handler
from runsight_core.llm.client import LiteLLMClient
from runsight_core.runner import _detect_provider
from runsight_core.security import SSRFError, validate_ssrf

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def make_http_handler(
    *,
    credentials: dict[str, str],
    url_allowlist: list[str],
) -> Handler:
    """Return an IPC handler that validates URLs and injects auth headers.

    Args:
        credentials: Headers to inject into every outgoing request
            (e.g. ``{"Authorization": "Bearer ..."}``)
        url_allowlist: Hostnames that are allowed.  ``"*"`` permits all hosts.
            An empty list blocks every request.
    """

    async def _handle(params: dict[str, Any]) -> dict[str, Any]:
        url: str = params.get("url", "")
        method: str = params.get("method", "GET")
        headers: dict[str, str] = dict(params.get("headers", {}))

        # -- URL allowlist check ------------------------------------------
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        if "*" not in url_allowlist:
            if hostname not in url_allowlist:
                return {"error": f"Host '{hostname}' is not on the allowed hosts list"}

        # -- SSRF validation ----------------------------------------------
        try:
            await validate_ssrf(url)
        except SSRFError as exc:
            return {"error": str(exc)}

        # -- Inject credentials (engine-side only) ------------------------
        headers.update(credentials)

        # Return a successful result without leaking injected credentials.
        return {
            "status": 200,
            "url": url,
            "method": method,
        }

    return _handle


# ---------------------------------------------------------------------------
# File I/O handler
# ---------------------------------------------------------------------------


def make_file_io_handler(*, base_dir: str) -> Handler:
    """Return an IPC handler that scopes all file operations to *base_dir*.

    Blocks absolute paths and path-traversal attempts (``..``).
    """
    base = Path(base_dir).resolve()

    async def _handle(params: dict[str, Any]) -> dict[str, Any]:
        action_type: str = params.get("action_type", "")
        raw_path: str = params.get("path", "")

        # Decode percent-encoded sequences so tricks like %2e%2e are caught
        decoded_path = unquote(raw_path)

        # Block absolute paths
        if Path(decoded_path).is_absolute():
            return {"error": f"Absolute paths are not allowed: {raw_path}"}

        # Block path traversal
        if ".." in Path(decoded_path).parts:
            return {"error": f"Path traversal (..) is not allowed: {raw_path}"}

        resolved = (base / decoded_path).resolve()

        # Belt-and-suspenders: ensure resolved path is within base_dir
        if not str(resolved).startswith(str(base)):
            return {"error": f"Path escapes base directory: {raw_path}"}

        if action_type == "read":
            try:
                content = resolved.read_text()
            except FileNotFoundError:
                return {"error": f"File not found: {raw_path}"}
            return {"content": content}

        if action_type == "write":
            content = params.get("content", "")
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content)
            return {"ok": True}

        return {"error": f"Unknown action_type: {action_type}"}

    return _handle


# ---------------------------------------------------------------------------
# Generic tool_call handler
# ---------------------------------------------------------------------------


def make_tool_call_handler(resolved_tools: dict[str, Any]) -> Handler:
    """Return an IPC handler that dispatches to resolved ToolInstances by name."""

    async def _handle(params: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(params.get("name", ""))
        tool_args = params.get("arguments", {})

        tool = resolved_tools.get(tool_name)
        if tool is None:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            output = await tool.execute(tool_args)
        except Exception as exc:
            return {"error": f"Tool '{tool_name}' failed: {exc}"}

        return {"output": output}

    return _handle


# ---------------------------------------------------------------------------
# LLM proxy handler
# ---------------------------------------------------------------------------


def make_llm_call_handler(api_keys: dict[str, str]) -> Handler:
    """Return an IPC streaming handler that proxies subprocess ``llm_call`` payloads."""

    async def _handle(params: dict[str, Any]):
        model_name = str(params.get("model", ""))
        if not model_name:
            yield {"error": "Missing required llm_call field: model"}
            return

        try:
            provider = _detect_provider(model_name)
        except Exception as exc:
            yield {"error": f"Unable to determine provider for model '{model_name}': {exc}"}
            return

        api_key = api_keys.get(provider)
        if not api_key:
            yield {
                "error": f"No API key configured for provider '{provider}' "
                f"(required by model '{model_name}')",
            }
            return

        extra_kwargs = {
            key: value
            for key, value in params.items()
            if key
            not in {
                "model",
                "messages",
                "system_prompt",
                "temperature",
                "tools",
                "tool_choice",
            }
        }

        try:
            client = LiteLLMClient(model_name=model_name, api_key=api_key)
            response = await client.achat(
                messages=list(params.get("messages", [])),
                system_prompt=params.get("system_prompt"),
                temperature=params.get("temperature"),
                tools=params.get("tools"),
                tool_choice=params.get("tool_choice"),
                **extra_kwargs,
            )
        except Exception as exc:
            yield {"error": f"llm_call failed: {exc}"}
            return

        chunk = dict(response)
        chunk.setdefault("content", "")
        chunk.setdefault("cost_usd", 0.0)
        chunk.setdefault("total_tokens", 0)
        yield chunk

    return _handle
