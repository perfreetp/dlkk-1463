from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        message: str = "请求处理失败",
        detail: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.status_code = status_code
        self.message = message
        self.detail = detail or {}
        self.error_code = error_code
        super().__init__(self.message)


class AuthenticationError(AppException):
    def __init__(self, message: str = "认证失败", detail: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            detail=detail,
            error_code="AUTHENTICATION_ERROR",
        )


class AuthorizationError(AppException):
    def __init__(self, message: str = "权限不足", detail: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            detail=detail,
            error_code="AUTHORIZATION_ERROR",
        )


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在", detail: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            detail=detail,
            error_code="NOT_FOUND",
        )


class ValidationError(AppException):
    def __init__(self, message: str = "数据验证失败", detail: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            detail=detail,
            error_code="VALIDATION_ERROR",
        )


class BusinessError(AppException):
    def __init__(
        self,
        message: str = "业务处理失败",
        detail: Optional[Dict[str, Any]] = None,
        error_code: str = "BUSINESS_ERROR",
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            detail=detail,
            error_code=error_code,
        )


class DatabaseError(AppException):
    def __init__(self, message: str = "数据库操作失败", detail: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            detail=detail,
            error_code="DATABASE_ERROR",
        )


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, AppException):
        logger.warning(f"AppException: {exc.message} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "detail": exc.detail,
                "error_code": exc.error_code,
            },
        )

    if isinstance(exc, RequestValidationError):
        errors = []
        for error in exc.errors():
            errors.append({
                "loc": error["loc"],
                "msg": error["msg"],
                "type": error["type"],
            })
        logger.warning(f"ValidationError: {errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": "请求参数验证失败",
                "detail": {"errors": errors},
                "error_code": "VALIDATION_ERROR",
            },
        )

    if isinstance(exc, SQLAlchemyError):
        logger.error(f"DatabaseError: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "数据库操作异常",
                "detail": {},
                "error_code": "DATABASE_ERROR",
            },
        )

    logger.error(f"UnhandledException: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "服务器内部错误",
            "detail": {},
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )
