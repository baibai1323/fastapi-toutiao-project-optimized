"""Redis 连接与基础缓存操作。

[优化] 原代码：
    REDIS_HOST = "localhost"
    redis_client = redis.Redis(host=..., port=..., db=0, protocol=2)
    except Exception as e:
        print(f"获取缓存失败：{e}")

问题：
    1. 地址写死，无法区分环境；
    2. 没有连接/读超时，Redis 挂起时所有请求一起卡住；
    3. 异常只 print，生产没有日志、没有指标；
    4. 固定 TTL，存在同一时刻大量 key 一起过期的风险。
修复：
    - 使用 REDIS_URL，并设置 socket 超时；
    - 异常记录 logger，业务层继续回退数据库；
    - set_cache 增加 ±10% TTL 抖动；
    - 增加 delete/incr 封装，供缓存失效和限流使用。
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

import redis.asyncio as redis

from config.settings import REDIS_TIMEOUT, REDIS_URL

logger = logging.getLogger(__name__)

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    protocol=2,
    socket_connect_timeout=REDIS_TIMEOUT,
    socket_timeout=REDIS_TIMEOUT,
    health_check_interval=30,
)


async def close_redis() -> None:
    try:
        await redis_client.aclose()
    except Exception:  # pragma: no cover - 关闭失败不影响进程退出
        logger.warning("关闭 Redis 连接失败", exc_info=True)


async def get_cache(key: str) -> str | None:
    try:
        return await redis_client.get(key)
    except Exception:
        logger.warning("读取缓存失败 key=%s", key, exc_info=True)
        return None


async def get_json_cache(key: str) -> Any | None:
    try:
        data = await redis_client.get(key)
        if data is None:
            return None
        return json.loads(data)
    except Exception:
        logger.warning("读取 JSON 缓存失败 key=%s", key, exc_info=True)
        return None


async def set_cache(key: str, value: Any, expire: int = 3600, *, jitter: bool = True) -> bool:
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        # 避免同一批 key 在同一秒集中失效，造成缓存雪崩。
        if jitter and expire > 60:
            expire = int(expire * random.uniform(0.9, 1.1))
        await redis_client.set(key, value, ex=expire)
        return True
    except Exception:
        logger.warning("写入缓存失败 key=%s", key, exc_info=True)
        return False


async def delete_cache(*keys: str) -> int:
    if not keys:
        return 0
    try:
        return int(await redis_client.delete(*keys))
    except Exception:
        logger.warning("删除缓存失败 keys=%s", keys, exc_info=True)
        return 0


async def incr_with_expire(key: str, window: int) -> int | None:
    """原子自增；第一次自增时设置过期时间。Redis 不可用时返回 None。"""
    try:
        count = int(await redis_client.incr(key))
        if count == 1:
            await redis_client.expire(key, window)
        return count
    except Exception:
        logger.warning("Redis 计数失败 key=%s", key, exc_info=True)
        return None
