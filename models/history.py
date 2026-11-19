"""浏览历史 ORM 模型。

[优化] 原代码：
    UniqueConstraint('user_id', 'news_id', name='uniq_history_user_news')
但 `02-数据库sql文件/database.sql` 的 history 表没有这个唯一索引。
问题：
    声明和真实表结构漂移；`crud/history.py` 只能“先查全部、再循环删重复”，
    并发下仍会插入重复记录，并且全表扫描该用户该新闻的所有行。
修复：
    - 模型与 SQL 迁移都补上 UNIQUE(user_id, news_id)；
    - 增加 (user_id, view_time) 复合索引；
    - 写入改为 MySQL 的 INSERT ... ON DUPLICATE KEY UPDATE（见 crud/history.py）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from utils.time import utcnow


class History(Base):
    __tablename__ = "history"
    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="uniq_history_user_news"),
        Index("ix_history_user_view", "user_id", "view_time"),
        Index("ix_history_news", "news_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="历史ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, comment="用户ID"
    )
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news.id", ondelete="CASCADE"), nullable=False, comment="新闻ID"
    )
    view_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, comment="浏览时间"
    )

    def __repr__(self) -> str:
        return (
            f"<History(id={self.id}, user_id={self.user_id}, "
            f"news_id={self.news_id}, view_time={self.view_time})>"
        )
