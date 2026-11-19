"""认证依赖。

[优化] 原代码：
    authorization: str = Header(..., alias="Authorization")
    token = authorization.replace("Bearer ", "")
问题：
    1. 缺少 Authorization 头时 FastAPI 返回 422，而不是 401；
    2. `replace` 不校验 scheme，传 "Basic xxx" 也可能被当成 Token；
    3. 没有 WWW-Authenticate 响应头，不符合 HTTP 认证规范。
修复：
    使用 FastAPI 的 HTTPBearer(auto_error=False)，统一返回 401 + WWW-Authenticate。
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from config.db_conf import get_db
from crud import users
from models.users import User

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "无效或已过期的令牌") -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("请先登录")

    user = await users.get_user_by_token(db, credentials.credentials)
    if not user:
        raise _unauthorized()
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return await users.get_user_by_token(db, credentials.credentials)
