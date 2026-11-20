"""浏览历史接口（全部需要登录）。

[优化] 原代码：
    histories = select(...).scalars().all()
    for extra in histories[1:]: await db.delete(extra)
问题：先查全部再循环删重复，并发下仍会重复，且数据库没有唯一约束。
修复：MySQL 原子 upsert；数据库补 UNIQUE(user_id, news_id)。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from crud import history as history_crud
from crud import news as news_crud
from models.users import User
from schemas.common import ApiResponse, ok
from schemas.history import HistoryAddRequest, HistoryListResponse
from utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/history", tags=["历史"])


@router.post(
    "/add",
    response_model=ApiResponse[None],
    summary="记录浏览历史",
)
async def add_history(
    payload: HistoryAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """记录一条浏览历史。

    做什么：先确认新闻存在，再用 MySQL 的原子 upsert（有则更新浏览时间、
        没有则插入）。这样同一用户对同一篇新闻永远只有一行，并发下也不会
        插出重复行——数据库上还有 UNIQUE(user_id, news_id) 兜底。
    参数：
        payload: 请求体，含 news_id。
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，成功时 data 为 None；新闻不存在抛 404。
    """
    # 先校验新闻存在，避免历史表里出现指向已删除新闻的“鬼记录”。
    news = await news_crud.get_news_detail(db, payload.news_id)
    if news is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    await history_crud.add_history(db, user.id, payload.news_id)
    return ok(None, message="已记录")


@router.get(
    "/list",
    response_model=ApiResponse[HistoryListResponse],
    summary="历史列表",
)
async def get_history_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[HistoryListResponse]:
    """分页返回当前用户的浏览历史，最近看过的排前面。

    做什么：查一页记录并取总数，拼成前端要的结构。和新闻/收藏列表一致，
        额外给一个 has_more，前端上拉加载时用它判断还有没有下一页。
    参数：
        page: 页码，从 1 开始；ge=1 拦住 0 和负数，否则会生成负 OFFSET。
        page_size: 每页条数，默认 10，上限 100，防止一次拉回太多数据。
        user: 当前登录用户；查询强制带 user.id，只能看自己的历史。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 含 list（当前页）、total（总条数）和 has_more。
    """
    items, total = await history_crud.get_history_list(db, user.id, page, page_size)
    # total 是总条数（不是本页条数），前端用它算总页数。
    data = HistoryListResponse(
        list=items,
        total=total,
        has_more=page * page_size < total,
    )
    return ok(data)


@router.delete(
    "/clear",
    response_model=ApiResponse[None],
    summary="清空历史",
)
async def clear_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """清空当前用户的全部浏览历史。

    做什么：一条 DELETE 删掉该用户的所有历史记录，返回删除条数供前端提示。
        条件里带 user.id，不会误删别人的历史。
    参数：
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 为 None，message 里带实际删除的条数。
    """
    count = await history_crud.clear_history(db, user.id)
    return ok(None, message=f"已清空 {count} 条历史")


@router.delete(
    "/{news_id}",
    response_model=ApiResponse[None],
    summary="删除单条历史",
)
async def delete_history(
    news_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """删除当前用户的一条浏览历史。

    做什么：按 user_id + news_id 删除单条记录。返回 False 说明这条记录
        不存在（或属于别人），统一回 404，避免泄露“别人有没有看过”。
    参数：
        news_id: 新闻主键，来自路径参数（URL 里的 {news_id}）。
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，成功时 data 为 None；记录不存在则抛 404。
    """
    removed = await history_crud.delete_history_by_news(db, user.id, news_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")
    return ok(None, message="已删除")
