"""Built-in tool catalog: ToolInstance, registration, and resolution."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict

import httpx

from runsight_core.blocks.code import (
    _HARNESS_PREFIX,
    _HARNESS_SUFFIX,
    DEFAULT_ALLOWED_IMPORTS,
    _validate_code_ast,
)
from runsight_core.security import validate_ssrf
from runsight_core.yaml.discovery import (
    RESERVED_BUILTIN_TOOL_IDS,
    ToolMeta,
    discover_custom_tools,
)

# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------

BUILTIN_TOOL_CATALOG: Dict[str, Callable] = {}
_ARG_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_ENV_TEMPLATE_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


# ---------------------------------------------------------------------------
# ToolInstance
# ---------------------------------------------------------------------------


@dataclass
class ToolInstance:
    """A fully-resolved tool ready for execution."""

    name: str
    description: str
    parameters: dict
    execute: Callable

    def to_openai_schema(self) -> dict:
        """Return the OpenAI function-calling tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------


def register_builtin(source: str, factory: Callable) -> None:
    """Register a factory function under *source* in the builtin catalog."""
    BUILTIN_TOOL_CATALOG[source] = factory


def get_builtin(source: str) -> Callable | None:
    """Retrieve a factory by *source*, or ``None`` if not registered."""
    return BUILTIN_TOOL_CATALOG.get(source)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _tool_instance_name(tool_id: str) -> str:
    """Derive the LLM-facing function name from a canonical tool ID."""
    return tool_id.removesuffix("_tool")


def _resolve_custom_tool_id(
    tool_id: str,
    *,
    tool_meta: ToolMeta | None = None,
    **kwargs: object,
) -> ToolInstance:
    """Resolve a custom tool from its canonical workflow ID."""
    base_dir = kwargs.get("base_dir", ".")
    timeout_seconds = kwargs.get("timeout_seconds", 30)
    if not isinstance(timeout_seconds, int):
        raise TypeError("timeout_seconds must be an int")

    tool_meta = tool_meta or discover_custom_tools(base_dir).get(tool_id)
    if tool_meta is None:
        raise ValueError(f"Unknown custom tool source: {tool_id!r}")
    if tool_meta.executor != "python":
        raise ValueError(
            f"Custom tool {tool_id!r} uses unsupported executor for python resolution: "
            f"{tool_meta.executor!r}"
        )
    if tool_meta.code is None:
        raise ValueError(f"Custom tool {tool_id!r} has no executable code")

    _validate_code_ast(tool_meta.code, list(DEFAULT_ALLOWED_IMPORTS))
    harness = _HARNESS_PREFIX + tool_meta.code + _HARNESS_SUFFIX

    async def _execute(args: dict) -> str:
        stdin_data = json.dumps(args).encode()
        minimal_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")}
        for key in ("HOME", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
            if key in os.environ:
                minimal_env[key] = os.environ[key]

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            harness,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=minimal_env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=stdin_data), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            return f"Error: custom tool '{tool_id}' timed out after {timeout_seconds}s"

        if proc.returncode != 0:
            error_msg = stderr_bytes.decode(errors="replace").strip()
            return f"Error: {error_msg}"

        return stdout_bytes.decode(errors="replace").strip()

    return ToolInstance(
        name=_tool_instance_name(tool_id),
        description=tool_meta.description,
        parameters=tool_meta.parameters,
        execute=_execute,
    )


def _render_http_template(template: str | None, args: dict) -> str | None:
    """Render ``{{ param }}`` placeholders and ``${ENV}`` references."""
    if template is None:
        return None

    rendered = _ARG_TEMPLATE_RE.sub(lambda match: str(args.get(match.group(1), "")), template)

    def _replace_env(match: re.Match[str]) -> str:
        env_name = match.group(1)
        env_value = os.environ.get(env_name)
        if env_value is None:
            raise ValueError(f"Missing environment secret: {env_name}")
        return env_value

    return _ENV_TEMPLATE_RE.sub(_replace_env, rendered)


def _extract_http_response_value(payload: object, response_path: str | None) -> object:
    """Traverse a dotted JSON path if one was configured."""
    if response_path is None:
        return payload

    value = payload
    for segment in response_path.split("."):
        if not isinstance(value, dict) or segment not in value:
            raise ValueError(f"Response path {response_path!r} was not found in the HTTP response")
        value = value[segment]
    return value


def _apply_response_size_policy(
    result: str,
    *,
    max_output_bytes: int | None,
    response_size_policy: Callable[..., str] | None,
) -> str:
    """Route oversized responses through the configured size policy hook."""
    if max_output_bytes is None or len(result.encode("utf-8")) <= max_output_bytes:
        return result
    if response_size_policy is None:
        return result
    return response_size_policy(result, max_output_bytes=max_output_bytes)


