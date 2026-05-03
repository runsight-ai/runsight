"""Governance: routers use centralized domain error handling.

Boundary: workflow and run routers must not bypass the shared exception handlers.
Owner: API transport owners.
Exit criteria: remove once route-level linting enforces the same boundary.
"""

from pathlib import Path


def test_no_manual_json_response_in_workflows():
    workflows_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "runsight_api"
        / "transport"
        / "routers"
        / "workflows.py"
    )
    source = workflows_path.read_text()

    assert "JSONResponse" not in source


def test_no_http_exception_in_runs():
    runs_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "runsight_api"
        / "transport"
        / "routers"
        / "runs.py"
    )
    source = runs_path.read_text()

    assert "HTTPException" not in source
