"""所有 ORM 模型共用的 Base。

[优化] 原代码每个模型文件都各自声明：
    class Base(DeclarativeBase):
        pass
问题：
    users/news/favorite/history 各自维护一份 metadata；
    `Base.metadata.create_all()` 只能看到其中一个文件里的表，
    Alembic autogenerate 也会漏表，relationship 也无法跨 Base 工作。
修复：
    全局唯一 Base，所有模型从 models.base 导入。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from utils.time import utcnow


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False, comment="更新时间"
    )
