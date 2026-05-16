"""IPC handler factories for credential injection and sandboxed I/O (ISO-008).

Each ``make_*`` factory returns an async handler compatible with
:class:`runsight_core.isolation.ipc.IPCServer`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from runsight_core.budget_enforcement import _active_budget
from runsight_core.isolation.ipc_models import Handler
from runsight_core.isolation.url_allowlist import normalize_allowlist_hostname
from runsight_core.isolation.workspace import HostToolExecutionRegistry, WorkerToolSchema
from runsight_core.llm.client import LiteLLMClient
from runsight_core.paths import is_path_within_base
from runsight_core.runner import _detect_provider
from runsight_core.security import SSRFError, validate_ssrf
from runsight_core.tools._catalog import (
    _apply_response_size_policy,
    _extract_http_response_value,
    _normalize_html_response,
    _render_http_template,
)

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
    allowed_hosts = {_allowlist_hostname(entry) for entry in url_allowlist}
    allowed_hosts.discard("")

    async def _handle(params: dict[str, Any]) -> dict[str, Any]:
        url: str = params.get("url", "")
        method: str = params.get("method", "GET")
        headers: dict[str, str] = dict(params.get("headers", {}))
        request_json = params.get("json")
        request_content = params.get("content", params.get("body"))
        timeout_seconds = float(params.get("timeout_seconds", 30.0))
        max_response_bytes = int(params.get("max_response_bytes", 1_000_000))

        # -- URL allowlist check ------------------------------------------
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        if hostname not in allowed_hosts:
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
            request_content=request_content,
            client_kwargs=client_kwargs,
            max_response_bytes=max_response_bytes,
        )

    return _handle


def _allowlist_hostname(entry: str) -> str:
    return normalize_allowlist_hostname(entry)


async def _perform_http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    request_json: Any,
    request_content: str | bytes | None,
    client_kwargs: dict[str, Any],
    max_response_bytes: int,
) -> dict[str, Any]:
    try:
        try:
            client_cm = httpx.AsyncClient(**client_kwargs)
        except TypeError:
            client_cm = httpx.AsyncClient()

        async with client_cm as client:
            request_kwargs: dict[str, Any] = {
                "method": method,
                "url": url,
                "headers": headers,
            }
            if request_json is not None:
                request_kwargs["json"] = request_json
            elif request_content is not None:
                request_kwargs["content"] = request_content
            response = await client.request(**request_kwargs)
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
        if not is_path_within_base(base, resolved):
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


def make_tool_call_handler(
    *,
    host_tools: HostToolExecutionRegistry,
    worker_tools: list[WorkerToolSchema],
) -> Handler:
    """Return an IPC handler that dispatches allowed tool calls by binding id."""

    worker_tool_binding_ids = {_effective_tool_binding_id(tool) for tool in worker_tools}
    host_tool_refs = {_effective_tool_binding_id(tool): tool for tool in host_tools.tools}

    async def _handle_workspace_tool_call(params: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(params.get("name", ""))
        binding_id = str(params.get("binding_id") or tool_name)
        tool_args = params.get("arguments", {})

        host_ref = host_tool_refs.get(binding_id)
        if host_ref is None or binding_id not in worker_tool_binding_ids:
            return {"error": {"code": "tool_not_found", "tool": tool_name}}

        try:
            output = await _execute_authorized_host_tool(host_ref, tool_args)
        except _ToolCallMediationError as exc:
            return {"error": str(exc)}
        except Exception:
            logger.exception("ipc.tool_call.failed", extra={"tool_name": tool_name})
            return {"error": f"Tool '{tool_name}' failed"}

        return {"output": output}

    return _handle_workspace_tool_call


def _effective_tool_binding_id(tool: Any) -> str:
    return str(getattr(tool, "binding_id", None) or tool.name)


class _ToolCallMediationError(Exception):
    """Expected policy or mediated tool failure safe to return to the worker."""


async def _execute_authorized_host_tool(host_ref: Any, tool_args: Any) -> Any:
    if not isinstance(tool_args, dict):
        tool_args = {}

    if getattr(host_ref, "mediation", None) == "file_io":
        return await _execute_mediated_file_tool(host_ref, tool_args)

    if getattr(host_ref, "mediation", None) == "http":
        return await _execute_mediated_http_tool(host_ref, tool_args)

    output = host_ref.tool.execute(tool_args)
    if hasattr(output, "__await__"):
        output = await output
    return output


async def _execute_mediated_file_tool(host_ref: Any, tool_args: dict[str, Any]) -> str:
    handler = getattr(host_ref, "mediated_handler", None)
    if handler is None:
        raise _ToolCallMediationError(f"Tool '{host_ref.name}' failed: missing file mediation")

    params = dict(tool_args)
    if "action" in params and "action_type" not in params:
        params["action_type"] = params["action"]
    result = await handler(params)
    if isinstance(result, dict) and result.get("error") is not None:
        raise _ToolCallMediationError(f"Tool '{host_ref.name}' failed: {result['error']}")

    action = str(tool_args.get("action") or tool_args.get("action_type") or "")
    if action == "read":
        return str(result.get("content", "")) if isinstance(result, dict) else str(result)
    if action == "write":
        content = str(tool_args.get("content", ""))
        path = str(tool_args.get("path", ""))
        return f"Written {len(content)} bytes to {path}"
    return str(result)


async def _execute_mediated_http_tool(host_ref: Any, tool_args: dict[str, Any]) -> str:
    handler = getattr(host_ref, "mediated_handler", None)
    if handler is None:
        raise _ToolCallMediationError(f"Tool '{host_ref.name}' failed: missing HTTP mediation")

    request_config = getattr(host_ref, "request_config", None)
    if request_config is None:
        request_config = {
            "method": tool_args["method"],
            "url": tool_args["url"],
            "headers": tool_args.get("headers"),
            "body_template": tool_args.get("body"),
            "response_path": tool_args.get("response_path"),
        }
        rendered_url = str(request_config["url"])
        rendered_body = request_config.get("body_template")
        rendered_headers = _literal_http_headers(request_config.get("headers"))
    else:
        rendered_url = _render_http_template(str(request_config["url"]), tool_args)
        rendered_body = _render_http_template(request_config.get("body_template"), tool_args)
        rendered_headers = _render_http_headers(request_config.get("headers"), tool_args)

    params: dict[str, Any] = {
        "method": str(request_config.get("method", "GET")),
        "url": rendered_url,
        "headers": rendered_headers,
    }
    if rendered_body is not None:
        params["content"] = rendered_body
    timeout_seconds = getattr(host_ref, "timeout_seconds", None)
    if timeout_seconds is not None:
        params["timeout_seconds"] = timeout_seconds

    result = await handler(params)
    if isinstance(result, dict) and result.get("error") is not None:
        raise _ToolCallMediationError(f"Tool '{host_ref.name}' failed: {result['error']}")
    if not isinstance(result, dict):
        return str(result)

    return _normalize_mediated_http_response(
        result,
        response_path=request_config.get("response_path"),
        max_output_bytes=getattr(host_ref, "max_output_bytes", None),
        response_size_policy=getattr(host_ref, "response_size_policy", None),
    )


def _render_http_headers(
    headers: dict[str, str] | None,
    tool_args: dict[str, Any],
) -> dict[str, str]:
    if headers is None:
        return {}
    return {key: _render_http_template(value, tool_args) or "" for key, value in headers.items()}


def _literal_http_headers(headers: Any) -> dict[str, str]:
    if headers is None or not isinstance(headers, dict):
        return {}
    return {str(key): "" if value is None else str(value) for key, value in headers.items()}


def _normalize_mediated_http_response(
    response: dict[str, Any],
    *,
    response_path: str | None,
    max_output_bytes: int | None,
    response_size_policy: Any,
) -> str:
    headers = response.get("headers", {})
    content_type = _header_value(headers, "content-type").lower()
    body = str(response.get("body", ""))

    if "application/json" in content_type:
        result = json.dumps(_extract_http_response_value(json.loads(body), response_path))
    elif "text/html" in content_type:
        result = _normalize_html_response(body)
    elif "text/plain" in content_type:
        result = body
    else:
        result = body

    return _apply_response_size_policy(
        result,
        max_output_bytes=max_output_bytes,
        response_size_policy=response_size_policy,
    )


def _header_value(headers: Any, name: str) -> str:
    if not isinstance(headers, dict):
        return ""
    for key, value in headers.items():
        if str(key).lower() == name:
            return str(value)
    return ""


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
            budget_token = _active_budget.set(None)
            try:
                response = await client.achat(
                    messages=list(params.get("messages", [])),
                    system_prompt=params.get("system_prompt"),
                    temperature=params.get("temperature"),
                    tools=params.get("tools"),
                    tool_choice=params.get("tool_choice"),
                    **extra_kwargs,
                )
            finally:
                _active_budget.reset(budget_token)
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