async def _execute_outbound_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None,
    body_template: str | None,
    response_path: str | None,
    args: dict[str, Any],
    timeout_seconds: int | None = None,
    max_output_bytes: int | None = None,
    response_size_policy: Callable[..., str] | None = None,
) -> str:
    """Execute a shared outbound HTTP request for builtin and custom tools."""
    rendered_url = _render_http_template(url, args)
    rendered_body = _render_http_template(body_template, args)
    rendered_headers = (
        {key: _render_http_template(value, args) for key, value in headers.items()}
        if headers is not None
        else None
    )
    await validate_ssrf(rendered_url)

    async with httpx.AsyncClient() as client:
        request_coro = client.request(
            method.upper(),
            rendered_url,
            headers=rendered_headers,
            content=rendered_body,
        )
        response = (
            await asyncio.wait_for(request_coro, timeout=timeout_seconds)
            if timeout_seconds is not None
            else await request_coro
        )

    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        result = json.dumps(_extract_http_response_value(response.json(), response_path))
    elif "text/plain" in content_type or "text/html" in content_type:
        result = response.text
    else:
        result = response.text

    return _apply_response_size_policy(
        result,
        max_output_bytes=max_output_bytes,
        response_size_policy=response_size_policy,
    )


def _build_http_tool(
    *,
    tool_name: str,
    description: str,
    parameters: dict[str, Any],
    method: str,
    url: str,
    headers: dict[str, str] | None,
    body_template: str | None,
    response_path: str | None,
    timeout_seconds: int | None = None,
    max_output_bytes: int | None = None,
    response_size_policy: Callable[..., str] | None = None,
) -> ToolInstance:
    """Build a ToolInstance for an HTTP-backed tool."""

    async def _execute(args: dict) -> str:
        return await _execute_outbound_request(
            method=method,
            url=url,
            headers=headers,
            body_template=body_template,
            response_path=response_path,
            args=args,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            response_size_policy=response_size_policy,
        )

    return ToolInstance(
        name=tool_name,
        description=description,
        parameters=parameters,
        execute=_execute,
    )


def _resolve_http_tool_id(
    tool_id: str,
    *,
    tool_meta: ToolMeta | None = None,
    **kwargs: object,
) -> ToolInstance:
    """Resolve a discovered HTTP tool from its canonical workflow ID."""
    base_dir = kwargs.get("base_dir", ".")
    tool_meta = tool_meta or discover_custom_tools(base_dir).get(tool_id)
    if tool_meta is None:
        raise ValueError(f"Unknown HTTP tool source: {tool_id!r}")
    if tool_meta.executor != "request":
        raise ValueError(
            f"Custom tool {tool_id!r} uses unsupported executor for request resolution: "
            f"{tool_meta.executor!r}"
        )
    if tool_meta.request is None:
        raise ValueError(f"Request tool {tool_id!r} is missing request configuration")

    return _build_http_tool(
        tool_name=_tool_instance_name(tool_id),
        description=tool_meta.description,
        parameters=tool_meta.parameters,
        method=str(tool_meta.request.get("method", "GET")),
        url=str(tool_meta.request["url"]),
        headers=tool_meta.request.get("headers"),
        body_template=tool_meta.request.get("body_template"),
        response_path=tool_meta.request.get("response_path"),
        timeout_seconds=tool_meta.timeout_seconds,
        max_output_bytes=kwargs.get("max_output_bytes"),
        response_size_policy=kwargs.get("response_size_policy"),
    )


def resolve_tool_id(tool_id: str, **kwargs: object) -> ToolInstance:
    """Resolve a workflow-authored canonical tool ID to a ToolInstance."""
    if not isinstance(tool_id, str):
        raise TypeError(f"tool_id must be a string, got {type(tool_id)!r}")

    base_dir = kwargs.get("base_dir", ".")
    discovered_tools = discover_custom_tools(base_dir)

    if tool_id in RESERVED_BUILTIN_TOOL_IDS:
        if tool_id in discovered_tools:
            collision_path = discovered_tools[tool_id].file_path
            raise ValueError(
                f"reserved builtin tool id '{tool_id}' collides with custom tool metadata at "
                f"{collision_path}"
            )
        factory = BUILTIN_TOOL_CATALOG.get(tool_id)
        if factory is None:
            raise ValueError(f"Unknown builtin tool id: {tool_id!r}")
        return factory(**kwargs)

    tool_meta = discovered_tools.get(tool_id)
    if tool_meta is None:
        raise ValueError(f"Unknown tool id: {tool_id!r}")
    if tool_meta.executor == "python":
        return _resolve_custom_tool_id(tool_id, tool_meta=tool_meta, **kwargs)
    if tool_meta.executor == "request":
        return _resolve_http_tool_id(tool_id, tool_meta=tool_meta, **kwargs)

    raise ValueError(f"Unsupported discovered tool executor {tool_meta.executor!r} for {tool_id!r}")


def resolve_tool(tool_id: str, **kwargs: object) -> ToolInstance:
    """Resolve a canonical tool ID to a ToolInstance."""
    return resolve_tool_id(tool_id, **kwargs)
