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

# pbkdf2_sha256 是一种“故意算得很慢”的密码哈希算法：内部要迭代很多轮，
# 慢是为了让暴力猜密码的成本变高；代价是单次计算很吃 CPU，
# 所以放到异步线程池里执行，绝不能直接写在 async 函数里。
# 启动时预生成一次，避免“用户不存在”分支在请求里同步哈希、阻塞事件循环。
_DUMMY_PASSWORD_HASH = security.get_hash_password("not-a-real-password")


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """按用户名查用户，登录和注册查重都走这里。

    参数：
        db: 异步数据库会话。
        username: 登录名，数据库里有唯一约束。
    返回：
        User 实体；用户名不存在时返回 None。
    """
    # username 上有唯一索引，所以这里最多返回一行，用 scalar_one_or_none 刚好。
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, user_data: UserRegisterRequest, *, commit: bool = True
) -> User:
    """创建用户，并把明文密码换成哈希后入库。

    参数：
        db: 异步数据库会话。
        user_data: 注册请求体，含用户名和明文密码。
        commit: 是否立刻提交事务；注册流程要“建用户 + 发 Token”一起成功，
            所以路由会传 False，把两步放进同一个事务。
    返回：
        User 实体，`id` 已由数据库自增赋值。
    """
    # 用 async 版本把哈希丢到线程池：pbkdf2 要算几十万轮，直接同步执行
    # 会卡住整个事件循环，让同一进程的其它请求一起等着。
    hashed_password = await security.hash_password_async(user_data.password)
    user = User(username=user_data.username, password=hashed_password)
    db.add(user)
    # flush 把 INSERT 发给数据库，能立刻拿到自增主键；但事务还没提交，
    # 后续步骤失败可以整体回滚，不会留下“半个用户”。
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
    # 数据库只存 SHA-256 摘要：万一数据库泄露，攻击者拿到的哈希也冒充不了用户。
    # Token 本身是 32 字节随机串，猜不出来，所以用快速哈希就够，不需要慢哈希。
    token_hash = security.hash_token(raw_token)
    # 过期时间从配置读，部署时改配置就能调整有效期，不用改代码。
    expires_at = utcnow() + timedelta(days=TOKEN_TTL_DAYS)

    await db.execute(delete(UserToken).where(UserToken.user_id == user_id))
    db.add(UserToken(user_id=user_id, token=token_hash, expires_at=expires_at))
    await db.flush()
    if commit:
        await db.commit()
    return raw_token


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """校验用户名 + 密码，成功返回用户，失败返回 None。

    参数：
        db: 异步数据库会话。
        username: 登录名。
        password: 用户输入的明文密码，只在内存里出现，不落库。
    返回：
        校验通过时返回 User 实体；用户名不存在或密码错误都返回 None
        （调用方统一回“用户名或密码错误”，不告诉攻击者哪一步错了）。
    """
    user = await get_user_by_username(db, username)
    if not user:
        # 仍然执行一次哈希校验，避免“用户不存在”和“密码错误”响应时间差异过大。
        await security.verify_password_async(password, _DUMMY_PASSWORD_HASH)
        return None
    if not await security.verify_password_async(password, user.password):
        return None
    return user


async def get_user_by_token(db: AsyncSession, token: str) -> User | None:
    """用原始 Token 换用户：先算哈希，再按哈希查未过期的令牌记录。

    参数：
        db: 异步数据库会话。
        token: 客户端 Authorization 头里带来的原始 Token。
    返回：
        Token 有效且未过期时返回对应 User；否则返回 None。
    """
    # 取舍：这里每个请求都查一次数据库，换来“Token 可以被立即吊销”
    # （退出登录、改密码后旧 Token 马上失效）。
    # 如果换成 JWT 这种“自校验”令牌、不查库，会更快，但服务端在过期前
    # 没法主动让某个 Token 失效，安全性上要打折。
    token_hash = security.hash_token(token)
    stmt = (
        select(User)
        .join(UserToken, UserToken.user_id == User.id)
        .where(UserToken.token == token_hash, UserToken.expires_at > utcnow())
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_token(db: AsyncSession, token: str) -> bool:
    """退出登录：删除该 Token 对应的记录，让它立刻失效。

    参数：
        db: 异步数据库会话。
        token: 客户端提交的原始 Token。
    返回：
        真的删掉了一行返回 True；Token 本来就不存在返回 False，重复退出不报错。
    """
    token_hash = security.hash_token(token)
    result = await db.execute(delete(UserToken).where(UserToken.token == token_hash))
    await db.commit()
    return bool(result.rowcount)


async def update_user(
    db: AsyncSession, username: str, user_data: UserUpdateRequest
) -> User | None:
    """更新用户资料（只改前端真正提交了的字段）。

    参数：
        db: 异步数据库会话。
        username: 要改的用户名，先按它查出用户。
        user_data: 更新请求体，所有字段都可选。
    返回：
        更新后的 User；用户不存在返回 None；一个字段都没传则抛 400。
    """
    # exclude_unset 只保留前端“真的传了”的字段，exclude_none 再滤掉显式传 null 的，
    # 于是“没传”和“传了空值”都不会把用户已有资料清空。
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
    """修改密码，并让该用户所有旧 Token 立即失效。

    参数：
        db: 异步数据库会话。
        user: 当前登录用户（已由认证依赖查出来）。
        old_password: 用户输入的旧密码，用于二次确认身份。
        new_password: 新密码明文，函数内部哈希后才入库。
    返回：
        旧密码正确并改成功返回 True；旧密码不对返回 False，什么都不改。
    """
    # 先校验旧密码：光有有效 Token 还不够，防止别人拿到手机后直接改密码锁号。
    if not await security.verify_password_async(old_password, user.password):
        return False

    user.password = await security.hash_password_async(new_password)
    db.add(user)
    # 改密码后吊销该用户全部 Token，旧设备立即失效。
    await db.execute(delete(UserToken).where(UserToken.user_id == user.id))
    await db.commit()
    await db.refresh(user)
    return True
