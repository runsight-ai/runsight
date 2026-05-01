"""
API OpenAPI schema contract coverage.

Coverage includes:
  1. OpenAPI spec can be extracted from FastAPI app
  2. OpenAPI spec contains schemas for workflow, run, soul, step, block entities
"""


# ---------------------------------------------------------------------------
# 1. OpenAPI spec extraction
# ---------------------------------------------------------------------------

class TestOpenAPISpecExtraction:
    """The FastAPI app should expose an OpenAPI spec that codegen can consume."""

    def test_openapi_json_endpoint_exists(self):
        """GET /openapi.json should return a valid OpenAPI 3.x spec."""
        from fastapi.testclient import TestClient

        from runsight_api.main import app

        client = TestClient(app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "openapi" in spec
        assert spec["openapi"].startswith("3.")

    def test_openapi_spec_contains_workflow_schemas(self):
        """The spec must include WorkflowResponse, WorkflowCreate, WorkflowUpdate schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schema_names = set(spec.get("components", {}).get("schemas", {}).keys())
        for expected in ["WorkflowResponse", "WorkflowCreate", "WorkflowUpdate"]:
            assert expected in schema_names, f"Missing schema: {expected}"

    def test_openapi_spec_contains_warning_item_schema_and_workflow_warnings_property(self):
        """Workflow responses must expose structured warnings in the OpenAPI schema."""
        from runsight_api.main import app

        spec = app.openapi()
        schemas = spec.get("components", {}).get("schemas", {})

        assert "WarningItem" in schemas, "Missing schema: WarningItem"

        workflow_schema = schemas["WorkflowResponse"]
        workflow_properties = workflow_schema.get("properties", {})
        assert "warnings" in workflow_properties, "WorkflowResponse is missing warnings"

        warnings_property = workflow_properties["warnings"]
        assert warnings_property.get("type") == "array"
        assert warnings_property.get("items", {}).get("$ref", "").endswith(
            "/WarningItem"
        )

        warning_item_schema = schemas["WarningItem"]
        warning_properties = warning_item_schema.get("properties", {})
        assert set(warning_properties) == {"message", "source", "context"}
        for expected in ["message", "source", "context"]:
            assert expected in warning_properties, (
                f"WarningItem is missing property: {expected}"
            )
        assert "code" not in warning_properties
        assert "severity" not in warning_properties

    def test_openapi_spec_exposes_single_canonical_warning_item_component(self):
        """Warnings must use one canonical WarningItem component across workflow/run schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schemas = spec.get("components", {}).get("schemas", {})

        warning_components = sorted(
            name for name in schemas if "warningitem" in name.lower()
        )
        assert warning_components == ["WarningItem"], (
            "OpenAPI must expose exactly one WarningItem-like component"
        )

        run_schema = schemas.get("RunResponse", {})
        run_warnings = run_schema.get("properties", {}).get("warnings", {})
        assert run_warnings.get("items", {}).get("$ref", "").endswith("/WarningItem")

    def test_openapi_spec_contains_run_schemas(self):
        """The spec must include RunResponse, RunCreate, RunNodeResponse schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schema_names = set(spec.get("components", {}).get("schemas", {}).keys())
        for expected in ["RunResponse", "RunCreate", "RunNodeResponse"]:
            assert expected in schema_names, f"Missing schema: {expected}"

        run_properties = spec["components"]["schemas"]["RunResponse"]["properties"]
        assert "warnings" in run_properties, "RunResponse is missing warnings"
        assert run_properties["warnings"].get("type") == "array"
        assert run_properties["warnings"].get("items", {}).get("$ref", "").endswith(
            "/WarningItem"
        )

    def test_openapi_spec_contains_soul_schemas(self):
        """The spec must include SoulResponse, SoulCreate, SoulUpdate schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schema_names = set(spec.get("components", {}).get("schemas", {}).keys())
        for expected in ["SoulResponse", "SoulCreate", "SoulUpdate"]:
            assert expected in schema_names, f"Missing schema: {expected}"
