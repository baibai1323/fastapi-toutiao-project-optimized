"""新闻业务层：Cache-Aside + 数据访问。

[优化] 原代码把缓存逻辑写在 router 和 crud 之间，分类缓存忽略分页，
缓存命中还重建 ORM。这里统一成：
    读缓存 → 未命中读库 → 回填缓存
缓存只存 Pydantic/JSON，不存 ORM 实体。
"""

from __future__ import annotations

# 先解释两个后面反复出现的词：
#   Cache-Aside（旁路缓存）：业务代码自己先查缓存，没有再查数据库，查完回填缓存；
#     数据库仍然是唯一可信来源，缓存只是加速。
#   Pydantic 模型：带类型校验的数据对象，能直接序列化成 JSON 存进 Redis。
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
    """读取全部分类：命中缓存直接返回，未命中才查库并回填缓存。

    参数：
        db: 异步数据库会话，只在缓存未命中时才会用到。
    返回：
        CachedCategory 列表；数据库里没有分类时返回空列表。
    """
    # 这里必须写 `is not None` 而不是 `if cached`：
    # 空列表 [] 也是合法结果，用真值判断会把“确实没有分类”误当成未命中，
    # 于是每次请求都去查库，缓存等于白做。
    cached = await cache_store.get_cached_categories()
    if cached is not None:
        return cached

    categories = await news_crud.get_categories(db)
    # 查库拿到的是 ORM 实体，先转成 Pydantic 模型再写缓存：
    # 缓存里只留纯数据，不会带着和数据库会话绑定的对象。
    data = [CachedCategory.model_validate(item) for item in categories]
    await cache_store.set_cache_categories(data)
    return data


async def get_news_list(
    db: AsyncSession, category_id: Optional[int], page: int, size: int
) -> tuple[list[CachedNewsItem], int]:
    """分页读取新闻列表，返回 (列表, 总数) 二元组。

    参数：
        db: 异步数据库会话。
        category_id: 分类主键；None 表示全部分类。
        page: 页码，从 1 开始。
        size: 每页条数。
    返回：
        (CachedNewsItem 列表, 总条数)；命中缓存时两项都直接从缓存取回。
    """
    # 缓存 key 组合了 category_id/page/size，所以命中时连 count 都不用再查，
    # 一次 Redis 读取就同时拿到列表和总数，这是合并缓存的直接收益。
    cached = await cache_store.get_cache_news_list(category_id, page, size)
    if cached is not None:
        return cached

    items = await news_crud.get_news_list(db, category_id, page, size)
    total = await news_crud.get_news_count(db, category_id)
    # 列表和 total 是两条独立的 SQL，可能落在不同的数据库快照上；
    # 只有把它们写进同一个缓存值，前端看到的“总数”和“列表”才是同一时刻的。
    # 列表与 total 一次写入，避免两者 TTL 不同步导致 total 与列表错位。
    await cache_store.set_cache_news_list(category_id, page, size, items, total)
    return items, total


async def get_detail(db: AsyncSession, news_id: int) -> CachedNewsDetail:
    """读取新闻详情：命中缓存直接返回，未命中查库并回填。

    参数：
        db: 异步数据库会话。
        news_id: 新闻主键。
    返回：
        CachedNewsDetail；数据库里没有这条新闻时抛 404。
    """
    cached = await cache_store.get_cached_news_detail(news_id)
    if cached is not None:
        return cached

    # 缓存层已经把 Redis 异常降级成“未命中”，走到这里就按数据库结果判断存在性：
    # 数据库也没有这条新闻，才是真的 404。
    news = await news_crud.get_news_detail(db, news_id)
    if news is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
    detail = CachedNewsDetail.model_validate(news)
    await cache_store.cache_news_detail(news_id, detail)
    return detail


async def get_related_news(
    db: AsyncSession, news_id: int, category_id: int
) -> list[CachedRelatedNews]:
    """读取相关新闻，命中缓存直接返回，未命中查库并回填。

    参数：
        db: 异步数据库会话，缓存未命中时使用。
        news_id: 当前新闻主键。
        category_id: 当前新闻所属分类。
    返回：
        CachedRelatedNews 列表；同分类没有其它新闻时是空列表（也会被缓存）。
    """
    # 相关新闻允许短暂不一致：半小时内浏览量变化不会立刻反映到推荐里，
    # 用一点新鲜度换响应速度，这类侧栏内容不值得每次实时算。
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
    """组装详情页的最终响应：新闻详情 + 相关新闻。

    参数：
        db: 异步数据库会话。
        news_id: 新闻主键。
    返回：
        NewsDetailResponse，related_news 字段已填好；新闻不存在时抛 404。
    """
    # 必须分两步：先取详情，因为相关新闻要用详情里的 category_id 才能查。
    detail = await get_detail(db, news_id)
    related = await get_related_news(db, news_id, detail.category_id)
    # model_copy 复制一份再替换字段，避免直接改动还留在缓存里的详情对象。
    return detail.model_copy(update={"related_news": related})
