"""统一时间工具。

[优化] 原代码混用 `datetime.utcnow` 与 `datetime.now`：
    favorite.created_at = datetime.utcnow
    history.view_time  = datetime.now
    user.created_at    = datetime.now
问题：
    MySQL TIMESTAMP 会按连接时区转换，收藏时间与浏览时间可能相差 8 小时，
    排序和“刚刚/几分钟前”都会错。
修复：
    数据库统一存 UTC 的 naive datetime（MySQL DATETIME/TIMESTAMP 友好）；
    API 序列化时补上 UTC 时区并输出 ISO8601 的 Z 后缀，前端按本地时区展示。
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """返回 UTC 的 naive datetime，供 MySQL DateTime 列使用。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_iso(value: datetime | None) -> str | None:
    """把数据库里的 naive UTC 时间序列化为带 Z 的 ISO 字符串。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
