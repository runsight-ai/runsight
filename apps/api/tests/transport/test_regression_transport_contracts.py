"""Regression endpoints use shared transport schemas."""

from __future__ import annotations

from fastapi.routing import APIRoute

from runsight_api.main import app

VALID_REGRESSION_TYPES = [
    "assertion_regression",
    "cost_spike",
    "quality_drop",
]


def _get_route(path: str, method: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Could not find {method} route for {path}")


class TestRegressionRoutesDeclareTransportContracts:
    def test_run_regressions_route_declares_response_model(self):
        route = _get_route("/api/runs/{run_id}/regressions", "GET")

        assert route.response_model is not None
        assert route.response_model.__name__ == "RunRegressionsResponse"

    def test_workflow_regressions_route_declares_response_model(self):
        route = _get_route("/api/workflows/{id}/regressions", "GET")

        assert route.response_model is not None
        assert route.response_model.__name__ == "WorkflowRegressionsResponse"

    def test_run_regressions_response_model_accepts_only_backend_regression_types(self):
        route = _get_route("/api/runs/{run_id}/regressions", "GET")
        response_model = route.response_model

        assert response_model is not None
        parsed = response_model.model_validate(
            {
                "count": 3,
                "issues": [
                    {
                        "node_id": "review",
                        "node_name": "Review",
                        "type": "assertion_regression",
                        "delta": {"eval_passed": False},
                    },
                    {
                        "node_id": "writer",
                        "node_name": "Writer",
                        "type": "cost_spike",
                        "delta": {"cost_pct": 38},
                    },
                    {
                        "node_id": "score",
                        "node_name": "Score",
                        "type": "quality_drop",
                        "delta": {"score_delta": -0.2},
                    },
                ],
            }
        )

        assert [issue.type for issue in parsed.issues] == VALID_REGRESSION_TYPES

    def test_workflow_regressions_response_model_preserves_run_context_shape(self):
        route = _get_route("/api/workflows/{id}/regressions", "GET")
        response_model = route.response_model

        assert response_model is not None
        parsed = response_model.model_validate(
            {
                "count": 1,
                "issues": [
                    {
                        "node_id": "review",
                        "node_name": "Review",
                        "type": "assertion_regression",
                        "delta": {"eval_passed": False},
                        "run_id": "run_regression_transport",
                        "run_number": 12,
                    }
                ],
            }
        )

        issue = parsed.issues[0]
        assert issue.run_id == "run_regression_transport"
        assert issue.run_number == 12


class TestRegressionTransportSchemas:
    def test_transport_modules_export_run_and_workflow_regression_models(self):
        import runsight_api.transport.schemas.runs as run_schemas
        import runsight_api.transport.schemas.workflows as workflow_schemas

        assert hasattr(run_schemas, "RunRegressionIssue")
        assert hasattr(run_schemas, "RunRegressionsResponse")
        assert hasattr(workflow_schemas, "WorkflowRegressionIssue")
        assert hasattr(workflow_schemas, "WorkflowRegressionsResponse")

    def test_transport_issue_shapes_preserve_run_vs_workflow_difference(self):
        import runsight_api.transport.schemas.runs as run_schemas
        import runsight_api.transport.schemas.workflows as workflow_schemas

        assert hasattr(run_schemas, "RunRegressionIssue")
        assert hasattr(workflow_schemas, "WorkflowRegressionIssue")

        run_issue_fields = set(run_schemas.RunRegressionIssue.model_fields.keys())
        workflow_issue_fields = set(workflow_schemas.WorkflowRegressionIssue.model_fields.keys())

        assert run_issue_fields == {"node_id", "node_name", "type", "delta"}
        assert workflow_issue_fields == {
            "node_id",
            "node_name",
            "type",
            "delta",
            "run_id",
            "run_number",
        }


class TestRegressionOpenAPIContracts:
    def test_openapi_uses_named_components_for_both_regressions_endpoints(self):
        spec = app.openapi()
        run_schema = spec["paths"]["/api/runs/{run_id}/regressions"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        workflow_schema = spec["paths"]["/api/workflows/{id}/regressions"]["get"]["responses"][
            "200"
        ]["content"]["application/json"]["schema"]

        assert run_schema == {"$ref": "#/components/schemas/RunRegressionsResponse"}
        assert workflow_schema == {"$ref": "#/components/schemas/WorkflowRegressionsResponse"}

    def test_openapi_components_define_issue_shapes_and_legitimate_type_values(self):
        spec = app.openapi()
        components = spec["components"]["schemas"]

        assert "RunRegressionIssue" in components
        assert "RunRegressionsResponse" in components
        assert "WorkflowRegressionIssue" in components
        assert "WorkflowRegressionsResponse" in components

        run_issue = components["RunRegressionIssue"]
        workflow_issue = components["WorkflowRegressionIssue"]

        assert set(run_issue["properties"].keys()) == {"node_id", "node_name", "type", "delta"}
        assert set(workflow_issue["properties"].keys()) == {
            "node_id",
            "node_name",
            "type",
            "delta",
            "run_id",
            "run_number",
        }
        assert run_issue["properties"]["type"]["enum"] == VALID_REGRESSION_TYPES
        assert workflow_issue["properties"]["type"]["enum"] == VALID_REGRESSION_TYPES
