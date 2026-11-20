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
# HTTPBearer 是 FastAPI 预置的“从 Authorization 头里取令牌”的工具。
# auto_error 设为 False：没带令牌时它不自己抛 403，而是把 None 交给我们，
# 这样缺令牌（应 401）和令牌错（也是 401）能给出同一种响应，不会一个 403 一个 401。


def _unauthorized(detail: str = "无效或已过期的令牌") -> HTTPException:
    """构造一个标准的 401 未认证异常。

    参数：
        detail: 返回给前端的提示文字，默认是“令牌无效或过期”。
    返回：
        带 WWW-Authenticate 响应头的 HTTPException，由全局异常处理器转成 JSON。
    """
    # 401 按 HTTP 规范必须带 WWW-Authenticate 头，告诉客户端该用哪种认证方式；
    # 少了它有些前端库/代理会当成普通错误处理，排障时很难看出是认证问题。
    return HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """必须登录的接口用它：解析令牌并查出当前用户。

    参数：
        credentials: 依赖注入（Dependency Injection）自动塞进来，里面是 scheme 和令牌原文；
            没带 Authorization 头时是 None。
        db: 数据库会话，同样由 FastAPI 依赖注入提供，用完自动关闭。
    返回：
        通过校验的 User 对象；令牌缺失、格式不对或查不到用户时抛 401。
    """
    # scheme 是 Authorization 头里 "Bearer xxx" 的前半段，
    # 必须校验：否则 "Basic xxx" 这种别的认证方式也会被当成令牌去查库。
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("请先登录")

    # 这里选择“每次请求都查一次库”而不是把用户信息签进 JWT：
    # 好处是退出登录、改密码、封号能立刻生效（令牌一删/一改就失效）；
    # 代价是每个受保护请求多一次按 token 唯一索引的查询，量级上完全可接受。
    user = await users.get_user_by_token(db, credentials.credentials)
    if not user:
        raise _unauthorized()
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选登录的接口用它：登录了就拿用户，没登录也放行。

    参数：
        credentials: 依赖注入的令牌信息，没带时为 None。
        db: 数据库会话，由依赖注入提供。
    返回：
        登录且令牌有效返回 User；没登录或令牌无效返回 None（不抛异常）。
    """
    # 典型用途是新闻详情页：登录用户可以顺带返回“是否已收藏”，
    # 未登录用户照样能看新闻，所以这里不能像上面那样抛 401。
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return await users.get_user_by_token(db, credentials.credentials)
