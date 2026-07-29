"""统一错误码与响应包装（系统设计说明书 §8.3）。

错误码前缀：VALIDATION_ 输入问题 / BUSINESS_ 业务规则拦截 / SYNC_ 同步异常。
message 一律是可以直接展示给使用者的中文文案。
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """业务/校验/同步异常的基类，routers 与 services 都应抛出这个而不是裸 HTTPException。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationAppError(AppError):
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        code: str = "VALIDATION_ERROR",
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class BusinessAppError(AppError):
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        code: str = "BUSINESS_ERROR",
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class SyncAppError(AppError):
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        code: str = "SYNC_ERROR",
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class UnauthorizedAppError(AppError):
    def __init__(self, message: str = "未登录或登录已失效", details: dict[str, Any] | None = None):
        super().__init__(
            code="BUSINESS_UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message, "details": details or {}}}


def success_body(data: Any = None, server_rev: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"success": True, "data": data}
    if server_rev is not None:
        body["server_rev"] = server_rev
    return body


def _json_safe_validation_detail(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe_validation_detail(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_validation_detail(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.details),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = {"errors": _json_safe_validation_detail(exc.errors())}
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body("VALIDATION_ERROR", "请求参数不正确，请检查后重试", details),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body("BUSINESS_ERROR", str(exc.detail) if exc.detail else "请求处理失败"),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("BUSINESS_INTERNAL_ERROR", "系统内部错误，请稍后重试或联系管理员"),
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
