"""收藏数据访问。

[优化] 原代码收藏列表：
    item = FavoriteNewsItemResponse.model_validate(news)
    item.favorite_id = favorite_id
    item.favorite_time = favorite_time
`favorite_id/favorite_time` 在 Schema 里是必填，validate 的瞬间就 500 了。
这里改成一次性构造完整 dict，再交给 Pydantic 校验。
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.favorite import Favorite
from models.news import News
from schemas.favorite import FavoriteNewsItemResponse
from schemas.base import NewsItemBase

# 读代码前先认识两个词：
#   收藏（favorite）= 用户把某条新闻加进“我的收藏”，一条记录就是一对 (user_id, news_id)。
#   联表（JOIN）= 一条 SQL 同时读两张表，这里靠 news_id 把收藏记录和新闻内容拼在一起。
# 收藏表本身不存新闻标题，只存外键：新闻改了标题，收藏列表跟着变，不会出现旧标题。


async def is_news_favorite(db: AsyncSession, user_id: int, news_id: int) -> bool:
    """判断某个用户有没有收藏过某条新闻。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键。
        news_id: 新闻主键。
    返回：
        收藏过返回 True，没收藏过返回 False。
    """
    # 只 select 主键 id，不把整行 Favorite 查出来：这里只关心“有没有”，
    # 少读几列能让这个高频调用的查询更轻。
    stmt = select(Favorite.id).where(
        Favorite.user_id == user_id, Favorite.news_id == news_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def add_news_favorite(db: AsyncSession, user_id: int, news_id: int) -> Favorite:
    """新增一条收藏记录。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键。
        news_id: 新闻主键。
    返回：
        刚插入的 Favorite 实体，`id` 和 `created_at` 已由数据库填好。
    """
    # 这里不做“先查再插”，而是直接 INSERT：
    # 收藏表有 UNIQUE(user_id, news_id) 约束，重复收藏会抛 IntegrityError，
    # 由全局异常处理器翻译成 409“已经收藏过这篇新闻”。
    # 先查后插在并发下反而会两个请求同时查到“没有”，然后都插入，还是靠约束兜底。
    favorite = Favorite(user_id=user_id, news_id=news_id)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite


async def remove_news_favorite(db: AsyncSession, user_id: int, news_id: int) -> bool:
    """取消收藏：按 (用户, 新闻) 删除收藏记录。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键。
        news_id: 新闻主键。
    返回：
        真的删掉一行返回 True；本来就没收藏返回 False
        （调用方可以据此返回“未收藏”，但重复取消也不算错误）。
    """
    stmt = delete(Favorite).where(
        Favorite.user_id == user_id, Favorite.news_id == news_id
    )
    result = await db.execute(stmt)
    await db.commit()
    # rowcount 是这条 DELETE 实际影响的行数，0 表示没有匹配记录。
    return bool(result.rowcount)


async def get_favorite_list(
    db: AsyncSession, user_id: int, page: int, size: int
) -> tuple[list[FavoriteNewsItemResponse], int]:
    """分页查询“我的收藏”，返回 (收藏列表, 总条数)。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键，只查这个人的收藏。
        page: 页码，从 1 开始。
        size: 每页条数。
    返回：
        (FavoriteNewsItemResponse 列表, 总条数)；没有收藏时列表是空的。
    """
    # 先查总数：前端要用它算总页数，必须和下面列表用同一个 user_id 条件。
    total_result = await db.execute(
        select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)
    )
    total = int(total_result.scalar_one())

    # 联表查新闻内容，同时用 label 给收藏表的两列起别名：
    # 这样结果行里能同时拿到“新闻字段”和“收藏时间/收藏 id”，一次查询搞定。
    # 排序按收藏时间倒序，最近收藏的排最前面。
    stmt = (
        select(
            News,
            Favorite.created_at.label("favorite_time"),
            Favorite.id.label("favorite_id"),
        )
        .join(Favorite, Favorite.news_id == News.id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await db.execute(stmt)).all()

    items: list[FavoriteNewsItemResponse] = []
    for news, favorite_time, favorite_id in rows:
        # 不能直接 model_validate(news)：favorite_id / favorite_time 是响应模型的
        # 必填字段，直接校验 ORM 对象会立刻报校验错误（原代码在这里 500）。
        # 正确做法是先用新闻字段拼出基础 dict，再补上收藏相关字段，最后整体校验。
        payload = NewsItemBase.model_validate(news).model_dump()
        payload["favorite_time"] = favorite_time
        payload["favorite_id"] = favorite_id
        items.append(FavoriteNewsItemResponse.model_validate(payload))
    return items, total


async def remove_all_favorites(db: AsyncSession, user_id: int) -> int:
    """清空某个用户的全部收藏。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键。
    返回：
        被删掉的收藏条数；本来就没有收藏时返回 0。
    """
    result = await db.execute(delete(Favorite).where(Favorite.user_id == user_id))
    await db.commit()
    return int(result.rowcount or 0)
