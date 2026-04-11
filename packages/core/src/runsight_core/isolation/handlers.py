"""IPC handler factories for credential injection and sandboxed I/O (ISO-008).

Each ``make_*`` factory returns an async handler compatible with
:class:`runsight_core.isolation.ipc.IPCServer`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from runsight_core.isolation.ipc import Handler
from runsight_core.llm.client import LiteLLMClient
from runsight_core.runner import _detect_provider
from runsight_core.security import SSRFError, validate_ssrf

logger = logging.getLogger(__name__)
_DEFAULT_MAX_FILE_WRITE_BYTES = 10 * 1024 * 1024
_DEFAULT_MAX_TOTAL_FILE_WRITE_BYTES = 50 * 1024 * 1024
_ALLOWED_LLM_EXTRA_KWARGS = frozenset(
    {
        "frequency_penalty",
        "max_tokens",
        "n",
        "presence_penalty",
        "response_format",
        "seed",
        "stop",
        "top_p",
    }
)

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def make_http_handler(
    *,
    credentials: dict[str, dict[str, str]],
    url_allowlist: list[str],
) -> Handler:
    """Return an IPC handler that performs real HTTP requests with SSRF/allowlist checks."""

    async def _handle(params: dict[str, Any]) -> dict[str, Any]:
        url: str = params.get("url", "")
        method: str = params.get("method", "GET")
        headers: dict[str, str] = dict(params.get("headers", {}))
        request_json = params.get("json")
        timeout_seconds = float(params.get("timeout_seconds", 30.0))
        max_response_bytes = int(params.get("max_response_bytes", 1_000_000))

        # -- URL allowlist check ------------------------------------------
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        if hostname not in url_allowlist:
            return {"error": f"Host not on allowed list: {hostname}"}

        # -- SSRF validation ----------------------------------------------
        try:
            await validate_ssrf(url)
        except SSRFError as exc:
            logger.info("ipc.http.ssrf_blocked", extra={"hostname": hostname, "reason": str(exc)})
            return {"error": "request blocked by SSRF policy"}

        # -- Inject host-scoped credentials (engine-side only) ------------
        host_credentials = credentials.get(hostname, {})
        headers.update(host_credentials)

        # -- Execute request -----------------------------------------------
        client_kwargs = {
            "timeout": timeout_seconds,
            # Redirect policy is engine-owned; subprocess payloads cannot relax SSRF gates.
            "follow_redirects": False,
        }
        return await _perform_http_request(
            method=method,
            url=url,
            headers=headers,
            request_json=request_json,
            client_kwargs=client_kwargs,
            max_response_bytes=max_response_bytes,
        )

    return _handle


async def _perform_http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    request_json: Any,
    client_kwargs: dict[str, Any],
    max_response_bytes: int,
) -> dict[str, Any]:
    try:
        try:
            client_cm = httpx.AsyncClient(**client_kwargs)
        except TypeError:
            client_cm = httpx.AsyncClient()

        async with client_cm as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=request_json,
            )
    except Exception:
        logger.exception("ipc.http.request_failed")
        return {"error": "HTTP request failed"}

    response_body = response.text
    if len(response_body.encode("utf-8")) > max_response_bytes:
        return {"error": f"response body exceeds max_response_bytes={max_response_bytes}"}

    return {
        "status_code": int(response.status_code),
        "body": response_body,
        "headers": dict(response.headers),
    }


# ---------------------------------------------------------------------------
# File I/O handler
# ---------------------------------------------------------------------------


def make_file_io_handler(
    *,
    base_dir: str,
    max_write_bytes: int = _DEFAULT_MAX_FILE_WRITE_BYTES,
    max_total_write_bytes: int = _DEFAULT_MAX_TOTAL_FILE_WRITE_BYTES,
) -> Handler:
    """Return an IPC handler that scopes all file operations to *base_dir*.

    Blocks absolute paths and path-traversal attempts (``..``).
    """
    base = Path(base_dir).resolve()
    total_bytes_written = 0

    async def _handle(params: dict[str, Any]) -> dict[str, Any]:
        nonlocal total_bytes_written
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
            encoded = str(content).encode("utf-8")
            if len(encoded) > max_write_bytes:
                return {"error": f"file write exceeds max_write_bytes={max_write_bytes}"}
            if total_bytes_written + len(encoded) > max_total_write_bytes:
                return {
                    "error": f"file writes exceed max_total_write_bytes={max_total_write_bytes}"
                }
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(str(content))
            total_bytes_written += len(encoded)
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
        except Exception:
            logger.exception("ipc.tool_call.failed", extra={"tool_name": tool_name})
            return {"error": f"Tool '{tool_name}' failed"}

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
        except Exception:
            logger.exception("ipc.llm.provider_detection_failed", extra={"model": model_name})
            yield {"error": "Unable to determine provider for requested model"}
            return

        api_key = api_keys.get(provider)
        if not api_key:
            yield {
                "error": f"No API key configured for provider '{provider}' "
                f"(required by model '{model_name}')",
            }
            return

        extra_kwargs = {
            key: value for key, value in params.items() if key in _ALLOWED_LLM_EXTRA_KWARGS
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
        except Exception:
            logger.exception("ipc.llm.call_failed", extra={"model": model_name})
            yield {"error": "llm_call failed"}
            return

        chunk = dict(response)
        chunk.setdefault("content", "")
        chunk.setdefault("cost_usd", 0.0)
        chunk.setdefault("total_tokens", 0)
        yield chunk

    return _handle
