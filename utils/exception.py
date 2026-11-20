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
# logger 是 logging 模块里“按模块名分类打日志”的对象；
# 用 __name__ 当名字，日志里就能看出是哪个文件打的，方便排查。


def _request_id(request: Request) -> str | None:
    """取出中间件给这次请求生成的追踪 id。

    参数：
        request: 当前请求对象；它的 state 上可能挂着中间件写入的 request_id。
    返回：
        有就返回字符串 id，没有则返回 None（例如没走那个中间件的测试请求）。
    """
    # 用 getattr 加默认值而不是直接访问属性：request.state 上不一定有 request_id，
    # 直接点属性会抛 AttributeError，把“记日志”变成新的报错。
    return getattr(request.state, "request_id", None)


def _error_payload(code: int, message: str, data=None, headers: dict | None = None) -> JSONResponse:
    """按项目统一的 {code, message, data} 结构构造错误响应。

    参数：
        code: HTTP 状态码，同时写进响应体的 code 字段，前端只认一处即可。
        message: 给用户看的中文错误说明。
        data: 附加数据，默认 None；只有调试模式才会塞细节。
        headers: 需要原样带回去的响应头（如 401 的 WWW-Authenticate）。
    返回：
        一个 JSONResponse 对象，交给 FastAPI 直接发出去。
    """
    # 所有错误都走这一个出口，前端只写一套解析逻辑：
    # 先看响应体的 code，再从 message 拿提示，data 里放细节。
    return JSONResponse(
        status_code=code,
        content={"code": code, "message": message, "data": data},
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理业务代码里主动抛出的 HTTPException（如 404 新闻不存在）。

    参数：
        request: 当前请求，这里暂时用不到，只为符合处理器的固定签名。
        exc: 抛出的异常对象，status_code 和 detail 就是业务方写的那两个值。
    返回：
        统一结构后的 JSONResponse。
    """
    # [优化] 原代码丢失了 exc.headers，401 没有 WWW-Authenticate。
    # HEADERS 对浏览器和调试工具是有效信息（例如告诉客户端该用哪种认证方式），
    # 所以有就原样透传，没有就传 None。
    return _error_payload(
        exc.status_code,
        str(exc.detail),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数校验失败（Pydantic 没通过）。

    参数：
        request: 当前请求，用来取 request_id 方便和日志对上。
        exc: 校验异常，errors() 里是每个字段出错的位置和原因。
    返回：
        422 状态的统一 JSONResponse，data.errors 是精简后的错误列表。
    """
    # 不返回 input，避免把用户密码等敏感字段原样回显到响应/日志。
    # loc 是 location 的缩写，指出错字段在请求里的路径，如 ["body", "news_id"]。
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
    # 参数：error_msg 是数据库原始报错文本，里面带着违反的约束名（如 username_UNIQUE）。
    # 返回：(HTTP 状态码, 中文提示) 二元组；认不出的约束统一按 400 处理。
    # 先转小写再匹配：MySQL、SQLite 报错里的约束名大小写并不统一。
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
    """处理数据库约束冲突（唯一键重复、外键不存在）。

    参数：
        request: 当前请求，用于记录 path 和 request_id。
        exc: SQLAlchemy 的完整性异常，原始数据库报错在它的 orig 属性里。
    返回：
        409 或 400 的统一 JSONResponse；调试模式下 data 里多带原始报错。
    """
    # 有的驱动不填 orig，所以用 getattr 兜底成异常本身，保证一定能拿到文字。
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
        # 只有 DEBUG 为真（本地开发）才回传数据库原文；
        # 生产环境把这些内容暴露出去，等于把表结构告诉攻击者。
        data = {
            "errorType": "IntegrityError",
            "errorDetail": error_msg,
            "path": str(request.url),
            "requestId": _request_id(request),
        }
    return _error_payload(code, detail, data)


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """处理其他数据库错误（连接失败、SQL 写错等）。

    参数：
        request: 当前请求，用于记录 path 和 request_id。
        exc: SQLAlchemy 异常基类的实例。
    返回：
        500 的统一 JSONResponse；调试模式下 data 里附带堆栈。
    """
    # logger.exception 会自动带上当前异常的完整堆栈，
    # 比 logger.error 多一份 traceback，排查线上问题时非常关键。
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
    """兜底处理所有没被前面处理器接住的异常。

    参数：
        request: 当前请求，用于记录 path 和 request_id。
        exc: 任意异常对象。
    返回：
        500 的统一 JSONResponse；客户端只会看到“服务器内部错误”。
    """
    # 这里一定要记完整堆栈：如果不记，线上只会看到一句“服务器内部错误”，
    # 完全不知道是哪个函数炸的。
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
