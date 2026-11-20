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
    """新闻分类，用于「分类」页顶部的标签列表。"""

    id: int
    name: str
    # 数字越小越靠前，前端按这个字段排序，不需要再自己排。
    sort_order: int


class RelatedNewsResponse(CamelModel):
    """详情页底部的「相关推荐」，只带展示需要的字段。

    这里不复用完整的 NewsItemBase：推荐位只显示标题和小图，
    字段越少，一次查多条时的响应体越小。
    """

    id: int
    title: str
    image: Optional[str] = None
    views: int


class NewsDetailResponse(NewsItemBase):
    """新闻详情：在列表字段的基础上多了正文和相关推荐。"""

    content: str
    # [优化] 用 default_factory，避免可变默认值在实例之间共享。
    related_news: list[RelatedNewsResponse] = Field(default_factory=list)


class NewsListResponse(PageResponse[NewsItemBase]):
    """新闻列表的统一分页结构：list + total + hasMore。

    total 和 list 由同一次查询产生，避免两者来自不同缓存而互相矛盾。
    """

    pass


class NewsViewResponse(CamelModel):
    """浏览数上报接口的返回值，告诉前端当前最新的浏览量。"""

    news_id: int
    views: int
