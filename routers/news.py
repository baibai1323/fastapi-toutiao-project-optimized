"""新闻接口。

[优化] 原代码问题：
    1. 列表直接返回 ORM，JSON 字段是 publish_time/category_id，前端要 publishTime；
    2. 详情手写 publishTime，列表/详情契约不一致；
    3. GET 详情里顺手 update views，GET 变成非幂等写接口；
    4. page/pageSize 没有下界，page=0 会生成负 OFFSET。
修复：
    - 全部用 response_model 输出 camelCase；
    - 详情只读；
    - 新增 POST /{news_id}/view 显式记录浏览；
    - 分页参数加 ge=1，pageSize 上限 100。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from crud import news_cache
from schemas.common import ApiResponse, ok
from schemas.news import (
    CategoryResponse,
    NewsDetailResponse,
    NewsListResponse,
    NewsViewResponse,
)
from utils.rate_limit import hit

router = APIRouter(prefix="/api/v1/news", tags=["新闻"])


@router.get(
    "/categories",
    response_model=ApiResponse[list[CategoryResponse]],
    summary="新闻分类",
)
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[CategoryResponse]]:
    categories = await news_cache.get_categories(db)
    return ok(categories)


@router.get(
    "/list",
    response_model=ApiResponse[NewsListResponse],
    summary="新闻列表",
)
async def get_news_list(
    category_id: Optional[int] = Query(None, alias="categoryId", gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[NewsListResponse]:
    items, total = await news_cache.get_news_list(db, category_id, page, page_size)
    data = NewsListResponse(
        list=items,
        total=total,
        has_more=page * page_size < total,
    )
    return ok(data)


@router.get(
    "/detail",
    response_model=ApiResponse[NewsDetailResponse],
    summary="新闻详情",
)
async def get_news_detail(
    news_id: int = Query(..., alias="id", gt=0),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[NewsDetailResponse]:
    detail = await news_cache.build_detail_response(db, news_id)
    return ok(detail)


@router.post(
    "/{news_id}/view",
    response_model=ApiResponse[NewsViewResponse],
    summary="记录浏览",
)
async def record_view(
    news_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[NewsViewResponse]:
    client_ip = request.client.host if request.client else "unknown"
    # 匿名接口也要限流，避免被脚本刷浏览量。
    if not await hit(f"rate:view:{client_ip}:{news_id}", 30, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="操作过于频繁",
        )
    views = await news_cache.record_view(db, news_id)
    return ok(NewsViewResponse(news_id=news_id, views=views))
