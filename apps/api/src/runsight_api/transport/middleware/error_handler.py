import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from ...core.context import request_id as _request_id_var
from ...domain.errors import RunsightError

logger = logging.getLogger(__name__)

# Map status codes to legacy simplified "code" values for backward compatibility.
_LEGACY_CODE_BY_STATUS = {
    404: "NOT_FOUND",
}


def _legacy_code(exc: RunsightError) -> str:
    """Derive the legacy 'code' field from the structured error."""
    return _LEGACY_CODE_BY_STATUS.get(exc.status_code, exc.error_code)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = _request_id_var.get() or None

    if isinstance(exc, RunsightError):
        body = exc.to_dict()
        body["code"] = _legacy_code(exc)
        if rid:
            body["request_id"] = rid
        return JSONResponse(status_code=exc.status_code, content=body)

    logger.exception("Unhandled exception: %s", exc)
    body: dict = {
        "error": "Internal server error",
        "error_code": "INTERNAL_ERROR",
        "code": "INTERNAL_ERROR",
        "status_code": 500,
    }
    if rid:
        body["request_id"] = rid
    return JSONResponse(status_code=500, content=body)
