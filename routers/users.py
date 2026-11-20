"""用户接口：注册、登录、资料、改密、登出。

[优化] 原代码问题：
    1. 注册先 commit 用户，再单独 commit Token，第二步失败会留下没有 Token 的用户；
    2. 登录没有限流，可以无限撞库；
    3. 改密码失败返回 500，且不吊销旧 Token；
    4. 没有登出接口。
修复：
    - 注册两步放在同一事务；
    - 登录按 IP + 用户名限流；
    - 改密失败返回 400，成功后旧 Token 全部失效；
    - 新增登出。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from config.settings import LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW
from crud import users as users_crud
from models.users import User
from schemas.common import ApiResponse, ok
from schemas.users import (
    UserAuthResponse,
    UserChangePasswordRequest,
    UserInfoResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserUpdateRequest,
)
from utils.auth import bearer_scheme, get_current_user
from utils.rate_limit import hit, reset

router = APIRouter(prefix="/api/v1/user", tags=["用户"])


def _auth_payload(user: User, token: str) -> UserAuthResponse:
    """把“用户 + 令牌”组装成注册/登录接口的统一返回体。

    做什么：注册和登录都要返回同样的结构（token + user_info），抽成小函数
        避免两处各写一遍，以后加字段时也不会漏改其中一处。
    参数：
        user: 用户 ORM 对象，交给 UserInfoResponse 转成对外字段。
        token: 原始访问令牌。它只在这一次响应里出现，服务端只保存它的哈希。
    返回：
        UserAuthResponse，前端保存后放进后续请求的 Authorization 头。
    """
    return UserAuthResponse(token=token, user_info=UserInfoResponse.model_validate(user))


@router.post(
    "/register",
    response_model=ApiResponse[UserAuthResponse],
    summary="注册",
)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserAuthResponse]:
    """注册新用户，并在同一事务里签发第一个访问令牌。

    做什么：先查用户名是否已存在（存在就 409），再把“建用户”和“建 Token”
        放在同一个事务里提交。任一步失败都会一起回滚，不会留下“有用户但
        没有 Token”的半成品数据（原实现分两次提交就有这个问题）。
    参数：
        payload: 注册请求体，含 username/password 等字段，已由 Pydantic 校验。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 含 token 与 user_info；用户名重复时抛 409。
    """
    # 用户名是登录凭据的一部分，必须唯一；先查一次给出友好提示，
    # 真正的兜底仍是数据库的唯一索引（并发下两次查询都可能“不存在”）。
    if await users_crud.get_user_by_username(db, payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

    # 传 commit=False 表示“先别提交，攒着等调用方一起提交”，这样两步要么都成功、
    # 要么都回滚。数据一致性靠事务（transaction）保证。
    # [优化] 用户与 Token 同一事务：任一步失败一起回滚。
    user = await users_crud.create_user(db, payload, commit=False)
    token = await users_crud.create_token(db, user.id, commit=False)
    await db.commit()
    await db.refresh(user)
    return ok(_auth_payload(user, token))


@router.post(
    "/login",
    response_model=ApiResponse[UserAuthResponse],
    summary="登录",
)
async def login(
    payload: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserAuthResponse]:
    """校验用户名密码，并签发一个新的访问令牌。

    做什么：先按“客户端 IP + 用户名”限流，防止脚本无限次试密码（撞库）；
        再校验密码，成功后清掉该用户所有旧 Token（相当于同一账号只保留
        一个有效登录），随后生成新 Token 并重置限流计数。
    参数：
        payload: 登录请求体，含 username 与 password。
        request: 请求对象，用来取客户端 IP 参与限流 key 的拼装。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 含 token 与 user_info；密码错抛 401，太频繁抛 429。
    """
    # request.client 在测试环境里可能为 None，兜底成 "unknown" 避免报错。
    client_ip = request.client.host if request.client else "unknown"
    # 限流 key 同时带上 IP 与用户名：既防单 IP 扫多个账号，也防多 IP 撞一个账号。
    rate_key = f"rate:login:{client_ip}:{payload.username}"
    if not await hit(rate_key, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
        )

    # authenticate_user 内部会把明文密码与库里的哈希比对，这里只关心是否为 None。
    user = await users_crud.authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 登录成功就清零失败计数，否则用户偶尔输错几次后，正常登录也会被拦。
    await reset(rate_key)
    # Token 是 UUID 形式的随机串，有效期 TOKEN_TTL_DAYS 天（默认 7 天）；
    # 数据库只存它的 SHA-256 哈希，即使库被拖也拿不到可用的明文 Token。
    token = await users_crud.create_token(db, user.id)
    return ok(_auth_payload(user, token), message="登录成功")


@router.get(
    "/info",
    response_model=ApiResponse[UserInfoResponse],
    summary="当前用户信息",
)
async def get_user_info(
    user: User = Depends(get_current_user),
) -> ApiResponse[UserInfoResponse]:
    """返回当前登录用户的资料。

    做什么：用户对象已经由 get_current_user 从 Token 解析好并注入进来，
        这里只做“ORM 对象 -> 响应模型”的字段转换，不再多查一次数据库。
    参数：
        user: 当前登录用户，由依赖注入自动解析，未登录时根本进不到这里。
    返回：
        ApiResponse，data 是用户资料（不含密码哈希等敏感字段）。
    """
    return ok(UserInfoResponse.model_validate(user))


@router.put(
    "/update",
    response_model=ApiResponse[UserInfoResponse],
    summary="更新资料",
)
async def update_user_info(
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserInfoResponse]:
    """更新当前登录用户的资料（昵称、头像等允许修改的字段）。

    做什么：用 Token 解析出的用户名定位记录，再写入请求体里的字段。
        用户名取自服务端解析结果而不是请求体，避免有人改别人的资料。
    参数：
        payload: 更新请求体，只包含允许修改的字段。
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 是更新后的用户资料；记录不存在时抛 404。
    """
    updated = await users_crud.update_user(db, user.username, payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return ok(UserInfoResponse.model_validate(updated), message="更新成功")


@router.put(
    "/password",
    response_model=ApiResponse[None],
    summary="修改密码",
)
async def change_password(
    payload: UserChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """修改当前用户密码，并让该用户所有旧 Token 立即失效。

    做什么：先校验旧密码（防止 Token 被盗后直接改密顶掉号主），成功后
        写入新密码并删除该用户的全部令牌记录；这样其他设备上的登录会
        立刻掉线，必须用新密码重新登录。
    参数：
        payload: 改密请求体，含 old_password 与 new_password。
        user: 当前登录用户，由依赖注入提供。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，成功时 data 为 None；旧密码错误时抛 400。
    """
    success = await users_crud.change_password(
        db, user, payload.old_password, payload.new_password
    )
    if not success:
        # 旧密码错属于“用户输入问题”，用 400 而不是 500；
        # 500 会误导监控以为服务端故障，还可能触发无意义的告警。
        # [优化] 原代码返回 500“修改密码失败”，把用户输入错误当成服务端错误。
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误",
        )
    return ok(None, message="密码修改成功，请重新登录")


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    summary="登出",
)
async def logout(
    credentials=Depends(bearer_scheme),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """退出登录：把本次请求携带的 Token 从数据库删除。

    做什么：只吊销当前这一个 Token，不影响同账号在其他设备上的登录；
        删除后再拿旧 Token 请求，get_current_user 查不到记录就会返回 401。
    参数：
        credentials: HTTPBearer 解析出的凭证对象，可能为 None。
        _: 当前登录用户。这里只借这个依赖确认“必须已登录”，本身不使用。
        db: 异步数据库会话，由依赖注入提供。
    返回：
        ApiResponse，data 为 None，message 提示已退出。
    """
    if credentials is not None:
        await users_crud.revoke_token(db, credentials.credentials)
    return ok(None, message="已退出登录")
