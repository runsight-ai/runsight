"""Built-in HTTP tool: runsight/http."""

from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from runsight_core.security import validate_ssrf
from runsight_core.tools._catalog import ToolInstance, register_builtin

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


async def _execute(args: dict) -> str:
    """Execute an HTTP request after SSRF validation."""
    url = args["url"]
    method = args["method"]
    headers = args.get("headers")
    body = args.get("body")

    await validate_ssrf(url)

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            url,
            headers=headers,
            content=body,
        )

    return json.dumps(
        {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text,
        }
    )


def create_http_tool() -> ToolInstance:
    """Factory that returns a ToolInstance for HTTP requests."""
    return ToolInstance(
        name="http_request",
        description="Make an HTTP request to an external URL.",
        parameters=_PARAMETERS_SCHEMA,
        execute=_execute,
    )


register_builtin("runsight/http", create_http_tool)
