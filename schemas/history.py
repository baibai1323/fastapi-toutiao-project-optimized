"""浏览历史 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer

from schemas.base import NewsItemBase
from schemas.common import CamelModel, PageResponse
from utils.time import to_utc_iso


class HistoryAddRequest(CamelModel):
    news_id: int = Field(..., gt=0)


class HistoryNewsItemResponse(NewsItemBase):
    history_id: int
    view_time: datetime

    @field_serializer("view_time")
    def serialize_view_time(self, value: datetime | None) -> str | None:
        return to_utc_iso(value)


class HistoryListResponse(PageResponse[HistoryNewsItemResponse]):
    pass
