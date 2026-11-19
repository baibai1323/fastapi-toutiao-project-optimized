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
    items, total = await history_crud.get_history_list(db, user.id, page, page_size)
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
    removed = await history_crud.delete_history_by_news(db, user.id, news_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")
    return ok(None, message="已删除")
