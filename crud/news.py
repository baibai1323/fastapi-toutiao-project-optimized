"""新闻数据访问。

[优化] 原代码 `select(News)` 会把 content（TEXT）一起查出来，列表页根本
不用 content；并且排序只依赖单列索引，category_id + publish_time 会 filesort。
这里列表只取需要的列，排序字段与复合索引 `(category_id, publish_time, id)` 对齐。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.news import Category, News
from schemas.news import NewsItemBase, RelatedNewsResponse


async def get_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(select(Category).order_by(Category.sort_order, Category.id))
    return list(result.scalars().all())


async def get_news_list(
    db: AsyncSession, category_id: Optional[int], page: int, size: int
) -> list[NewsItemBase]:
    offset = (page - 1) * size
    # [优化] 不查 content，避免把大文本带进列表响应和内存。
    stmt = select(
        News.id,
        News.title,
        News.description,
        News.image,
        News.author,
        News.category_id,
        News.views,
        News.publish_time,
    )
    if category_id is not None:
        stmt = stmt.where(News.category_id == category_id)
    stmt = stmt.order_by(News.publish_time.desc(), News.id.desc()).offset(offset).limit(size)

    rows = (await db.execute(stmt)).all()
    return [NewsItemBase.model_validate(dict(row._mapping)) for row in rows]


async def get_news_count(db: AsyncSession, category_id: Optional[int]) -> int:
    stmt = select(func.count()).select_from(News)
    if category_id is not None:
        stmt = stmt.where(News.category_id == category_id)
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def get_news_detail(db: AsyncSession, news_id: int) -> News | None:
    result = await db.execute(select(News).where(News.id == news_id))
    return result.scalar_one_or_none()


async def get_related_news(
    db: AsyncSession, news_id: int, category_id: int, limit: int = 5
) -> list[RelatedNewsResponse]:
    stmt = (
        select(News.id, News.title, News.image, News.views)
        .where(News.category_id == category_id, News.id != news_id)
        .order_by(News.views.desc(), News.publish_time.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [RelatedNewsResponse.model_validate(dict(row._mapping)) for row in rows]


async def increase_news_views(db: AsyncSession, news_id: int) -> int:
    """浏览量 +1，返回最新值。

    [优化] 原代码先查详情、再 update +1，但缓存写在 +1 之前，
    用户刷新看到的还是旧值。这里更新后重新读一次，由服务层刷新缓存。
    """
    await db.execute(
        update(News).where(News.id == news_id).values(views=News.views + 1)
    )
    await db.commit()
    result = await db.execute(select(News.views).where(News.id == news_id))
    return int(result.scalar_one_or_none() or 0)
