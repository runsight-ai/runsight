import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from ...domain.errors import (
    WorkflowNotFound,
    SoulNotFound,
    RunFailed,
    RunNotFound,
    TaskNotFound,
    StepNotFound,
    ProviderNotConfigured,
)

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (WorkflowNotFound, SoulNotFound, RunNotFound, TaskNotFound, StepNotFound)):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": str(exc), "code": "NOT_FOUND"}
        )
    if isinstance(exc, ProviderNotConfigured):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(exc), "code": "PROVIDER_NOT_CONFIGURED"},
        )
    if isinstance(exc, RunFailed):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(exc), "code": "RUN_FAILED"},
        )

    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "code": "INTERNAL_ERROR"},
    )
