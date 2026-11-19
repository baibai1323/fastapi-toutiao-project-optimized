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


async def is_news_favorite(db: AsyncSession, user_id: int, news_id: int) -> bool:
    stmt = select(Favorite.id).where(
        Favorite.user_id == user_id, Favorite.news_id == news_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def add_news_favorite(db: AsyncSession, user_id: int, news_id: int) -> Favorite:
    favorite = Favorite(user_id=user_id, news_id=news_id)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite


async def remove_news_favorite(db: AsyncSession, user_id: int, news_id: int) -> bool:
    stmt = delete(Favorite).where(
        Favorite.user_id == user_id, Favorite.news_id == news_id
    )
    result = await db.execute(stmt)
    await db.commit()
    return bool(result.rowcount)


async def get_favorite_list(
    db: AsyncSession, user_id: int, page: int, size: int
) -> tuple[list[FavoriteNewsItemResponse], int]:
    total_result = await db.execute(
        select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)
    )
    total = int(total_result.scalar_one())

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
        payload = NewsItemBase.model_validate(news).model_dump()
        payload["favorite_time"] = favorite_time
        payload["favorite_id"] = favorite_id
        items.append(FavoriteNewsItemResponse.model_validate(payload))
    return items, total


async def remove_all_favorites(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(delete(Favorite).where(Favorite.user_id == user_id))
    await db.commit()
    return int(result.rowcount or 0)
