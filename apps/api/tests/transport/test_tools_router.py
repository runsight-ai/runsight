from pathlib import Path
from textwrap import dedent

from fastapi.testclient import TestClient

from runsight_api.core.config import settings
from runsight_api.main import app

client = TestClient(app, raise_server_exceptions=False)

EXPECTED_ASSIGNABLE_TOOL_FIELDS = {"id", "name", "description", "origin", "executor"}


def _items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"]
    return payload


def _write_custom_tool_file(base_path: Path, tool_id: str, body: str) -> Path:
    tools_dir = base_path / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tools_dir / f"{tool_id}.yaml"
    tool_file.write_text(dedent(body).strip() + "\n", encoding="utf-8")
    return tool_file


def _tool_index(items):
    return {item["id"]: item for item in items}


def test_tools_list_returns_canonical_assignable_contract_for_builtins(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "base_path", str(tmp_path))

    response = client.get("/api/tools")

    assert response.status_code == 200
    items = _items(response.json())
    assert isinstance(items, list)
    assert items, "Expected builtin tools to be listed"
    for item in items:
        assert set(item) == EXPECTED_ASSIGNABLE_TOOL_FIELDS, item
        assert "slug" not in item
        assert "type" not in item
        assert not item["id"].startswith("runsight/"), item

    indexed = _tool_index(items)
    assert indexed == {
        "http": {
            "id": "http",
            "name": "HTTP Requests",
            "description": "Fetch external APIs.",
            "origin": "builtin",
            "executor": "native",
        },
        "file_io": {
            "id": "file_io",
            "name": "Workspace Files",
            "description": "Read project files.",
            "origin": "builtin",
            "executor": "native",
        },
    }
    assert "delegate" not in indexed


def test_tools_list_merges_builtin_and_custom_executor_variants_without_legacy_taxonomy(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "base_path", str(tmp_path))
    _write_custom_tool_file(
        tmp_path,
        "report_lookup",
        """
        id: report_lookup
        kind: tool
        version: "1.0"
        type: custom
        executor: python
        name: Report Lookup
        description: Look up saved reports.
        parameters:
          type: object
          properties:
            report_id:
              type: string
          required:
            - report_id
        code: |
          def main(args):
              return {"report_id": args["report_id"]}
        """,
    )
    _write_custom_tool_file(
        tmp_path,
        "profile_fetch",
        """
        id: profile_fetch
        kind: tool
        version: "1.0"
        type: custom
        executor: request
        name: Profile Fetch
        description: Fetch a remote profile.
        parameters:
          type: object
          properties:
            profile_id:
              type: string
          required:
            - profile_id
        request:
          method: GET
          url: https://example.com/profiles/{{ profile_id }}
          headers:
            X-Test: runsight
          response_path: data.profile
        timeout_seconds: 9
        """,
    )

    response = client.get("/api/tools")

    assert response.status_code == 200
    items = _items(response.json())
    assert isinstance(items, list)
    for item in items:
        assert set(item) == EXPECTED_ASSIGNABLE_TOOL_FIELDS, item
        assert "slug" not in item
        assert "type" not in item
        assert not item["id"].startswith("runsight/"), item

    indexed = _tool_index(items)
    assert indexed["http"]["origin"] == "builtin"
    assert indexed["http"]["executor"] == "native"
    assert indexed["file_io"]["origin"] == "builtin"
    assert indexed["file_io"]["executor"] == "native"
    assert indexed["report_lookup"] == {
        "id": "report_lookup",
        "name": "Report Lookup",
        "description": "Look up saved reports.",
        "origin": "custom",
        "executor": "python",
    }
    assert indexed["profile_fetch"] == {
        "id": "profile_fetch",
        "name": "Profile Fetch",
        "description": "Fetch a remote profile.",
        "origin": "custom",
        "executor": "request",
    }
    assert "delegate" not in indexed


def test_invalid_custom_tool_file_blocks_tools_api_with_explicit_file_specific_error(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "base_path", str(tmp_path))
    _write_custom_tool_file(
        tmp_path,
        "legacy_http",
        """
        version: "1.0"
        type: http
        """,
    )

    response = client.get("/api/tools")

    assert response.status_code >= 400
    body = response.json()
    assert "error" in body
    assert body["error"] != "Internal server error"
    assert "legacy_http.yaml" in body["error"]
    assert "type" in body["error"].lower()
