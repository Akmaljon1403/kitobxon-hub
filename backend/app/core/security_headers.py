"""HTTP hardening applied to every response and request.

* Security headers chosen per area: the API never renders HTML and must not be cached or
  framed; the Admin Panel may be framed only by Telegram Web; the Mini App must stay embeddable
  because Telegram Web shows it in an iframe (neither can sign in without Telegram's signed
  launch data or a one-time link anyway).
* Request body size limits, so a single request cannot exhaust memory.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # report photos are limited to 8 MB by the service

_COMMON = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}
_SPA_POLICY = (
    "default-src 'self'; script-src 'self'{scripts}; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'{frames}"
)
# The Admin Panel also opens inside Telegram (from the bot), so it may load Telegram's script and
# be shown by Telegram Web; no other site may embed it.
ADMIN_CSP = _SPA_POLICY.format(scripts=" https://telegram.org", frames="; frame-ancestors https://web.telegram.org")
MINIAPP_CSP = _SPA_POLICY.format(scripts=" https://telegram.org", frames="")
API_CSP = "default-src 'none'; frame-ancestors 'none'"
HSTS = "max-age=31536000"

_API_PREFIXES = ("/api/", "/telegram/", "/health")
_DOCS_PATHS = ("/api/docs", "/api/redoc", "/docs/oauth2-redirect")


def headers_for(path: str, *, production: bool) -> dict[str, str]:
    headers = dict(_COMMON)
    if production:
        headers["Strict-Transport-Security"] = HSTS
    if path == "/app" or path.startswith("/app/"):
        headers["Content-Security-Policy"] = MINIAPP_CSP
    elif path == "/admin" or path.startswith("/admin/"):
        # No X-Frame-Options here: it cannot allow Telegram Web; frame-ancestors in the CSP does.
        headers["Content-Security-Policy"] = ADMIN_CSP
    elif path.startswith(_DOCS_PATHS):
        headers["X-Frame-Options"] = "DENY"  # Swagger UI loads its own scripts; no CSP here
    else:
        headers["X-Frame-Options"] = "DENY"
        headers["Content-Security-Policy"] = API_CSP
        if path.startswith(_API_PREFIXES):
            # Personal data must never end up in a shared or browser cache.
            headers["Cache-Control"] = "no-store"
    return headers


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, production: bool) -> None:
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = headers_for(scope.get("path", ""), production=self.production)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in extra.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodyTooLargeError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413)


def body_limit(scope: Scope) -> int:
    for name, value in scope.get("headers", []):
        if name == b"content-type" and value.lower().startswith(b"multipart/form-data"):
            return MAX_UPLOAD_BYTES
    return MAX_JSON_BYTES


class BodySizeLimitMiddleware:
    """Rejects bodies above the limit: early from Content-Length, and while streaming for
    chunked requests (the error then surfaces as a 413 from the request handler)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        limit = body_limit(scope)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = limit + 1
                if declared > limit:
                    response = JSONResponse(
                        status_code=413,
                        content=error_body("PAYLOAD_TOO_LARGE", "Yuborilgan fayl yoki ma'lumot juda katta."),
                    )
                    await response(scope, receive, send)
                    return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise BodyTooLargeError
            return message

        await self.app(scope, limited_receive, send)
