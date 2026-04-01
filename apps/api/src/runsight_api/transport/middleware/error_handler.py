import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from ...core.context import request_id as _request_id_var
from ...domain.errors import RunsightError

logger = logging.getLogger(__name__)


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
