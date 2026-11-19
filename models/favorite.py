"""收藏 ORM 模型。

[优化] 原代码：
    class Base(DeclarativeBase): ...
    created_at = datetime.utcnow
    Index('fk_favorite_user_idx', 'user_id')   # 被唯一约束的最左列覆盖
问题：
    1. 独立 Base，metadata 分裂；
    2. 时区混用；
    3. user_id 单列索引与 (user_id, news_id) 唯一索引重复；
    4. 外键没有 ondelete="CASCADE"。
修复：
    统一 Base、统一 UTC 时间、外键级联删除，
    并增加 (user_id, created_at) 索引支撑“我的收藏按时间倒序”。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from utils.time import utcnow


class Favorite(Base):
    __tablename__ = "favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="user_news_unique"),
        Index("ix_favorite_user_created", "user_id", "created_at"),
        Index("ix_favorite_news", "news_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="收藏ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, comment="用户ID"
    )
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news.id", ondelete="CASCADE"), nullable=False, comment="新闻ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, comment="收藏时间"
    )

    def __repr__(self) -> str:
        return (
            f"<Favorite(id={self.id}, user_id={self.user_id}, "
            f"news_id={self.news_id}, created_at={self.created_at})>"
        )
