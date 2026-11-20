"""新闻条目公共 Schema。"""

# Schema（模式/契约）：约定“接口返回的新闻长什么样”——有哪些字段、各是什么类型。
# 它和数据库模型是两回事：数据库模型管怎么存，Schema 管对外怎么给。
# 为什么抽成基类：新闻列表、详情、收藏、历史返回的新闻字段几乎一样，
# 继承同一个基类，字段改动只需改这一处。
# CamelModel 见 schemas.common：它会把 Python 里 snake_case 的字段名，
# 自动换成前端习惯的 camelCase（如 category_id → categoryId）。

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import field_serializer

from schemas.common import CamelModel
from utils.time import to_utc_iso


class NewsItemBase(CamelModel):
    # id 是数据库主键，一定存在，所以类型写 int 而不是 Optional[int]
    # （Optional 表示“也可能是 None”，这里不需要）。
    id: int
    # 标题必填：前端列表和详情都要显示它，缺了就没法展示。
    title: str
    # 简介、图片、作者都允许为空：老数据可能没填，
    # 默认值 None 表示“确实没有”，和空字符串 "" 是两种含义。
    description: Optional[str] = None
    image: Optional[str] = None
    author: Optional[str] = None
    # 分类 id 必填：详情页要靠它去找同一分类的相关新闻。
    category_id: int
    # 浏览量：数据库里有默认值 0，读出来一定是个整数，所以不需要 Optional。
    views: int
    # 发布时间允许为空：尚未发布的草稿、或从老系统迁移来的数据可能没有这个时间。
    publish_time: Optional[datetime] = None

    @field_serializer("publish_time")
    def serialize_publish_time(self, value: datetime | None) -> str | None:
        """把 publish_time 字段转成字符串再输出。

        参数：
            value: 字段当前值；可能是 None（没有发布时间）。
        返回：
            带 Z 后缀的 ISO 8601 时间字符串；value 为 None 时原样返回 None。
        """
        # field_serializer 是 Pydantic v2 的装饰器：它只影响“转成 JSON 的那一刻”，
        # 不改变字段在程序内部的类型，所以业务代码里拿到的仍是 datetime。
        # [优化] 数据库存 UTC naive，API 明确输出 ...Z，前端 new Date() 不再差 8 小时。
        return to_utc_iso(value)
