"""浏览历史 Schema。"""

# 浏览历史记录“谁在什么时候看过哪条新闻”，和收藏的区别是：
# 收藏是用户主动点的，历史是打开详情页就自动记的，允许重复（同一条可以看很多次）。
# 这里只描述对外的数据形状，不涉及数据库怎么写。

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer

from schemas.base import NewsItemBase
from schemas.common import CamelModel, PageResponse
from utils.time import to_utc_iso


class HistoryAddRequest(CamelModel):
    """新增一条浏览记录时的请求体。

    请求体（request body）：前端 POST 过来的 JSON，Pydantic 会按这里的字段校验。
    """

    # Field(...) 里的三个点表示“必填，没有默认值”；
    # 这里的 gt 是 greater than 的缩写，0 是下界，意思是“必须大于 0”——
    # 数据库主键从 1 开始，传 0 或负数一定是前端算错了，这里提前拦掉，别等查库才发现。
    news_id: int = Field(..., gt=0)


class HistoryNewsItemResponse(NewsItemBase):
    """历史列表里的一条：新闻字段 + 这条浏览记录自己的信息。

    继承 NewsItemBase，所以新闻的标题、简介、浏览量等字段都自动带了；
    这里只补两个“属于浏览记录而非新闻”的字段。
    """

    # history_id 是“浏览记录表”的主键，不是新闻主键；
    # 前端要用它去删某一条历史，所以必须单独返回。
    history_id: int
    # view_time 是这条记录被写入的时间（数据库里存 UTC，输出时转成带 Z 的字符串）。
    view_time: datetime

    @field_serializer("view_time")
    def serialize_view_time(self, value: datetime | None) -> str | None:
        """把 view_time 字段转成字符串再输出。

        参数：
            value: 字段当前值；理论上历史记录一定有浏览时间，但类型上仍允许 None。
        返回：
            带 Z 后缀的 ISO 8601 时间字符串；value 为 None 时返回 None。
        """
        # 和 NewsItemBase 里的处理保持一致：统一成 UTC + Z，
        # 前端 new Date() 能直接解析出正确时区，不会莫名差 8 小时。
        return to_utc_iso(value)


class HistoryListResponse(PageResponse[HistoryNewsItemResponse]):
    # 这个类是“历史列表的分页返回”。
    # PageResponse 是 schemas.common 里的泛型（generic）分页壳，
    # 里面固定有 list、total、has_more 三个字段；方括号里指定“列表元素是什么类型”，
    # 这样每个元素都会按 HistoryNewsItemResponse 校验并序列化。
    # 下面这句 pass 是 Python 的空语句：类体里必须有内容，这里不再加字段，就写 pass。
    pass
