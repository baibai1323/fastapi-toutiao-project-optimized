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
# key 里带版本号（v2、v3）的原因：缓存结构或 key 规则改动后，旧 key 自然读不到，
# 新代码不会被老格式的脏数据坑到，也不用上线时手工去 Redis 里删一遍。
# 列表之所以是 v3：它比其他几种晚一步改成“列表 + total 合并存储”，版本单独升。
NEWS_LIST_PREFIX = "news:v3:list:"
NEWS_DETAIL_PREFIX = "news:v2:detail:"
RELATED_NEWS_PREFIX = "news:v2:related:"

# TTL（Time To Live，存活时间）= 这条缓存最多活多少秒，到期 Redis 自动删除。
# 下面的数字按“数据变化快慢 + 用户能忍多久”来定，不是随手写的：
#   分类 7200 秒（2 小时）：几乎不变，只有运营新增分类才会动；
#   列表 1800 秒（30 分钟）：新闻更新不频繁，半小时延迟可以接受；
#   空列表 120 秒（2 分钟）：见 set_cache_news_list 里的说明；
#   详情 300 秒（5 分钟）：浏览量一直在涨，缓存久了数字明显不准；
#   相关新闻 1800 秒：侧栏推荐对新鲜度不敏感，久一点更省数据库。
CATEGORIES_TTL = 7200
LIST_TTL = 1800
EMPTY_LIST_TTL = 120
DETAIL_TTL = 300
RELATED_TTL = 1800


async def get_cached_categories() -> list[CachedCategory] | None:
    """读取分类缓存。

    参数：
        无（分类是全量固定的一份，不需要分页或过滤参数）。
    返回：
        命中返回 CachedCategory 列表（可能是空列表）；未命中返回 None。
        调用方必须用 `is None` 判断，不能把空列表当成未命中。
    """
    data = await get_json_cache(CATEGORIES_KEY)
    if data is None:
        return None
    return [CachedCategory.model_validate(item) for item in data]


async def set_cache_categories(data: list[CachedCategory], expire: int = CATEGORIES_TTL) -> bool:
    """写入分类缓存。

    参数：
        data: 要缓存的分类列表。
        expire: 存活秒数，默认 2 小时；测试里可以传小值让它尽快过期。
    返回：
        写入成功返回 True；Redis 不可用返回 False（调用方按降级继续走数据库）。
    """
    # 序列化用两个开关：mode 设为 "json" 把 datetime 等类型转成 JSON 能表示的值；
    # by_alias 设为 True 输出前端的 camelCase 字段名，让“读缓存”和“读数据库”两条路
    # 返回的字段名完全一致，前端不用为是否命中缓存写两套解析。
    payload = [item.model_dump(mode="json", by_alias=True) for item in data]
    return await set_cache(CATEGORIES_KEY, payload, expire)


def _list_key(category_id: Optional[int], page: int, size: int) -> str:
    """拼出“某一页新闻列表”的缓存 key。

    参数：
        category_id: 分类主键；None 表示全部分类。
        page: 页码，从 1 开始。
        size: 每页条数。
    返回：
        形如 `news:v3:list:all:1:20` 的字符串；category_id 为 None 时写成 `all`。
    """
    # 用字符串 "all" 代替 None：Redis 的 key 只能是字符串，
    # 而且把“全部分类”和某个真实分类 id 区分开，两者不会互相覆盖。
    category_part = category_id if category_id is not None else "all"
    return f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"


async def get_cache_news_list(
    category_id: Optional[int], page: int, size: int
) -> tuple[list[CachedNewsItem], int] | None:
    """返回 (列表, 总数)。

    总数与列表放在同一个缓存值里：两者必须同生同灭，否则会出现
    “新列表 + 旧 total”的错位（旧实现 list TTL 与 count TTL 不同导致）。
    """
    data = await get_json_cache(_list_key(category_id, page, size))
    if not isinstance(data, dict):
        # 旧版本缓存的是裸列表，结构已变，直接视为未命中。
        return None
    items = [CachedNewsItem.model_validate(item) for item in data.get("items", [])]
    # total 用 0 兜底：老缓存可能没有这个键，缺了也不该让整个请求报错。
    return items, int(data.get("total", 0))


