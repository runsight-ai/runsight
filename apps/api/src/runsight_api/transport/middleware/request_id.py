"""Middleware that ensures every request/response carries an X-Request-ID."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from runsight_api.core.context import bind_request_context


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate or propagate X-Request-ID and bind it to structlog context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        bind_request_context(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
