"""基于 Redis 的固定窗口限流。

[优化] 原项目登录和 AI 接口都没有频率限制：
    - 登录可以无限撞库；
    - AI 接口无鉴权，任何人都能刷爆 DashScope 账单。
修复：
    用 Redis INCR + EXPIRE 做固定窗口计数；Redis 不可用时 fail-open，
    保证缓存故障不会让登录/问答整体不可用。
"""

from __future__ import annotations

from config.cache_conf import delete_cache, incr_with_expire


async def hit(key: str, limit: int, window: int) -> bool:
    """计数 +1；未超过限制返回 True。"""
    count = await incr_with_expire(key, window)
    if count is None:
        return True
    return count <= limit


async def reset(key: str) -> None:
    await delete_cache(key)
