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
    """记录一次浏览：同一用户同一新闻只保留一条，重复浏览只更新时间。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键。
        news_id: 新闻主键。
    返回：
        该用户这条新闻对应的 History 实体（新建的或更新后的）。
    """
    # upsert 是 update 与 insert 的合成词，意思是“有就更新、没有就插入”。
    # 这里先看数据库方言（dialect = 数据库类型，如 mysql / sqlite）：
    # 生产用 MySQL，可以直接用一条原子 upsert 语句；测试用 SQLite 不支持这个语法，
    # 只能退回“先查、再决定改还是插”的写法。
    now = utcnow()
    dialect = db.bind.dialect.name if db.bind is not None else "mysql"

    if dialect == "mysql":
        # ON DUPLICATE KEY UPDATE：撞到 UNIQUE(user_id, news_id) 时不报错，
        # 直接把 view_time 改成新时间。整件事在一条 SQL 里完成，并发也安全。
        stmt = (
            mysql_insert(History)
            .values(user_id=user_id, news_id=news_id, view_time=now)
            .on_duplicate_key_update(view_time=now)
        )
        await db.execute(stmt)
        await db.commit()
    else:
        # 回退实现（测试用 SQLite 会走到这里）：先查有没有旧记录，
        # 有就只改时间，没有才插入。单线程测试足够用，并发下仍靠唯一约束兜底。
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

    # 再查一次把最终记录读出来返回：MySQL 的 upsert 语句本身不返回行，
    # 而调用方需要 history.id / view_time 去拼响应。
    result = await db.execute(
        select(History).where(History.user_id == user_id, History.news_id == news_id)
    )
    return result.scalar_one()


async def get_history_list(
    db: AsyncSession, user_id: int, page: int, size: int
) -> tuple[list[HistoryNewsItemResponse], int]:
    """分页查询浏览历史，返回 (历史列表, 总条数)。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键，只查这个人的历史。
        page: 页码，从 1 开始。
        size: 每页条数。
    返回：
        (HistoryNewsItemResponse 列表, 总条数)；没浏览过任何新闻时列表为空。
    """
    # 总数和列表必须用同一个 user_id 条件，否则前端算出的总页数会对不上。
    total_result = await db.execute(
        select(func.count()).select_from(History).where(History.user_id == user_id)
    )
    total = int(total_result.scalar_one())

    # 联表取新闻字段，同时把浏览时间、历史主键用 label 起别名带出来。
    # 按浏览时间倒序：最近看过的排最前，符合“历史记录”的使用习惯。
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
        # history_id / view_time 是响应模型的必填字段，ORM 对象里没有这两个属性，
        # 所以先转成新闻字段的 dict，补齐这两个键，再整体交给 Pydantic 校验。
        payload = NewsItemBase.model_validate(news).model_dump()
        payload["view_time"] = view_time
        payload["history_id"] = history_id
        items.append(HistoryNewsItemResponse.model_validate(payload))
    return items, total


async def delete_history_by_news(db: AsyncSession, user_id: int, news_id: int) -> bool:
    """删除某条新闻的浏览记录（历史页的单条删除）。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键，避免删到别人的记录。
        news_id: 新闻主键。
    返回：
        真的删掉一条返回 True；本来就没有这条记录返回 False。
    """
    result = await db.execute(
        delete(History).where(
            History.user_id == user_id, History.news_id == news_id
        )
    )
    await db.commit()
    return bool(result.rowcount)


async def clear_history(db: AsyncSession, user_id: int) -> int:
    """清空某个用户的全部浏览历史。

    参数：
        db: 异步数据库会话。
        user_id: 用户主键。
    返回：
        被删掉的记录条数；本来就没有历史时返回 0。
    """
    # 一定要带 user_id 条件，否则会清空整张表（所有用户的历史）。
    result = await db.execute(delete(History).where(History.user_id == user_id))
    await db.commit()
    return int(result.rowcount or 0)
