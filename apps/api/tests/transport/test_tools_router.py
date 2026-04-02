from pathlib import Path

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_core.yaml.discovery import ToolMeta

client = TestClient(app)


def _items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"]
    return payload


def _tool_meta(tool_id, *, executor="python"):
    return ToolMeta(
        tool_id=tool_id,
        file_path=Path(f"/tmp/{tool_id}.yaml"),
        version="1.0",
        type="custom",
        executor=executor,
        name=tool_id.replace("_", " ").title(),
        description=f"{tool_id} description",
        parameters={"type": "object", "properties": {}},
        code="def main(args):\n    return args\n" if executor == "python" else None,
        request=(
            {
                "method": "GET",
                "url": "https://example.com/items/{{ item_id }}",
                "headers": {},
                "body_template": None,
                "response_path": "data.answer",
            }
            if executor == "request"
            else None
        ),
        timeout_seconds=9 if executor == "request" else None,
    )


def _patch_custom_tools(monkeypatch, mapping):
    monkeypatch.setattr(
        "runsight_core.yaml.discovery.discover_custom_tools",
        lambda base_dir: mapping,
    )
    try:
        import runsight_api.transport.routers.tools as tools_router
    except ImportError:
        return

    monkeypatch.setattr(tools_router, "discover_custom_tools", lambda base_dir: mapping)


def test_tools_list_endpoint_exists_and_returns_required_fields(monkeypatch):
    _patch_custom_tools(monkeypatch, {})

    response = client.get("/api/tools")

    assert response.status_code != 404, "Route /api/tools not registered"
    assert response.status_code != 405, "Method GET not allowed on /api/tools"

    if response.status_code == 200:
        items = _items(response.json())
        assert isinstance(items, list)
        assert items, "Expected builtin tools to be listed"
        required_fields = {"slug", "name", "description", "type"}
        for item in items:
            assert required_fields.issubset(item.keys())


def test_tools_list_uses_canonical_builtin_ids_and_hides_delegate(monkeypatch):
    _patch_custom_tools(monkeypatch, {})

    response = client.get("/api/tools")

    assert response.status_code == 200
    items = _items(response.json())
    slugs = {item["slug"] for item in items}

    assert "http" in slugs
    assert "file_io" in slugs
    assert "delegate" not in slugs
    assert "runsight/http" not in slugs
    assert "runsight/file-io" not in slugs


def test_tools_list_includes_discovered_custom_tool_ids(monkeypatch):
    _patch_custom_tools(
        monkeypatch,
        {
            "report_lookup": _tool_meta("report_lookup", executor="python"),
            "profile_fetch": _tool_meta("profile_fetch", executor="request"),
        },
    )

    response = client.get("/api/tools")

    assert response.status_code == 200
    items = _items(response.json())
    indexed = {item["slug"]: item for item in items}

    assert indexed["report_lookup"]["type"] == "custom"
    assert indexed["profile_fetch"]["type"] == "custom"
