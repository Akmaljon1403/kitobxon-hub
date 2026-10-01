"""ASGI middleware: request correlation id, access log, safety headers, last-resort error handling."""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body
from app.core.logging import client_ip_ctx, request_id_ctx

logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.errors")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_QUIET_PATHS = ("/health",)


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
    return None


class RequestContextMiddleware:
    """Assigns a request id to every HTTP request and guarantees a JSON error body.

    The request id is returned in the ``X-Request-ID`` header, included in every log
    line and in error responses, so a user-reported problem can be traced in the logs.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        client = scope.get("client")
        ip_token = client_ip_ctx.set(client[0] if client else None)
        started_at = time.perf_counter()
        state = {"status": 500, "started": False}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["started"] = True
                state["status"] = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "no-referrer")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            error_logger.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if not state["started"]:
                response = JSONResponse(
                    status_code=500,
                    content=error_body(
                        "INTERNAL_ERROR", "Serverda kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring."
                    ),
                )
                await response(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            path = scope.get("path", "")
            level = logging.DEBUG if path.startswith(_QUIET_PATHS) else logging.INFO
            # Only the path is logged: query strings may carry tokens or personal data.
            logger.log(
                level,
                "%s %s -> %s",
                scope.get("method"),
                path,
                state["status"],
                extra={"status": state["status"], "duration_ms": duration_ms},
            )
            request_id_ctx.reset(token)
            client_ip_ctx.reset(ip_token)
