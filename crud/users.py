"""用户与令牌数据库操作。

[优化] 原代码：
    async def create_user(...):
        hashed_password = security.get_hash_password(...)   # 阻塞事件循环
        await db.commit()
        await db.refresh(user)
    async def create_token(...):
        token = str(uuid.uuid4())
        ...
        await db.commit()
    async def update_user(...):
        update(...).values(**user_data.model_dump(...))     # 空 dict → CompileError
    async def change_password(...):
        user.password = ...
        await db.commit()                                   # 不吊销旧 Token
问题：
    1. 注册分两次 commit，第二次失败会留下没有 Token 的用户；
    2. 密码哈希是同步 CPU 操作；
    3. 空更新会让 SQLAlchemy 生成非法 SQL；
    4. 改密码后旧 Token 仍然有效。
修复：
    - create_user/create_token 支持 commit=False，由路由把两步放进同一事务；
    - 哈希放到线程池；
    - 空更新直接 400；
    - 改密码时删除该用户全部 Token；
    - Token 只存 SHA-256，7 天过期可配置。
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import TOKEN_TTL_DAYS
from models.users import User, UserToken
from schemas.users import UserRegisterRequest, UserUpdateRequest
from utils import security
from utils.time import utcnow

# 启动时预生成一次，避免“用户不存在”分支在请求里同步哈希、阻塞事件循环。
_DUMMY_PASSWORD_HASH = security.get_hash_password("not-a-real-password")


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, user_data: UserRegisterRequest, *, commit: bool = True
) -> User:
    hashed_password = await security.hash_password_async(user_data.password)
    user = User(username=user_data.username, password=hashed_password)
    db.add(user)
    await db.flush()
    if commit:
        await db.commit()
        await db.refresh(user)
    return user


async def create_token(db: AsyncSession, user_id: int, *, commit: bool = True) -> str:
    """生成原始 Token 返回给客户端，数据库只保存哈希。

    [优化] 原代码用一个 UUID4 明文 token，并且“查到旧 token 就更新”。
    这里改为每次登录删除该用户旧 token 再插入新 token，语义更清晰：
    单会话登录，旧设备自动失效。
    """
    raw_token = security.generate_token()
    token_hash = security.hash_token(raw_token)
    expires_at = utcnow() + timedelta(days=TOKEN_TTL_DAYS)

    await db.execute(delete(UserToken).where(UserToken.user_id == user_id))
    db.add(UserToken(user_id=user_id, token=token_hash, expires_at=expires_at))
    await db.flush()
    if commit:
        await db.commit()
    return raw_token


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if not user:
        # 仍然执行一次哈希校验，避免“用户不存在”和“密码错误”响应时间差异过大。
        await security.verify_password_async(password, _DUMMY_PASSWORD_HASH)
        return None
    if not await security.verify_password_async(password, user.password):
        return None
    return user


async def get_user_by_token(db: AsyncSession, token: str) -> User | None:
    token_hash = security.hash_token(token)
    stmt = (
        select(User)
        .join(UserToken, UserToken.user_id == User.id)
        .where(UserToken.token == token_hash, UserToken.expires_at > utcnow())
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_token(db: AsyncSession, token: str) -> bool:
    token_hash = security.hash_token(token)
    result = await db.execute(delete(UserToken).where(UserToken.token == token_hash))
    await db.commit()
    return bool(result.rowcount)


async def update_user(
    db: AsyncSession, username: str, user_data: UserUpdateRequest
) -> User | None:
    values = user_data.model_dump(exclude_unset=True, exclude_none=True)
    # [优化] 原代码直接 .values(**{})，SQLAlchemy 会抛 CompileError → 500。
    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有需要更新的字段",
        )

    user = await get_user_by_username(db, username)
    if not user:
        return None
    for field, value in values.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, user: User, old_password: str, new_password: str
) -> bool:
    if not await security.verify_password_async(old_password, user.password):
        return False

    user.password = await security.hash_password_async(new_password)
    db.add(user)
    # 改密码后吊销该用户全部 Token，旧设备立即失效。
    await db.execute(delete(UserToken).where(UserToken.user_id == user.id))
    await db.commit()
    await db.refresh(user)
    return True
