"""收藏接口（全部需要登录）。

[优化] 原代码：
    FavoriteNewsItemResponse.model_validate(news)  # 缺 favorite_id/time，直接 500
问题：必填字段在 validate 之后才赋值。
修复：crud 层一次性构造完整 dict；重复收藏交给唯一约束 + 异常映射返回 409。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from crud import favorite as favorite_crud
from crud import news as news_crud
from models.users import User
from schemas.common import ApiResponse, ok
from schemas.favorite import (
    FavoriteAddRequest,
    FavoriteCheckResponse,
    FavoriteListResponse,
)
from utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/favorite", tags=["收藏"])


@router.get(
    "/check",
    response_model=ApiResponse[FavoriteCheckResponse],
    summary="是否已收藏",
)
async def check_favorite(
    news_id: int = Query(..., alias="newsId", gt=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FavoriteCheckResponse]:
    is_favorite = await favorite_crud.is_news_favorite(db, user.id, news_id)
    return ok(FavoriteCheckResponse(is_favorite=is_favorite))


@router.post(
    "/add",
    response_model=ApiResponse[None],
    summary="添加收藏",
)
async def add_favorite(
    payload: FavoriteAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    news = await news_crud.get_news_detail(db, payload.news_id)
    if news is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    await favorite_crud.add_news_favorite(db, user.id, payload.news_id)
    return ok(None, message="收藏成功")


@router.delete(
    "/remove",
    response_model=ApiResponse[None],
    summary="取消收藏",
)
async def remove_favorite(
    news_id: int = Query(..., alias="newsId", gt=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    removed = await favorite_crud.remove_news_favorite(db, user.id, news_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚未收藏该新闻")
    return ok(None, message="已取消收藏")


@router.get(
    "/list",
    response_model=ApiResponse[FavoriteListResponse],
    summary="收藏列表",
)
async def get_favorite_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FavoriteListResponse]:
    items, total = await favorite_crud.get_favorite_list(db, user.id, page, page_size)
    data = FavoriteListResponse(
        list=items,
        total=total,
        has_more=page * page_size < total,
    )
    return ok(data)


@router.delete(
    "/clear",
    response_model=ApiResponse[None],
    summary="清空收藏",
)
async def clear_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    count = await favorite_crud.remove_all_favorites(db, user.id)
    return ok(None, message=f"已清空 {count} 条收藏")
