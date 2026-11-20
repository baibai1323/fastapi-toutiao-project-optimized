"""新闻数据访问。

[优化] 原代码 `select(News)` 会把 content（TEXT）一起查出来，列表页根本
不用 content；并且排序只依赖单列索引，category_id + publish_time 会 filesort。
这里列表只取需要的列，排序字段与复合索引 `(category_id, publish_time, id)` 对齐。
"""

# `from __future__ import annotations` 让类型注解只作为字符串保存、
# 不在导入时求值，所以下面 `News | None` 这类联合类型写法在低版本 Python 也能用。
# `Optional[int]` 等价于 `int | None`，意思是“可能是整数，也可能是空”。
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.news import Category, News
from schemas.news import NewsItemBase, RelatedNewsResponse


# 下面统一用 SQLAlchemy 2.0 风格的 `select(...)` 拼查询语句，
# 再由 `await db.execute(...)` 真正发给数据库；db 是 AsyncSession（异步会话），
# 一个 HTTP 请求复用一个会话，请求结束后由依赖注入统一关闭。
async def get_categories(db: AsyncSession) -> list[Category]:
    """查询全部分类，按“排序号、主键”升序返回。

    参数：
        db: 异步数据库会话，SQL 都通过它发给数据库。
    返回：
        Category 实体列表；表里没有分类时返回空列表，不会是 None。
    """
    # sort_order 是运营手工调整的展示顺序，再用 id 兜底，
    # 否则两个分类排序号相同时，每次查询的先后顺序可能不一样。
    result = await db.execute(select(Category).order_by(Category.sort_order, Category.id))
    return list(result.scalars().all())


async def get_news_list(
    db: AsyncSession, category_id: Optional[int], page: int, size: int
) -> list[NewsItemBase]:
    """分页查询新闻列表，只取列表页要展示的列（不含正文 content）。

    参数：
        db: 异步数据库会话。
        category_id: 分类主键；传 None 表示“全部分类”，不加分类过滤。
        page: 页码，从 1 开始，和前端用户看到的页码一致。
        size: 每页条数，上限由路由层校验，防止一次拉取过多数据。
    返回：
        NewsItemBase 列表，已按发布时间倒序；页码超出范围时返回空列表。
    """
    # 数据库分页靠 offset + limit：先跳过前面 (page-1) 页的数据，再取 size 条。
    # offset 越大扫描行数越多，所以很深的页码会变慢，这是分页的固有代价。
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
    # 只有前端选了具体分类才加 WHERE，传 None 时保持“全部新闻”的语义。
    if category_id is not None:
        stmt = stmt.where(News.category_id == category_id)
    # 排序字段要和复合索引 (category_id, publish_time, id) 对齐，
    # 这样 MySQL 能顺着索引直接取数据，不用额外做一次 filesort（文件排序）。
    stmt = stmt.order_by(News.publish_time.desc(), News.id.desc()).offset(offset).limit(size)

    # 每行是 SQLAlchemy 的 Row 对象，`_mapping` 把它转成 {列名: 值} 的字典，
    # 再交给 Pydantic 校验成 NewsItemBase，省去手写字段赋值、也避免漏字段。
    rows = (await db.execute(stmt)).all()
    return [NewsItemBase.model_validate(dict(row._mapping)) for row in rows]


async def get_news_count(db: AsyncSession, category_id: Optional[int]) -> int:
    """统计新闻总条数，过滤条件必须和列表查询完全一致。

    参数：
        db: 异步数据库会话。
        category_id: 分类主键；None 表示统计全部新闻。
    返回：
        总条数（int）。分页响应的 total 就用它，
        两边条件不一致会出现“有总数但翻不到数据”的假分页。
    """
    # select(func.count()) 生成 COUNT(*)，select_from(News) 指明统计哪张表。
    stmt = select(func.count()).select_from(News)
    if category_id is not None:
        stmt = stmt.where(News.category_id == category_id)
    result = await db.execute(stmt)
    # COUNT(*) 一定返回一行，所以用 scalar_one() 取那个数字。
    return int(result.scalar_one())


async def get_news_detail(db: AsyncSession, news_id: int) -> News | None:
    """按主键查询一条新闻的完整记录（包含正文 content）。

    参数：
        db: 异步数据库会话。
        news_id: 新闻主键，详情页和“浏览量 +1”都靠它定位。
    返回：
        News 实体；找不到时返回 None，由上层决定抛 404 还是别的处理。
    """
    # 详情页要展示正文，所以这里查完整实体，不像列表那样裁剪列。
    result = await db.execute(select(News).where(News.id == news_id))
    # scalar_one_or_none()：查到一行就返回它，零行返回 None，多行会报错。
    return result.scalar_one_or_none()


async def get_related_news(
    db: AsyncSession, news_id: int, category_id: int, limit: int = 5
) -> list[RelatedNewsResponse]:
    """查询“相关新闻”：同分类下除自己以外、浏览量最高的几条。

    参数：
        db: 异步数据库会话。
        news_id: 当前新闻主键，用来把自己从结果里排除掉。
        category_id: 当前新闻所属分类，相关推荐只在同分类内找。
        limit: 最多返回几条，默认 5 条，详情页侧栏只放得下这么多。
    返回：
        RelatedNewsResponse 列表；同分类没有其它新闻时返回空列表。
    """
    # 排序走 (category_id, views, publish_time) 复合索引：
    # 先按浏览量降序，浏览量相同再按发布时间降序，保证每次结果顺序一致。
    stmt = (
        select(News.id, News.title, News.image, News.views)
        # `!=` 把当前这条新闻自己过滤掉，否则“相关新闻”里会出现自己。
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
    # 用 SQL 里的 views = views + 1 自增，而不是“读到内存 +1 再写回”，
    # 这样并发请求不会互相覆盖：两个请求同时 +1，结果仍然是加 2。
    await db.execute(
        update(News).where(News.id == news_id).values(views=News.views + 1)
    )
    await db.commit()
    # 提交后重新查一次，拿到数据库里的真实数值返回给前端展示。
    result = await db.execute(select(News.views).where(News.id == news_id))
    return int(result.scalar_one_or_none() or 0)
