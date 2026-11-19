"""全局异常处理。

[优化] 原代码：
    DEBUG_MODE = True
    if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
        detail = "用户名已存在"
    if DEBUG_MODE:
        error_data = {"traceback": ..., "error_detail": str(exc), "path": ...}
问题：
    1. 任何 Duplicate entry 都被说成“用户名已存在”，收藏重复、手机号重复全误报；
    2. DEBUG 硬编码 True，生产把 traceback、SQL、请求 URL 返回给客户端；
    3. 422 参数错误没有统一成 {code,message,data}。
修复：
    - 按约束名分别映射，唯一冲突返回 409；
    - DEBUG 从环境变量读取，默认关闭；
    - 服务端 logger.exception 记录完整堆栈，客户端只拿到安全信息；
    - 增加 RequestValidationError 统一处理。
"""

from __future__ import annotations

import logging
import traceback

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import DEBUG

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_payload(code: int, message: str, data=None, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"code": code, "message": message, "data": data},
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # [优化] 原代码丢失了 exc.headers，401 没有 WWW-Authenticate。
    return _error_payload(
        exc.status_code,
        str(exc.detail),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 不返回 input，避免把用户密码等敏感字段原样回显到响应/日志。
    errors = [
        {
            "loc": list(item.get("loc", [])),
            "msg": item.get("msg", "参数错误"),
            "type": item.get("type", "value_error"),
        }
        for item in exc.errors()
    ]
    return _error_payload(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "请求参数校验失败",
        {"errors": errors, "requestId": _request_id(request)},
    )


def _map_integrity_error(error_msg: str) -> tuple[int, str]:
    """把数据库约束名翻译成用户可理解的业务错误。"""
    msg = error_msg.lower()

    if "user_news_unique" in msg or "favorite.user_id" in msg:
        return status.HTTP_409_CONFLICT, "已经收藏过这篇新闻"
    if "uniq_history_user_news" in msg or "history.user_id" in msg:
        return status.HTTP_409_CONFLICT, "浏览历史已存在"
    if "username_unique" in msg or "user.username" in msg:
        return status.HTTP_409_CONFLICT, "用户名已存在"
    if "phone_unique" in msg or "user.phone" in msg:
        return status.HTTP_409_CONFLICT, "手机号已被绑定"
    if "token_unique" in msg or "user_token.token" in msg:
        return status.HTTP_409_CONFLICT, "令牌冲突，请重试"
    if "foreign key" in msg or "cannot add or update a child row" in msg:
        return status.HTTP_400_BAD_REQUEST, "关联数据不存在"
    return status.HTTP_400_BAD_REQUEST, "数据约束冲突，请检查输入"


async def integrity_error_handler(request: Request, exc: IntegrityError):
    error_msg = str(getattr(exc, "orig", exc))
    code, detail = _map_integrity_error(error_msg)
    logger.warning(
        "完整性约束冲突 request_id=%s path=%s detail=%s",
        _request_id(request),
        request.url.path,
        error_msg,
    )

    data = None
    if DEBUG:
        data = {
            "errorType": "IntegrityError",
            "errorDetail": error_msg,
            "path": str(request.url),
            "requestId": _request_id(request),
        }
    return _error_payload(code, detail, data)


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception(
        "数据库异常 request_id=%s path=%s",
        _request_id(request),
        request.url.path,
        exc_info=exc,
    )
    data = None
    if DEBUG:
        data = {
            "errorType": type(exc).__name__,
            "errorDetail": str(exc),
            "traceback": traceback.format_exc(),
            "path": str(request.url),
            "requestId": _request_id(request),
        }
    return _error_payload(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "数据库操作失败，请稍后重试",
        data,
    )


async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "未捕获异常 request_id=%s path=%s",
        _request_id(request),
        request.url.path,
        exc_info=exc,
    )
    data = None
    if DEBUG:
        data = {
            "errorType": type(exc).__name__,
            "errorDetail": str(exc),
            "traceback": traceback.format_exc(),
            "path": str(request.url),
            "requestId": _request_id(request),
        }
    return _error_payload(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "服务器内部错误",
        data,
    )
