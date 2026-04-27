from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not _is_direct_api_invocation_request(scope):
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope.get("headers", []))
        if content_length is not None and content_length > self.max_body_bytes:
            await _body_too_large_response()(scope, receive, send)
            return

        limited_receive = _LimitedReceive(
            receive,
            max_body_bytes=self.max_body_bytes,
        )
        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _body_too_large_response()(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


class _LimitedReceive:
    def __init__(self, receive: Receive, *, max_body_bytes: int) -> None:
        self.receive = receive
        self.max_body_bytes = max_body_bytes
        self.bytes_seen = 0
        self.rejected = False

    async def __call__(self) -> Message:
        if self.rejected:
            return {"type": "http.disconnect"}

        message = await self.receive()
        if message["type"] != "http.request":
            return message

        body = message.get("body", b"")
        self.bytes_seen += len(body)
        if self.bytes_seen > self.max_body_bytes:
            self.rejected = True
            raise _BodyTooLarge()
        return message


def _content_length(headers: list[tuple[bytes, bytes]]) -> int | None:
    for name, value in headers:
        if name.lower() != b"content-length":
            continue
        try:
            return int(value.decode("ascii"))
        except ValueError:
            return None
    return None


def _is_direct_api_invocation_request(scope: Scope) -> bool:
    if scope.get("method") != "POST":
        return False
    parts = str(scope.get("path", "")).strip("/").split("/")
    return len(parts) == 4 and parts[0] == "api" and parts[1] == "workflows" and parts[3] == "runs"


def _body_too_large_response() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={
            "error": "Request body too large",
            "error_code": "REQUEST_BODY_TOO_LARGE",
            "status_code": 413,
        },
    )
