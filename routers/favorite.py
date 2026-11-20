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
    """查询“当前用户是否收藏了这篇新闻”。

    做什么：用 user_id + news_id 去收藏表查一条记录，只回一个布尔值；
        前端据此把按钮渲染成“已收藏 / 未收藏”两种状态。
    参数：
        news_id: 新闻主键，通过查询参数 newsId 传入（前端习惯驼峰命名）。
        user: 当前登录用户，由依赖注入解析 Token 得到。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 是 FavoriteCheckResponse，含 is_favorite 布尔值。
    """
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
    """添加一条收藏。

    做什么：先确认新闻存在（不存在就 404），再写收藏记录。重复收藏交给
        数据库的 UNIQUE(user_id, news_id) 唯一约束兜底，crud 层把它翻译
        成 409；因此这里不做“先查再插”——那种写法在并发下仍会重复。
    参数：
        payload: 收藏请求体，含 news_id。
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，成功时 data 为 None；新闻不存在抛 404，重复收藏抛 409。
    """
    # 先校验新闻是否存在，避免往收藏表里写一条指向不存在新闻的脏数据。
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
    """取消收藏。

    做什么：按 user_id + news_id 删除记录，用返回值判断“到底有没有删到”。
        没删到说明本来就没收藏，回 404 让前端知道状态没有变化。
    参数：
        news_id: 新闻主键，通过查询参数 newsId 传入。
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，成功时 data 为 None；未收藏过则抛 404。
    """
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
    """分页返回当前用户的收藏列表。

    做什么：先按收藏时间倒序取一页，再查满足条件的总数，拼成前端要的结构；
        和新闻列表一样补 has_more，上拉加载时用它判断还有没有下一页。
    参数：
        page: 页码，从 1 开始；ge=1 防止 0/负数算出非法 OFFSET。
        page_size: 每页条数，默认 10，上限 100，避免一次返回过多数据。
        user: 当前登录用户；查询条件里强制带上 user.id，只能看自己的收藏。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 含 list（当前页）、total（总条数）和 has_more。
    """
    items, total = await favorite_crud.get_favorite_list(db, user.id, page, page_size)
    # total 是总条数而不是本页条数，前端用它算总页数；has_more 省一次请求探测。
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
    """清空当前用户的全部收藏。

    做什么：一条 DELETE 删掉该用户的所有收藏记录，并返回删除条数，
        前端据此提示“已清空 N 条”。条件里有 user.id，不会动别人的数据。
    参数：
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 为 None，message 里带实际删除的条数。
    """
    count = await favorite_crud.remove_all_favorites(db, user.id)
    return ok(None, message=f"已清空 {count} 条收藏")
