"""统一响应工具。

[优化] 原代码：
    def success_response(...):
        content = {"code": 200, ...}
        return JSONResponse(content=jsonable_encoder(content))
问题：
    1. 直接返回 Response 会绕过 FastAPI 的 response_model，
       OpenAPI 里没有字段结构，也无法自动按 alias 序列化；
    2. jsonable_encoder 对 ORM 的 by_alias 行为依赖对象类型，容易不一致。
修复：
    返回 Pydantic 的 ApiResponse，由 FastAPI 按 response_model + alias 序列化。
"""

from __future__ import annotations

from typing import TypeVar

from schemas.common import ApiResponse, ok

T = TypeVar("T")


def success_response(message: str = "success", data: T | None = None) -> ApiResponse[T]:
    """兼容旧调用点的薄封装；新代码建议直接用 ok()。"""
    return ok(data=data, message=message)
