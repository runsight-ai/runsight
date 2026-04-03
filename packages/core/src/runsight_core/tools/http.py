"""Built-in HTTP tool."""

from __future__ import annotations

from typing import Any, Callable, Dict

from runsight_core.tools._catalog import ToolInstance, _execute_outbound_request, register_builtin

_PARAMETERS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "method": {"type": "string"},
        "url": {"type": "string"},
        "headers": {"type": "object"},
        "body": {"type": "string"},
    },
    "required": ["method", "url"],
}


async def _execute(
    args: dict,
    *,
    timeout_seconds: int | None = None,
    max_output_bytes: int | None = None,
    response_size_policy: Callable[..., str] | None = None,
) -> str:
    """Execute the builtin HTTP tool through the shared outbound request path."""
    return await _execute_outbound_request(
        method=str(args["method"]),
        url=str(args["url"]),
        headers=args.get("headers"),
        body_template=args.get("body"),
        response_path=None,
        args=args,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        response_size_policy=response_size_policy,
    )


def create_http_tool(
    *,
    timeout_seconds: int | None = None,
    max_output_bytes: int | None = None,
    response_size_policy: Callable[..., str] | None = None,
    **_: Any,
) -> ToolInstance:
    """Factory that returns a ToolInstance for HTTP requests."""

    async def _execute_with_options(args: dict) -> str:
        return await _execute(
            args,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            response_size_policy=response_size_policy,
        )

    return ToolInstance(
        name="http_request",
        description="Make an HTTP request to an external URL.",
        parameters=_PARAMETERS_SCHEMA,
        execute=_execute_with_options,
    )


register_builtin("http", create_http_tool)
register_builtin("runsight/http", create_http_tool)
