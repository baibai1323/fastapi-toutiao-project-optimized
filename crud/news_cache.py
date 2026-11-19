"""新闻业务层：Cache-Aside + 数据访问。

[优化] 原代码把缓存逻辑写在 router 和 crud 之间，分类缓存忽略分页，
缓存命中还重建 ORM。这里统一成：
    读缓存 → 未命中读库 → 回填缓存
缓存只存 Pydantic/JSON，不存 ORM 实体。
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cache import news_cache as cache_store
from cache.news_cache_schemas import (
    CachedCategory,
    CachedNewsDetail,
    CachedNewsItem,
    CachedRelatedNews,
)
from crud import news as news_crud
from schemas.news import NewsDetailResponse


async def get_categories(db: AsyncSession) -> list[CachedCategory]:
    cached = await cache_store.get_cached_categories()
    if cached is not None:
        return cached

    categories = await news_crud.get_categories(db)
    data = [CachedCategory.model_validate(item) for item in categories]
    await cache_store.set_cache_categories(data)
    return data


async def get_news_list(
    db: AsyncSession, category_id: Optional[int], page: int, size: int
) -> tuple[list[CachedNewsItem], int]:
    cached = await cache_store.get_cache_news_list(category_id, page, size)
    if cached is not None:
        return cached

    items = await news_crud.get_news_list(db, category_id, page, size)
    total = await news_crud.get_news_count(db, category_id)
    # 列表与 total 一次写入，避免两者 TTL 不同步导致 total 与列表错位。
    await cache_store.set_cache_news_list(category_id, page, size, items, total)
    return items, total


async def get_detail(db: AsyncSession, news_id: int) -> CachedNewsDetail:
    cached = await cache_store.get_cached_news_detail(news_id)
    if cached is not None:
        return cached

    news = await news_crud.get_news_detail(db, news_id)
    if news is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
    detail = CachedNewsDetail.model_validate(news)
    await cache_store.cache_news_detail(news_id, detail)
    return detail


async def get_related_news(
    db: AsyncSession, news_id: int, category_id: int
) -> list[CachedRelatedNews]:
    cached = await cache_store.get_cached_related_news(news_id, category_id)
    if cached is not None:
        return cached

    related = await news_crud.get_related_news(db, news_id, category_id)
    await cache_store.cache_related_news(news_id, category_id, related)
    return related


async def record_view(db: AsyncSession, news_id: int) -> int:
    """浏览量 +1 并让详情缓存失效。

    [优化] 原代码 GET 详情里直接写库，而且缓存写在 +1 之前。
    现在写操作独立成 POST /news/{id}/view，GET 保持只读语义。
    """
    views = await news_crud.increase_news_views(db, news_id)
    await cache_store.invalidate_news_detail(news_id)
    return views


async def build_detail_response(db: AsyncSession, news_id: int) -> NewsDetailResponse:
    detail = await get_detail(db, news_id)
    related = await get_related_news(db, news_id, detail.category_id)
    return detail.model_copy(update={"related_news": related})
