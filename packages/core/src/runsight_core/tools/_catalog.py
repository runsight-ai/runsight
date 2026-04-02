"""Built-in tool catalog: ToolInstance, registration, and resolution."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Dict

import httpx

from runsight_core.blocks.code import (
    _HARNESS_PREFIX,
    _HARNESS_SUFFIX,
    DEFAULT_ALLOWED_IMPORTS,
    _validate_code_ast,
)
from runsight_core.security import validate_ssrf
from runsight_core.yaml.discovery import ToolMeta, discover_custom_tools
from runsight_core.yaml.schema import BuiltinToolDef, CustomToolDef, HTTPToolDef, ToolDef

# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------

BUILTIN_TOOL_CATALOG: Dict[str, Callable] = {}
RESERVED_BUILTIN_TOOL_IDS = frozenset({"http", "file_io", "delegate"})
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


def _resolve_builtin_tool(tool_def: BuiltinToolDef, **kwargs: object) -> ToolInstance:
    """Resolve a built-in tool through the registered factory catalog."""
    factory = BUILTIN_TOOL_CATALOG.get(tool_def.source)
    if factory is None:
        raise ValueError(f"Unknown tool source: {tool_def.source!r}")
    return factory(**kwargs)


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
        description=f"Custom tool '{tool_id}'",
        parameters={"type": "object", "properties": {}},
        execute=_execute,
    )


def resolve_custom_tool(tool_def: CustomToolDef, **kwargs: object) -> ToolInstance:
    """Resolve a custom tool from ``custom/tools/*.yaml`` metadata."""
    return _resolve_custom_tool_id(tool_def.source, **kwargs)


def _render_http_template(template: str | None, args: dict) -> str | None:
    """Render ``{{ param }}`` placeholders and ``${ENV}`` references."""
    if template is None:
        return None

    rendered = _ARG_TEMPLATE_RE.sub(lambda match: str(args.get(match.group(1), "")), template)
    return _ENV_TEMPLATE_RE.sub(lambda match: os.environ.get(match.group(1), ""), rendered)


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


def _build_http_tool(
    *,
    tool_name: str,
    method: str,
    url: str,
    body_template: str | None,
    response_path: str | None,
) -> ToolInstance:
    """Build a ToolInstance for an HTTP-backed tool."""

    async def _execute(args: dict) -> str:
        rendered_url = _render_http_template(url, args)
        rendered_body = _render_http_template(body_template, args)
        await validate_ssrf(rendered_url)

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method.upper(),
                rendered_url,
                headers=None,
                content=rendered_body,
            )

        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            payload = response.json()
            return json.dumps(_extract_http_response_value(payload, response_path))
        if "text/plain" in content_type or "text/html" in content_type:
            return response.text
        return response.text

    return ToolInstance(
        name=tool_name,
        description=f"HTTP tool '{tool_name}'",
        parameters={"type": "object", "properties": {}},
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
    if tool_meta is None or tool_meta.type != "http":
        raise ValueError(f"Unknown HTTP tool source: {tool_id!r}")
    if tool_meta.url is None:
        raise ValueError("HTTP tools must declare either an inline URL or a file source slug")

    return _build_http_tool(
        tool_name=_tool_instance_name(tool_id),
        method=tool_meta.method or "GET",
        url=tool_meta.url,
        body_template=tool_meta.body_template,
        response_path=tool_meta.response_path,
    )


def _resolve_http_tool(tool_def: HTTPToolDef, **kwargs: object) -> ToolInstance:
    """Resolve an HTTP tool from inline fields or ``custom/tools/*.yaml`` metadata."""
    method = tool_def.method or "GET"
    url = tool_def.url
    body_template = tool_def.body_template
    response_path = tool_def.response_path

    if url is None:
        if tool_def.source is None:
            raise ValueError("HTTP tools must declare either an inline URL or a file source slug")
        return _resolve_http_tool_id(tool_def.source, **kwargs)

    return _build_http_tool(
        tool_name=_tool_instance_name(tool_def.source or "http_tool"),
        method=method,
        url=url,
        body_template=body_template,
        response_path=response_path,
    )


def resolve_tool_id(tool_id: str, **kwargs: object) -> ToolInstance:
    """Resolve a workflow-authored canonical tool ID to a ToolInstance."""
    if tool_id in RESERVED_BUILTIN_TOOL_IDS:
        factory = BUILTIN_TOOL_CATALOG.get(tool_id)
        if factory is None:
            raise ValueError(f"Unknown builtin tool id: {tool_id!r}")
        return factory(**kwargs)

    base_dir = kwargs.get("base_dir", ".")
    tool_meta = discover_custom_tools(base_dir).get(tool_id)
    if tool_meta is None:
        raise ValueError(f"Unknown tool id: {tool_id!r}")
    if tool_meta.type == "custom":
        return _resolve_custom_tool_id(tool_id, tool_meta=tool_meta, **kwargs)
    if tool_meta.type == "http":
        return _resolve_http_tool_id(tool_id, tool_meta=tool_meta, **kwargs)

    raise ValueError(f"Unsupported discovered tool type {tool_meta.type!r} for {tool_id!r}")


def resolve_tool(tool_def: ToolDef, **kwargs: object) -> ToolInstance:
    """Dispatch to the appropriate resolver for the validated ToolDef variant.

    Raises:
        ValueError: If the builtin source is not registered in BUILTIN_TOOL_CATALOG.
        NotImplementedError: If custom/http resolution has not been implemented yet.
    """
    if isinstance(tool_def, BuiltinToolDef):
        return _resolve_builtin_tool(tool_def, **kwargs)
    if isinstance(tool_def, CustomToolDef):
        return resolve_custom_tool(tool_def, **kwargs)
    if isinstance(tool_def, HTTPToolDef):
        return _resolve_http_tool(tool_def, **kwargs)

    raise TypeError(f"Unsupported tool definition type: {type(tool_def)!r}")
