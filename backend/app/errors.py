"""One error shape for every non-2xx response (contract section 2).

{ "error": { "code": "...", "message": "...", "details": null | [...] } }
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.enums import HTTP_STATUS_FOR_CODE, ErrorCode
from app.rules import Rejection

logger = logging.getLogger("blinkhub")


class AppError(Exception):
    """Raised anywhere in the app to send a contract-shaped error response."""

    def __init__(self, code: ErrorCode, message: str, details: list[dict[str, str]] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    @property
    def status_code(self) -> int:
        return HTTP_STATUS_FOR_CODE[self.code]

    @classmethod
    def from_rejection(cls, rejection: Rejection) -> AppError:
        return cls(rejection.code, rejection.message, rejection.details)


def error_body(code: ErrorCode | str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": str(code), "message": message, "details": details}}


# Default codes for HTTP errors raised by the framework itself (unknown route, wrong method).
_CODE_FOR_HTTP_STATUS = {
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
}


def _field_name(err: dict[str, Any]) -> str:
    if err.get("type") == "json_invalid":
        return "body"
    # Pydantic locations look like ("body", "amount") or ("query", "status").
    # The contract wants just the field name, so drop the leading section.
    parts = [str(p) for p in err.get("loc", ())]
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]
    return ".".join(parts) or "body"


def _clean_message(message: str) -> str:
    # Pydantic prefixes custom validator messages with "Value error, "; drop it.
    return message.removeprefix("Value error, ")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": _field_name(err),
                "message": _clean_message(str(err.get("msg", "invalid"))),
            }
            for err in exc.errors()
        ]
        summary = "; ".join(f"{d['field']}: {d['message']}" for d in details) or "Invalid request."
        return JSONResponse(error_body(ErrorCode.VALIDATION_ERROR, summary, details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODE_FOR_HTTP_STATUS.get(exc.status_code, f"HTTP_{exc.status_code}")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        if exc.status_code == 404:
            message = "Not found."
        return JSONResponse(error_body(code, message), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            error_body(ErrorCode.INTERNAL_ERROR, "Something went wrong on the server."), status_code=500
        )
