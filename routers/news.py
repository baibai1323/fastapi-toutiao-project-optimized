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

# 所有接口都用 response_model 声明出参结构：FastAPI 会据此把 ORM 对象
# 转成 camelCase 字段（如 publish_time -> publishTime），列表与详情格式统一，
# 前端不需要为两个接口写两套解析逻辑。
router = APIRouter(prefix="/api/v1/news", tags=["新闻"])


@router.get(
    "/categories",
    response_model=ApiResponse[list[CategoryResponse]],
    summary="新闻分类",
)
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[CategoryResponse]]:
    """返回全部新闻分类，供前端下拉框/导航使用。

    做什么：直接委托给 news_cache.get_categories。分类数据几乎不变，
        这一层带 Redis 缓存，命中缓存时连数据库都不会查。
    参数：
        db: 异步数据库会话，由 get_db 依赖注入；只有缓存未命中时才用到。
    返回：
        ApiResponse，data 是分类数组，每项含分类 ID 与名称。
    """
    # Redis 是内存键值数据库，读写远快于 MySQL；这里由 cache 层决定是否回源。
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
    """分页返回新闻列表，可按分类筛选。

    做什么：把筛选与分页参数交给 news_cache 查询（内部带缓存），再补一个
        has_more 字段，告诉前端“下一页还有没有数据”。
    参数：
        category_id: 分类 ID，可选；传了就只看该分类，必须大于 0。
        page: 页码，从 1 开始；用 ge=1 拦住 0 和负数，否则会算出负 OFFSET。
        page_size: 每页条数，默认 10，上限 100，避免一次把大量数据读进内存。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 含 list（当前页）、total（总条数）和 has_more。
    """
    items, total = await news_cache.get_news_list(db, category_id, page, page_size)
    # total 是“符合筛选条件的总条数”，不是本页条数；前端靠它算总页数。
    # has_more 用 page*page_size 与 total 比较得出，省一次额外的 count 查询。
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
    """按 ID 查询新闻详情，是只读接口。

    做什么：委托 news_cache.build_detail_response 组装详情（含分类名等
        展示字段）；查不到时由下层抛出 404，不在路由层重复判断。
    参数：
        news_id: 新闻主键，通过查询参数 id 传入，必须大于 0。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 是新闻详情对象，字段为 camelCase。
    """
    # GET 必须是幂等的：以前这里顺手把浏览量 +1，导致每刷新一次就写一次库，
    # 爬虫/预取也会虚增数据。现在浏览量改由 POST /{news_id}/view 显式记录。
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
    """记录一次浏览，并把最新浏览量返回给前端。

    做什么：先按“客户端 IP + 新闻 ID”限流，挡住脚本刷量；通过后再让
        news_cache 原子地给 views 加一，避免并发下读改写丢失计数。
    参数：
        news_id: 新闻主键，来自路径参数（URL 里的 {news_id}）。
        request: 请求对象，用来取客户端 IP 作为限流维度。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 含 news_id 与自增后的 views。
    """
    # request.client 在单元测试里可能为 None，故兜底成 "unknown"。
    client_ip = request.client.host if request.client else "unknown"
    # 匿名接口也要限流，避免被脚本刷浏览量。
    # 具体规则：同一个 IP 对同一篇新闻 60 秒内最多计 30 次；
    # 只限流不鉴权，是因为浏览行为本来就允许未登录用户发生。
    if not await hit(f"rate:view:{client_ip}:{news_id}", 30, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="操作过于频繁",
        )
    views = await news_cache.record_view(db, news_id)
    return ok(NewsViewResponse(news_id=news_id, views=views))
