"""Application errors and the single, consistent API error format.

Every error response has the shape::

    {
      "success": false,
      "error": {"code": "ATTENDANCE_EXPIRED", "message": "...", "request_id": "..."}
    }

Internal details (stack traces, SQL, file paths) are never sent to clients; they are
written to the server log together with the request id so they can be correlated.
Messages are written in Uzbek because they are shown directly to club members.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected business/API errors."""

    status_code: int = 400
    code: str = "BAD_REQUEST"
    message: str = "So'rov noto'g'ri."

    def __init__(
        self,
        code: str | None = None,
        message: str | None = None,
        *,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        self.code = code or self.code
        self.message = message or self.message
        if status_code is not None:
            self.status_code = status_code
        self.details = details
        super().__init__(f"{self.code}: {self.message}")


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"
    message = "So'rov noto'g'ri."


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Avval tizimga kiring."


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "Bu amal uchun ruxsatingiz yo'q."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Ma'lumot topilmadi."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Bu amal allaqachon bajarilgan yoki ma'lumotlar ziddiyatli."


class ValidationFailedError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Kiritilgan ma'lumotlar noto'g'ri."


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "Xizmat vaqtincha ishlamayapti."


_HTTP_STATUS_CODES = {
    400: ("BAD_REQUEST", "So'rov noto'g'ri."),
    401: ("UNAUTHORIZED", "Avval tizimga kiring."),
    403: ("FORBIDDEN", "Bu amal uchun ruxsatingiz yo'q."),
    404: ("NOT_FOUND", "Sahifa yoki ma'lumot topilmadi."),
    405: ("METHOD_NOT_ALLOWED", "Bu usul qo'llab-quvvatlanmaydi."),
    413: ("PAYLOAD_TOO_LARGE", "Yuborilgan fayl yoki ma'lumot juda katta."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Fayl turi qo'llab-quvvatlanmaydi."),
    429: ("RATE_LIMITED", "Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring."),
}


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    request_id = request_id_ctx.get()
    if request_id:
        error["request_id"] = request_id
    return {"success": False, "error": error}


def _response(status_code: int, code: str, message: str, details: Any = None, headers=None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_body(code, message, details), headers=headers)


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    headers = (
        {"Retry-After": str(exc.details["retry_after"])}
        if (isinstance(exc, RateLimitedError) and isinstance(exc.details, dict) and "retry_after" in exc.details)
        else None
    )
    return _response(exc.status_code, exc.code, exc.message, exc.details, headers)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Report where and why validation failed, but never echo the submitted values back.
    details = [
        {"field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"), "reason": err.get("msg", "")}
        for err in exc.errors()
    ]
    # Log the field+reason (never the submitted values) so a 422 is diagnosable from the server log.
    logger.warning("Request validation failed on %s %s: %s", request.method, request.url.path, details)
    return _response(422, "VALIDATION_ERROR", "Kiritilgan ma'lumotlar noto'g'ri.", details)


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code, message = _HTTP_STATUS_CODES.get(exc.status_code, ("HTTP_ERROR", "So'rovni bajarib bo'lmadi."))
    return _response(exc.status_code, code, message, headers=getattr(exc, "headers", None))


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _response(500, "INTERNAL_ERROR", "Serverda kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
