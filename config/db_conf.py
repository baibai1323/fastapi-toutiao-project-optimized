"""数据库连接与会话管理。

[优化] 原代码：
    echo=True
    pool_size=10, max_overflow=20
    async def get_db():
        yield session
        await session.commit()      # 每个请求自动提交
        # except: rollback

问题：
    1. echo=True 在生产会把每条 SQL 和参数打进日志，泄露数据且拖慢性能；
    2. 没有 pool_pre_ping / pool_recycle，MySQL 8 小时断开后会出现
       “MySQL server has gone away”；
    3. get_db 统一 commit 会掩盖事务边界：注册接口先 commit 用户、再 commit token，
       第二步失败会留下“没有 token 的用户”；
    4. CRUD 里又各自 commit，事务边界完全不可控。
修复：
    - echo 由 SQL_ECHO 控制；
    - 增加 pool_pre_ping / pool_recycle；
    - get_db 只负责 rollback/close，不再自动 commit；
    - 每个写操作在 CRUD/路由中显式 commit，组合操作放在同一事务里。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import (
    DATABASE_URL,
    DB_MAX_OVERFLOW,
    DB_POOL_RECYCLE,
    DB_POOL_SIZE,
    SQL_ECHO,
)

if not DATABASE_URL:
    raise ValueError("未找到 DATABASE_URL 环境变量，请参考 env.example 配置")

# SQLite 主要用于本地测试：它不支持 pool_size/max_overflow 这组 QueuePool 参数。
_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {
    "echo": SQL_ECHO,
    "pool_pre_ping": True,
}
if not _is_sqlite:
    _engine_kwargs.update(
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_recycle=DB_POOL_RECYCLE,
        # [优化] 统一连接时区为 UTC。否则 MySQL TIMESTAMP 会按服务器本地时区
        # 转换一次，Python 再按 UTC 序列化，前端就会差 8 小时。
        connect_args={"init_command": "SET time_zone = '+00:00'"},
    )

async_engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db():
    """请求级 Session：只负责回滚和关闭，提交由业务代码显式控制。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
