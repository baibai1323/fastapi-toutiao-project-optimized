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

# 全局共享一个异步 Redis 客户端。
# decode_responses=True 让 get() 直接返回 str，省去业务层反复 decode；
# protocol=2 是为了兼容较老的 Redis 版本（RESP3 需要 Redis 6+）。
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    protocol=2,
    socket_connect_timeout=REDIS_TIMEOUT,
    socket_timeout=REDIS_TIMEOUT,
    health_check_interval=30,
)


async def close_redis() -> None:
    """关闭 Redis 连接池，在应用退出时调用。

    关闭失败不影响进程退出，因此这里只记一条 warning，
    不向外抛异常（否则优雅停机会因为 Redis 抖动而失败）。
    """
    try:
        await redis_client.aclose()
    except Exception:  # pragma: no cover - 关闭失败不影响进程退出
        logger.warning("关闭 Redis 连接失败", exc_info=True)


async def get_cache(key: str) -> str | None:
    """读取字符串缓存；Redis 异常或 key 不存在都返回 None。

    刻意不抛异常：调用方拿不到缓存时会自然回退到数据库查询，
    缓存故障不应该变成接口故障。
    """
    try:
        return await redis_client.get(key)
    except Exception:
        logger.warning("读取缓存失败 key=%s", key, exc_info=True)
        return None


async def get_json_cache(key: str) -> Any | None:
    """读取 JSON 缓存并反序列化。

    数据损坏（例如旧版本写入的裸列表结构）会触发 JSONDecodeError，
    同样按“未命中”处理，让调用方重新查库并覆盖旧缓存。
    """
    try:
        data = await redis_client.get(key)
        if data is None:
            return None
        return json.loads(data)
    except Exception:
        logger.warning("读取 JSON 缓存失败 key=%s", key, exc_info=True)
        return None


async def set_cache(key: str, value: Any, expire: int = 3600, *, jitter: bool = True) -> bool:
    """写入缓存，dict/list 会自动序列化成 JSON。

    jitter 会给 TTL 加 ±10% 的随机抖动，避免大量 key 在同一秒集中过期，
    也就是常说的“缓存雪崩”。返回值表示是否写成功，失败只记日志。
    """
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
    """批量删除缓存，返回实际删除的 key 数量。

    列表/详情更新后用它做失效；一个 key 都不传时直接返回 0，
    避免对 Redis 发起无意义的 DEL 命令。
    """
    if not keys:
        return 0
    try:
        return int(await redis_client.delete(*keys))
    except Exception:
        logger.warning("删除缓存失败 keys=%s", keys, exc_info=True)
        return 0


async def incr_with_expire(key: str, window: int) -> int | None:
    """原子自增；第一次自增时设置过期时间。Redis 不可用时返回 None。"""
    # 这是登录限流和 AI 限流的计数器：INCR 是原子操作，
    # 多个请求同时到达也不会把计数算丢；只有 count == 1 时才设置过期，
    # 保证窗口从第一次请求开始计时。
    try:
        count = int(await redis_client.incr(key))
        if count == 1:
            await redis_client.expire(key, window)
        return count
    except Exception:
        logger.warning("Redis 计数失败 key=%s", key, exc_info=True)
        return None
