"""新闻缓存读写。

[优化] 原代码：
    CATEGORIES_KEY = "news:categories"           # 分类缓存无视 skip/limit
    return [News(**item) for item in cached_list] # 用缓存字典重建 ORM
    if cached_list:                               # 空列表被当成未命中
    if news_list:                                 # 空列表不写缓存
问题：
    1. 分类第一次请求的 skip/limit 被缓存 2 小时，后续分页都拿同一份；
    2. 缓存命中时重建 ORM，对象脱离 Session，字段/别名稍变就 TypeError；
    3. 空列表无法缓存，缓存穿透；
    4. key 没有版本，改结构后旧缓存会污染新代码。
修复：
    - key 加 v2 版本；
    - 只缓存/返回 Pydantic 模型，不重建 ORM；
    - 空列表也缓存（短 TTL）；
    - 分类不再分页，固定一份全量。
"""

from __future__ import annotations

from typing import Optional

from cache.news_cache_schemas import (
    CachedCategory,
    CachedNewsDetail,
    CachedNewsItem,
    CachedRelatedNews,
)
from config.cache_conf import delete_cache, get_json_cache, set_cache

CATEGORIES_KEY = "news:v2:categories"
NEWS_LIST_PREFIX = "news:v2:list:"
NEWS_COUNT_PREFIX = "news:v2:count:"
NEWS_DETAIL_PREFIX = "news:v2:detail:"
RELATED_NEWS_PREFIX = "news:v2:related:"

CATEGORIES_TTL = 7200
LIST_TTL = 1800
EMPTY_LIST_TTL = 120
COUNT_TTL = 300
DETAIL_TTL = 300
RELATED_TTL = 1800


async def get_cached_categories() -> list[CachedCategory] | None:
    data = await get_json_cache(CATEGORIES_KEY)
    if data is None:
        return None
    return [CachedCategory.model_validate(item) for item in data]


async def set_cache_categories(data: list[CachedCategory], expire: int = CATEGORIES_TTL) -> bool:
    payload = [item.model_dump(mode="json", by_alias=True) for item in data]
    return await set_cache(CATEGORIES_KEY, payload, expire)


def _list_key(category_id: Optional[int], page: int, size: int) -> str:
    category_part = category_id if category_id is not None else "all"
    return f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"


async def get_cache_news_list(
    category_id: Optional[int], page: int, size: int
) -> list[CachedNewsItem] | None:
    data = await get_json_cache(_list_key(category_id, page, size))
    if data is None:
        return None
    return [CachedNewsItem.model_validate(item) for item in data]


async def set_cache_news_list(
    category_id: Optional[int],
    page: int,
    size: int,
    news_list: list[CachedNewsItem],
) -> bool:
    payload = [item.model_dump(mode="json", by_alias=True) for item in news_list]
    ttl = LIST_TTL if payload else EMPTY_LIST_TTL
    return await set_cache(_list_key(category_id, page, size), payload, ttl)


async def get_cached_news_count(category_id: Optional[int]) -> int | None:
    category_part = category_id if category_id is not None else "all"
    value = await get_json_cache(f"{NEWS_COUNT_PREFIX}{category_part}")
    return int(value) if value is not None else None


async def set_cached_news_count(category_id: Optional[int], total: int) -> bool:
    category_part = category_id if category_id is not None else "all"
    return await set_cache(f"{NEWS_COUNT_PREFIX}{category_part}", total, COUNT_TTL)


async def get_cached_news_detail(news_id: int) -> CachedNewsDetail | None:
    data = await get_json_cache(f"{NEWS_DETAIL_PREFIX}{news_id}")
    if data is None:
        return None
    return CachedNewsDetail.model_validate(data)


async def cache_news_detail(news_id: int, news_data: CachedNewsDetail) -> bool:
    payload = news_data.model_dump(mode="json", by_alias=True, exclude={"related_news"})
    return await set_cache(f"{NEWS_DETAIL_PREFIX}{news_id}", payload, DETAIL_TTL)


async def invalidate_news_detail(news_id: int) -> None:
    # 浏览量变化后，详情缓存里的 views 会过期；删掉让下次读库。
    await delete_cache(f"{NEWS_DETAIL_PREFIX}{news_id}")


async def cache_related_news(
    news_id: int, category_id: int, related_list: list[CachedRelatedNews]
) -> bool:
    payload = [item.model_dump(mode="json", by_alias=True) for item in related_list]
    return await set_cache(f"{RELATED_NEWS_PREFIX}{news_id}:{category_id}", payload, RELATED_TTL)


async def get_cached_related_news(
    news_id: int, category_id: int
) -> list[CachedRelatedNews] | None:
    data = await get_json_cache(f"{RELATED_NEWS_PREFIX}{news_id}:{category_id}")
    if data is None:
        return None
    return [CachedRelatedNews.model_validate(item) for item in data]
