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

# 每个模块用 __name__ 建自己的 logger（名字形如 "main"），这样日志里能看出
# 是哪个文件打的，也方便按模块单独调级别。
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期钩子：启动时初始化日志，关闭时释放外部连接。

    做什么：FastAPI 在开始接收请求之前执行 yield 之前的代码，在进程退出时
        执行 yield 之后的代码。这里先配置日志（保证后面所有日志格式统一），
        再在退出阶段关闭 Redis 与数据库连接池，避免连接泄漏。
    参数：
        _: FastAPI 应用实例。本函数用不到它，按 Python 惯例用下划线表示
            “这个参数是必需的，但我有意不使用”。
    返回：
        异步上下文管理器；进入时是启动逻辑，退出时是关闭逻辑。
    """
    setup_logging()
    logger.info("%s %s 启动，DEBUG=%s", APP_NAME, APP_VERSION, DEBUG)
    yield
    logger.info("应用关闭，释放 Redis / 数据库连接")
    await close_redis()
    await async_engine.dispose()


# FastAPI 实例是整个应用的“总入口”：title/version 会显示在 /docs 文档页，
# lifespan 绑定上面的启动/关闭钩子。把这些元信息集中在这里，OpenAPI 文档
# 才不会显示默认的 "FastAPI" 占位标题。
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="新闻资讯 API：用户、新闻、收藏、历史、AI 对话。",
    lifespan=lifespan,
)

# CORS（跨域资源共享）：浏览器默认禁止页面脚本读取“别的域名/端口”的响应。
# 前端跑在 5173、后端在 8000，端口不同就算跨域，必须由后端显式放行，
# 否则请求可能已经到达后端并被处理，但浏览器仍然把响应拦下来。
# 注意规范禁止“来源写 * 又允许携带 Cookie”的组合，所以下面用 allow_all
# 判断：只有显式配置 "*" 时才关闭 credentials，两者不会同时开启。
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
# GZip 中间件：响应体超过 1024 字节（1KB）才压缩。小响应压缩后可能反而更大，
# 所以留一个阈值；对新闻列表这类大 JSON 能明显省带宽。
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """给每个请求生成/透传追踪 ID，并记录访问日志与耗时。

    做什么：优先复用网关或前端传来的 X-Request-ID（同一次用户操作可能经过
        多个服务，靠这个 ID 把日志串起来），没有就用 UUID 现场生成一个。
        随后把 ID 挂到 request.state 上供业务代码读取，等响应回来再写回
        响应头并输出一行“方法/路径/状态码/耗时”的日志。
    参数：
        request: 本次 HTTP 请求对象，可以读请求头、URL、客户端地址。
        call_next: FastAPI 提供的“继续执行后续处理”的可调用对象，调用它
            才会真正进入路由函数。
    返回：
        Response 对象；如果后续处理抛异常，先记一条带堆栈的错误日志，
        再把异常原样抛出，交给统一异常处理去变成 JSON 响应。
    """
    # UUID（通用唯一识别码）是一串几乎不可能重复的随机十六进制字符；
    # 这里用 hex 形式，方便放进 URL/日志。
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    # perf_counter 是单调时钟，不受系统时间被校准的影响，适合量耗时。
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "请求异常 request_id=%s %s %s", request_id, request.method, request.url.path
        )
        raise

    # 乘以 1000 把“秒”换算成“毫秒”，保留两位小数便于人看。
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


# 统一异常处理：把业务异常、参数校验失败等转成统一的 JSON 结构，
# 避免前端直接看到 500 堆栈页。注册必须在挂载路由之前完成。
register_exception_handlers(app)

# 各业务路由的 prefix/tags 在各自模块里声明，这里只负责按顺序挂到总应用上。
app.include_router(news.router)
app.include_router(users.router)
app.include_router(favorite.router)
app.include_router(history.router)
app.include_router(ai_proxy.router)


@app.get("/", tags=["系统"], summary="服务信息")
async def root():
    """返回服务名、版本与常用入口地址，方便部署后快速确认“跑的是哪个版本”。

    做什么：只回显配置里的静态信息，不访问数据库和 Redis，因此任何依赖
        故障时也能秒回。
    参数：
        无。这是一个无参路由，FastAPI 会把它注册成 GET /。
    返回：
        dict，包含 name/version 以及文档地址 docs 和健康检查地址 health。
    """
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["系统"], summary="健康检查")
async def health():
    """数据库/Redis 都正常才返回 200，否则 503，方便容器编排探活。"""
    # 做什么：分别探测数据库和 Redis，只有两个依赖都通才算健康。
    # 参数：无。
    # 返回：JSONResponse，status=200 表示健康，503 表示降级（degraded）。
    db_ok = True
    redis_ok = True

    try:
        async with AsyncSessionLocal() as session:
            # SELECT 1 是最轻量的连通性探测：不碰业务表，只验证连接能用。
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.warning("健康检查：数据库不可用", exc_info=True)
        db_ok = False

    try:
        # ping 只做一次往返，确认 Redis 还能响应；断连或超时会抛异常。
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
