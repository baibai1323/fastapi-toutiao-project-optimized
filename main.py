"""应用入口。

[优化] 原代码：
    app = FastAPI()                       # 没有 title/version/lifespan
    allow_origins=["*"] + allow_credentials=True
    app.include_router(ai_proxy.router, prefix="/api")   # 最终 /api/ai/chat
问题：
    1. OpenAPI 文档没有项目名/版本；
    2. 通配符 CORS + credentials 是无效且危险的组合；
    3. 没有启动/关闭钩子，Redis/DB 连接不会优雅释放；
    4. 没有健康检查、请求日志、请求 ID。
修复：见下。
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from config.cache_conf import close_redis, redis_client
from config.db_conf import AsyncSessionLocal, async_engine
from config.settings import APP_NAME, APP_VERSION, CORS_ORIGINS, DEBUG
from routers import ai_proxy, favorite, history, news, users
from utils.exception_handlers import register_exception_handlers
from utils.logging_conf import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    logger.info("%s %s 启动，DEBUG=%s", APP_NAME, APP_VERSION, DEBUG)
    yield
    logger.info("应用关闭，释放 Redis / 数据库连接")
    await close_redis()
    await async_engine.dispose()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="新闻资讯 API：用户、新闻、收藏、历史、AI 对话。",
    lifespan=lifespan,
)

# CORS 白名单从环境变量读取；只有显式配置 "*" 时才放开 credentials。
allow_all = "*" in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=not allow_all,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms", "X-AI-Mode"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "请求异常 request_id=%s %s %s", request_id, request.method, request.url.path
        )
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    logger.info(
        "%s %s status=%s %.2fms request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


register_exception_handlers(app)

app.include_router(news.router)
app.include_router(users.router)
app.include_router(favorite.router)
app.include_router(history.router)
app.include_router(ai_proxy.router)


@app.get("/", tags=["系统"], summary="服务信息")
async def root():
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["系统"], summary="健康检查")
async def health():
    """数据库/Redis 都正常才返回 200，否则 503，方便容器编排探活。"""
    db_ok = True
    redis_ok = True

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.warning("健康检查：数据库不可用", exc_info=True)
        db_ok = False

    try:
        await redis_client.ping()
    except Exception:
        logger.warning("健康检查：Redis 不可用", exc_info=True)
        redis_ok = False

    healthy = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "database": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
        },
    )
