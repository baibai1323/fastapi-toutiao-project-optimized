"""新闻相关 Schema。

[优化] 原代码：
    列表接口直接返回 ORM 列表 → JSON 是 publish_time / category_id；
    详情接口手写 publishTime；
    schemas/base.py 又把 alias 拼成 publishedTime。
问题：同一个 News 在列表、详情、收藏、历史里字段名不一致。
修复：全部走 CamelModel 自动 snake_case → camelCase，并用 response_model 声明。
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from schemas.base import NewsItemBase
from schemas.common import CamelModel, PageResponse


class CategoryResponse(CamelModel):
    id: int
    name: str
    sort_order: int


class RelatedNewsResponse(CamelModel):
    id: int
    title: str
    image: Optional[str] = None
    views: int


class NewsDetailResponse(NewsItemBase):
    content: str
    # [优化] 用 default_factory，避免可变默认值在实例之间共享。
    related_news: list[RelatedNewsResponse] = Field(default_factory=list)


class NewsListResponse(PageResponse[NewsItemBase]):
    pass


class NewsViewResponse(CamelModel):
    news_id: int
    views: int
