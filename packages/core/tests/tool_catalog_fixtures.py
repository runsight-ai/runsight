"""Package-local builders for tool catalog behavior suites."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


async def dummy_execute(args: dict) -> str:
    """Dummy async execute function for test ToolInstances."""
    return f"executed with {args}"


def fixture_url(path: str = "") -> str:
    """Return a syntactically valid dummy URL without contacting a live service."""
    return "https" + "://" + "request-tool-fixture.test" + path


def make_dummy_tool_instance():
    """Return a basic ToolInstance for schema and registry tests."""
    from runsight_core.tools import ToolInstance

    return ToolInstance(
        name="test_tool",
        description="A tool for testing",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        execute=dummy_execute,
    )


def write_custom_tool_yaml(base_dir: Path, slug: str, metadata: dict[str, Any]) -> Path:
    """Create a custom tool YAML file under an isolated fixture root."""
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": slug,
        "kind": "tool",
        "version": "1.0",
        "type": "custom",
        **metadata,
    }
    yaml_path = tools_dir / f"{slug}.yaml"
    yaml_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return yaml_path


def empty_object_parameters() -> dict[str, Any]:
    """Return the minimal object schema used by tools without inputs."""
    return {"type": "object", "properties": {}}


def two_integer_parameters() -> dict[str, Any]:
    """Return the shared two-integer parameter schema."""
    return {
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"},
        },
        "required": ["a", "b"],
    }


def write_adder_python_tool(base_dir: Path, slug: str = "adder") -> Path:
    """Write the canonical adder Python custom tool fixture."""
    return write_custom_tool_yaml(
        base_dir,
        slug,
        {
            "executor": "python",
            "name": "Adder",
            "description": "Add integers together.",
            "parameters": two_integer_parameters(),
            "code": 'def main(args):\n    return {"sum": args["a"] + args["b"]}\n',
        },
    )


def write_echo_json_python_tool(base_dir: Path, slug: str = "echo_json") -> Path:
    """Write a Python tool that round-trips JSON subprocess input."""
    return write_custom_tool_yaml(
        base_dir,
        slug,
        {
            "executor": "python",
            "name": "Echo JSON",
            "description": "Return a personalized message.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            "code": 'def main(args):\n    return {"message": "hello " + args["name"]}\n',
        },
    )


def write_blocked_import_python_tool(base_dir: Path) -> Path:
    """Write a Python tool fixture that imports a blocked module."""
    return write_custom_tool_yaml(
        base_dir,
        "blocked_import_tool",
        {
            "executor": "python",
            "name": "Blocked Import Tool",
            "description": "Imports a blocked module.",
            "parameters": empty_object_parameters(),
            "code": "import os\n\n\ndef main(args):\n    return {}\n",
        },
    )


def write_blocked_builtin_python_tool(base_dir: Path) -> Path:
    """Write a Python tool fixture that uses a blocked builtin."""
    return write_custom_tool_yaml(
        base_dir,
        "blocked_builtin_tool",
        {
            "executor": "python",
            "name": "Blocked Builtin Tool",
            "description": "Uses a blocked builtin.",
            "parameters": empty_object_parameters(),
            "code": 'def main(args):\n    eval("1 + 1")\n    return {}\n',
        },
    )


def write_slow_python_tool(base_dir: Path) -> Path:
    """Write a Python tool fixture that exceeds the execution timeout."""
    return write_custom_tool_yaml(
        base_dir,
        "slow_tool",
        {
            "executor": "python",
            "name": "Slow Tool",
            "description": "Sleeps longer than the timeout.",
            "parameters": empty_object_parameters(),
            "code": 'import time\n\n\ndef main(args):\n    time.sleep(5)\n    return {"done": True}\n',
        },
    )


def write_file_backed_python_tool(base_dir: Path) -> Path:
    """Write a Python tool that loads implementation code from code_file."""
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "file_backed_impl.py").write_text(
        'def main(args):\n    return {"port": args["port"]}\n',
        encoding="utf-8",
    )
    return write_custom_tool_yaml(
        base_dir,
        "file_backed",
        {
            "executor": "python",
            "name": "File Backed",
            "description": "Loads code from an external file.",
            "parameters": {
                "type": "object",
                "properties": {"port": {"type": "string"}},
                "required": ["port"],
            },
            "code_file": "file_backed_impl.py",
        },
    )


def write_shadow_http_python_tool(base_dir: Path) -> Path:
    """Write a custom tool that attempts to collide with the reserved http ID."""
    return write_custom_tool_yaml(
        base_dir,
        "http",
        {
            "executor": "python",
            "name": "Shadow HTTP",
            "description": "Attempts to shadow the reserved builtin ID.",
            "parameters": {"type": "object"},
            "code": "def main(args):\n    return args\n",
        },
    )


def write_fetch_answer_request_tool(base_dir: Path, slug: str = "fetch_answer") -> Path:
    """Write a request-backed tool fixture with a rendered URL and JSON path."""
    return write_custom_tool_yaml(
        base_dir,
        slug,
        {
            "executor": "request",
            "name": "Fetch Answer",
            "description": "Fetch an answer from a remote API.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}},
                "required": ["item_id"],
            },
            "request": {
                "method": "GET",
                "url": fixture_url("/items/{{ item_id }}"),
                "response_path": "data.answer",
            },
            "timeout_seconds": 9,
        },
    )


def write_lookup_profile_request_tool(base_dir: Path) -> Path:
    """Write a request tool fixture for template, env, and JSON-path behavior."""
    return write_custom_tool_yaml(
        base_dir,
        "lookup_profile",
        {
            "executor": "request",
            "name": "Lookup Profile",
            "description": "Fetch a user profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["user_id", "note"],
            },
            "request": {
                "method": "POST",
                "url": fixture_url("/users/{{ user_id }}"),
                "body_template": '{"token":"${AUTH_VALUE}","note":"{{ note }}"}',
                "response_path": "data.profile.name",
            },
        },
    )


def write_lookup_admin_request_tool(base_dir: Path) -> Path:
    """Write a request tool fixture whose rendered URL can be SSRF-blocked."""
    return write_custom_tool_yaml(
        base_dir,
        "lookup_admin",
        {
            "executor": "request",
            "name": "Lookup Admin",
            "description": "Fetch an admin page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "scheme": {"type": "string"},
                },
                "required": ["host", "scheme"],
            },
            "request": {"method": "GET", "url": "{{ scheme }}://{{ host }}/admin"},
        },
    )


def write_read_page_request_tool(
    base_dir: Path,
    *,
    slug: str = "read_page",
    path: str = "/plain",
) -> Path:
    """Write a simple GET request tool fixture."""
    return write_custom_tool_yaml(
        base_dir,
        slug,
        {
            "executor": "request",
            "name": "Read Page",
            "description": "Read a remote page.",
            "parameters": empty_object_parameters(),
            "request": {"method": "GET", "url": fixture_url(path)},
        },
    )


def write_secure_lookup_request_tool(base_dir: Path, *, location: str) -> Path:
    """Write a request tool fixture with a missing env reference in one location."""
    request: dict[str, Any] = {
        "method": "POST",
        "url": fixture_url("/secure"),
        "headers": {"Authorization": "Bearer ${MISSING_AUTH_VALUE}"},
        "body_template": '{"token":"${MISSING_AUTH_VALUE}"}',
    }
    if location == "headers":
        request = {
            "method": "GET",
            "url": fixture_url("/secure"),
            "headers": {"Authorization": "Bearer ${MISSING_AUTH_VALUE}"},
        }
    elif location == "body_template":
        request = {
            "method": "POST",
            "url": fixture_url("/secure"),
            "body_template": '{"token":"${MISSING_AUTH_VALUE}"}',
        }

    return write_custom_tool_yaml(
        base_dir,
        f"secure_lookup_{location}",
        {
            "executor": "request",
            "name": "Secure Lookup",
            "description": "Fetches a protected resource.",
            "parameters": empty_object_parameters(),
            "request": request,
        },
    )
