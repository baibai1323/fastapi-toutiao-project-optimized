"""用户与令牌 ORM 模型。

[优化] 原代码：
    class Base(DeclarativeBase): ...
    Index('username_UNIQUE', 'username') + unique=True   # 重复索引
    token = str(uuid.uuid4())                            # 明文 UUID 入库
问题：
    1. 每个模型文件一个 Base，metadata 不统一；
    2. unique=True 已经会建唯一索引，再写 Index 是重复索引；
    3. Token 明文存库，数据库泄露即可冒充用户；
    4. 外键没有 ondelete，和 SQL 里的 CASCADE 不一致。
修复：
    - 统一继承 models.base.Base；
    - 去掉重复索引；
    - 只存 Token 的 SHA-256 摘要，原始 Token 只在登录响应中出现一次；
    - 外键补 ondelete="CASCADE"。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin
from utils.time import utcnow


class User(Base, TimestampMixin):
    """用户信息表。"""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码（加密存储）")
    nickname: Mapped[Optional[str]] = mapped_column(String(50), comment="昵称")
    avatar: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="头像URL",
        default="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg",
    )
    gender: Mapped[Optional[str]] = mapped_column(
        Enum("male", "female", "unknown"), comment="性别", default="unknown"
    )
    bio: Mapped[Optional[str]] = mapped_column(
        String(500), comment="个人简介", default="这个人很懒，什么都没留下"
    )
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, comment="手机号")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', nickname='{self.nickname}')>"


class UserToken(Base):
    """用户令牌表。只保存 Token 的哈希，不保存明文。"""

    __tablename__ = "user_token"
    __table_args__ = (Index("ix_user_token_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="令牌ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, comment="用户ID"
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="令牌哈希")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<UserToken(id={self.id}, user_id={self.user_id})>"
