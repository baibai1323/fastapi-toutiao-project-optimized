"""新闻条目公共 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import field_serializer

from schemas.common import CamelModel
from utils.time import to_utc_iso


class NewsItemBase(CamelModel):
    id: int
    title: str
    description: Optional[str] = None
    image: Optional[str] = None
    author: Optional[str] = None
    category_id: int
    views: int
    publish_time: Optional[datetime] = None

    @field_serializer("publish_time")
    def serialize_publish_time(self, value: datetime | None) -> str | None:
        # [优化] 数据库存 UTC naive，API 明确输出 ...Z，前端 new Date() 不再差 8 小时。
        return to_utc_iso(value)
