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
    if await users_crud.get_user_by_username(db, payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

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
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"rate:login:{client_ip}:{payload.username}"
    if not await hit(rate_key, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
        )

    user = await users_crud.authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    await reset(rate_key)
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
    success = await users_crud.change_password(
        db, user, payload.old_password, payload.new_password
    )
    if not success:
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
    if credentials is not None:
        await users_crud.revoke_token(db, credentials.credentials)
    return ok(None, message="已退出登录")
