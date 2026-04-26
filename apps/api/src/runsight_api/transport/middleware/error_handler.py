import logging
import re
from typing import Any

from fastapi import Request
from fastapi.exception_handlers import (
    request_validation_exception_handler as fastapi_validation_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ...core.context import request_id as _request_id_var
from ...domain.errors import RunsightError

logger = logging.getLogger(__name__)

_DIRECT_API_RUN_PATH = re.compile(r"^/api/workflows/([^/]+)/runs$")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = _request_id_var.get() or None

    if isinstance(exc, RunsightError):
        body = exc.to_dict()
        if rid:
            body["request_id"] = rid
        return JSONResponse(status_code=exc.status_code, content=body)

    logger.exception("Unhandled exception: %s", exc)
    body: dict = {
        "error": "Internal server error",
        "error_code": "INTERNAL_ERROR",
        "status_code": 500,
    }
    if rid:
        body["request_id"] = rid
    return JSONResponse(status_code=500, content=body)


def _workflow_request_field_error(error: dict[str, Any]) -> dict[str, Any]:
    loc = [part for part in error.get("loc", []) if part != "body"]
    field = str(loc[0]) if loc else "__body__"
    error_type = str(error.get("type", "invalid"))
    code = "malformed_request"
    expected_type: str | None = None
    actual_type: str | None = None

    if error_type == "missing":
        code = "required"
    elif error_type in {"dict_type", "model_attributes_type"}:
        code = "type_mismatch"
        expected_type = "json"
    elif error_type == "extra_forbidden":
        code = "unknown"

    if field == "__body__":
        input_path = ["body"]
    elif loc and str(loc[0]) == "inputs" and len(loc) > 1:
        field = str(loc[1])
        input_path = ["inputs", field]
    else:
        input_path = ["body", field]

    return {
        "field": field,
        "code": code,
        "message": "Run input request body is invalid.",
        "input_path": input_path,
        "expected_type": expected_type,
        "actual_type": actual_type,
    }


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    workflow_id: str | None = None
    if request.method == "POST" and request.url.path == "/api/runs":
        body_value = getattr(exc, "body", None)
        workflow_id = body_value.get("workflow_id") if isinstance(body_value, dict) else None
    elif request.method == "POST" and (match := _DIRECT_API_RUN_PATH.match(request.url.path)):
        workflow_id = match.group(1)
    else:
        return await fastapi_validation_handler(request, exc)

    fields = [_workflow_request_field_error(error) for error in exc.errors()]
    body: dict[str, Any] = {
        "error": "Workflow input validation failed",
        "error_code": "WORKFLOW_INPUT_VALIDATION_ERROR",
        "status_code": 422,
        "details": {
            "kind": "workflow_input_validation",
            "workflow_id": workflow_id if isinstance(workflow_id, str) else None,
            "fields": fields,
        },
    }
    rid = _request_id_var.get() or None
    if rid:
        body["request_id"] = rid
    return JSONResponse(status_code=422, content=body)
