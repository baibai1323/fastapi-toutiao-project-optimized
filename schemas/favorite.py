"""收藏 Schema。

[优化] 原代码：
    item = FavoriteNewsItemResponse.model_validate(news)
    item.favorite_id = favorite_id      # 太晚：favorite_id 是必填
    item.favorite_time = favorite_time
问题：model_validate 时直接抛 ValidationError，收藏列表必 500。
修复：一次性构造完整 dict（新闻字段 + favorite_id/favorite_time）再校验。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer

from schemas.base import NewsItemBase
from schemas.common import CamelModel, PageResponse
from utils.time import to_utc_iso


class FavoriteCheckResponse(CamelModel):
    is_favorite: bool


class FavoriteAddRequest(CamelModel):
    news_id: int = Field(..., gt=0)


class FavoriteNewsItemResponse(NewsItemBase):
    favorite_id: int
    favorite_time: datetime

    @field_serializer("favorite_time")
    def serialize_favorite_time(self, value: datetime | None) -> str | None:
        return to_utc_iso(value)


class FavoriteListResponse(PageResponse[FavoriteNewsItemResponse]):
    pass
