"""新闻分类与新闻 ORM 模型。

[优化] 原代码：
    class Base(DeclarativeBase):
        created_at = ...
        updated_at = ...
    __table_args__ = (
        Index('fk_news_category_idx', 'category_id'),
        Index('idx_publish_time', 'publish_time'),
    )
问题：
    1. 所有模型共享同一个“带时间戳的 Base”，语义混乱且 metadata 分裂；
    2. 只有单列索引：`WHERE category_id = ? ORDER BY publish_time` 仍会 filesort；
    3. 分类/新闻的 timestamps 没有 nullable=False，和 SQL 不一致。
修复：
    - 用 TimestampMixin 显式表达；
    - 增加 (category_id, publish_time, id) 复合索引；
    - 相关新闻再加 (category_id, views, publish_time) 复合索引。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin
from utils.time import utcnow


class Category(Base, TimestampMixin):
    __tablename__ = "news_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="分类ID")
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="分类名称")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序")

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name}, sort_order={self.sort_order})>"


class News(Base, TimestampMixin):
    __tablename__ = "news"
    __table_args__ = (
        # 列表页：WHERE category_id = ? ORDER BY publish_time DESC, id DESC
        Index("ix_news_category_publish", "category_id", "publish_time", "id"),
        # 相关新闻：WHERE category_id = ? ORDER BY views DESC, publish_time DESC
        Index("ix_news_category_views", "category_id", "views", "publish_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="新闻ID")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻标题")
    description: Mapped[Optional[str]] = mapped_column(String(500), comment="新闻简介")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="新闻内容")
    image: Mapped[Optional[str]] = mapped_column(String(255), comment="封面图片URL")
    author: Mapped[Optional[str]] = mapped_column(String(50), comment="作者")
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("news_category.id", ondelete="RESTRICT"),
        nullable=False,
        comment="分类ID",
    )
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="浏览量")
    publish_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, comment="发布时间"
    )

    def __repr__(self) -> str:
        return f"<News(id={self.id}, title='{self.title}', views={self.views})>"
