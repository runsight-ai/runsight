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


def test_tools_list_includes_http_and_file_io_but_excludes_delegate(monkeypatch):
    _patch_custom_tools(monkeypatch, {})

    response = client.get("/api/tools")

    assert response.status_code == 200
    items = _items(response.json())
    slugs = {item["slug"] for item in items}

    assert "runsight/http" in slugs
    assert "runsight/file-io" in slugs
    assert "runsight/delegate" not in slugs


def test_tools_list_includes_custom_tools_from_discovery(monkeypatch):
    _patch_custom_tools(
        monkeypatch,
        {
            "report_lookup": ToolMeta(
                type="custom",
                source="report_lookup",
                code="def main(args): return {}",
            ),
            "profile_fetch": ToolMeta(
                type="http",
                source="profile_fetch",
                url="https://example.com/users/{{ user_id }}",
                method="GET",
            ),
        },
    )

    response = client.get("/api/tools")

    assert response.status_code == 200
    items = _items(response.json())
    indexed = {item["slug"]: item for item in items}

    assert indexed["report_lookup"]["type"] == "custom"
    assert indexed["profile_fetch"]["type"] == "http"