async def set_cache_news_list(
    category_id: Optional[int],
    page: int,
    size: int,
    news_list: list[CachedNewsItem],
    total: int,
) -> bool:
    """把“一页列表 + 该页总数”作为一个整体写入缓存。

    参数：
        category_id: 分类主键；None 表示全部分类。
        page: 页码，从 1 开始。
        size: 每页条数。
        news_list: 这一页的新闻条目。
        total: 满足同样条件的总条数。
    返回：
        写入成功返回 True；Redis 不可用返回 False。
    """
    payload = {
        "items": [item.model_dump(mode="json", by_alias=True) for item in news_list],
        "total": total,
    }
    # 空列表给 120 秒的短 TTL，这是“防缓存穿透”的常用手法：
    # 如果不缓存空结果，用户翻到最后一页之后继续点下一页，每次都会打到数据库；
    # 而空结果又可能是“刚发布了新新闻”造成的，所以只留 2 分钟，不能像正常列表那样留 30 分钟。
    ttl = LIST_TTL if payload["items"] else EMPTY_LIST_TTL
    return await set_cache(_list_key(category_id, page, size), payload, ttl)


async def get_cached_news_detail(news_id: int) -> CachedNewsDetail | None:
    """读取新闻详情缓存。

    参数：
        news_id: 新闻主键。
    返回：
        命中返回 CachedNewsDetail；未命中（或 Redis 出错）返回 None。
    """
    data = await get_json_cache(f"{NEWS_DETAIL_PREFIX}{news_id}")
    if data is None:
        return None
    return CachedNewsDetail.model_validate(data)


async def cache_news_detail(news_id: int, news_data: CachedNewsDetail) -> bool:
    """写入新闻详情缓存。

    参数：
        news_id: 新闻主键，用来拼 key。
        news_data: 详情数据。
    返回：
        写入成功返回 True；Redis 不可用返回 False。
    """
    # 用 exclude 参数排除 related_news 字段：相关新闻有自己独立的 key 和 TTL，
    # 如果塞进详情里存两份，就会出现“详情里的推荐”和“推荐接口”内容打架。
    payload = news_data.model_dump(mode="json", by_alias=True, exclude={"related_news"})
    return await set_cache(f"{NEWS_DETAIL_PREFIX}{news_id}", payload, DETAIL_TTL)


async def invalidate_news_detail(news_id: int) -> None:
    """让某条新闻的详情缓存失效（删掉这一条 key）。

    参数：
        news_id: 新闻主键，对应要删的 key。
    返回：
        没有返回值；Redis 出错时内部只记日志，不向上抛异常。
    """
    # 浏览量变化后，详情缓存里的 views 会过期；删掉让下次读库。
    await delete_cache(f"{NEWS_DETAIL_PREFIX}{news_id}")


async def cache_related_news(
    news_id: int, category_id: int, related_list: list[CachedRelatedNews]
) -> bool:
    """写入相关新闻缓存。

    参数：
        news_id: 当前新闻主键。
        category_id: 分类主键；相关推荐按分类算，所以 key 里必须带上它。
        related_list: 相关新闻列表，空列表也会照样缓存。
    返回：
        写入成功返回 True；Redis 不可用返回 False。
    """
    payload = [item.model_dump(mode="json", by_alias=True) for item in related_list]
    return await set_cache(f"{RELATED_NEWS_PREFIX}{news_id}:{category_id}", payload, RELATED_TTL)


async def get_cached_related_news(
    news_id: int, category_id: int
) -> list[CachedRelatedNews] | None:
    """读取相关新闻缓存。

    参数：
        news_id: 当前新闻主键。
        category_id: 分类主键，必须和写入时一致才能命中。
    返回：
        命中返回 CachedRelatedNews 列表（可能是空列表）；未命中返回 None。
    """
    data = await get_json_cache(f"{RELATED_NEWS_PREFIX}{news_id}:{category_id}")
    if data is None:
        return None
    return [CachedRelatedNews.model_validate(item) for item in data]
