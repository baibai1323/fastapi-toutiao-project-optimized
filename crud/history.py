"""浏览历史数据访问。

[优化] 原代码：
    result = await db.execute(select(History).where(user_id, news_id))
    histories = result.scalars().all()
    if histories:
        for extra in histories[1:]:
            await db.delete(extra)          # 先查全部、再循环删重复
        history = histories[0]
        history.view_time = ...
问题：
    1. 数据库根本没有 (user_id, news_id) 唯一约束，并发请求会插出重复行；
    2. 先查后删是应用层去重，两个请求同时到达仍然会重复；
    3. 每次都要把该用户该新闻的所有行读出来。
修复：
    - SQL 迁移补 UNIQUE(user_id, news_id)；
    - MySQL 用 INSERT ... ON DUPLICATE KEY UPDATE，一条语句原子 upsert；
    - SQLite（测试）用 select → update/insert 的回退实现。
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import History
from models.news import News
from schemas.base import NewsItemBase
from schemas.history import HistoryNewsItemResponse
from utils.time import utcnow


async def add_history(db: AsyncSession, user_id: int, news_id: int) -> History:
    now = utcnow()
    dialect = db.bind.dialect.name if db.bind is not None else "mysql"

    if dialect == "mysql":
        stmt = (
            mysql_insert(History)
            .values(user_id=user_id, news_id=news_id, view_time=now)
            .on_duplicate_key_update(view_time=now)
        )
        await db.execute(stmt)
        await db.commit()
    else:
        existing = await db.execute(
            select(History).where(
                History.user_id == user_id, History.news_id == news_id
            )
        )
        history = existing.scalar_one_or_none()
        if history is not None:
            history.view_time = now
        else:
            db.add(History(user_id=user_id, news_id=news_id, view_time=now))
        await db.commit()

    result = await db.execute(
        select(History).where(History.user_id == user_id, History.news_id == news_id)
    )
    return result.scalar_one()


async def get_history_list(
    db: AsyncSession, user_id: int, page: int, size: int
) -> tuple[list[HistoryNewsItemResponse], int]:
    total_result = await db.execute(
        select(func.count()).select_from(History).where(History.user_id == user_id)
    )
    total = int(total_result.scalar_one())

    stmt = (
        select(
            News,
            History.view_time.label("view_time"),
            History.id.label("history_id"),
        )
        .join(History, History.news_id == News.id)
        .where(History.user_id == user_id)
        .order_by(History.view_time.desc(), History.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await db.execute(stmt)).all()

    items: list[HistoryNewsItemResponse] = []
    for news, view_time, history_id in rows:
        payload = NewsItemBase.model_validate(news).model_dump()
        payload["view_time"] = view_time
        payload["history_id"] = history_id
        items.append(HistoryNewsItemResponse.model_validate(payload))
    return items, total


async def delete_history_by_news(db: AsyncSession, user_id: int, news_id: int) -> bool:
    result = await db.execute(
        delete(History).where(
            History.user_id == user_id, History.news_id == news_id
        )
    )
    await db.commit()
    return bool(result.rowcount)


async def clear_history(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(delete(History).where(History.user_id == user_id))
    await db.commit()
    return int(result.rowcount or 0)
