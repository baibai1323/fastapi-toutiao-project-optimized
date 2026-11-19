"""Schema 公共基类。

[优化] 原代码在每个字段上手工写 alias：
    category_id: int = Field(alias="categoryId")
    publish_time: Optional[datetime] = Field(None, alias="publishedTime")  # 拼错
问题：
    1. 字段一多就容易漏写/拼错；
    2. 列表接口直接返回 ORM，`publish_time` 根本没走 alias；
    3. 每个响应各自定义 list/total/hasMore，契约不统一。
修复：
    - 统一 alias_generator=to_camel，Python 用 snake_case，JSON 自动 camelCase；
    - 统一 ApiResponse[T] / PageResponse[T] 泛型；
    - 响应模型统一 from_attributes，但仍通过 response_model 显式声明。
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ApiResponse(CamelModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: T | None = None


class PageResponse(CamelModel, Generic[T]):
    list: list[T]
    total: int
    has_more: bool


def ok(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    return ApiResponse[T](code=200, message=message, data=data)
