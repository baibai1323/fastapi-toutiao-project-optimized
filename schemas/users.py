"""用户请求/响应 Schema。

[优化] 原代码：
    class UserRequest(BaseModel):
        username: str
        password: str
    class UserUpdateRequest(BaseModel):
        nickname: Optional[str] = None      # 没有 max_length
问题：
    1. 注册不校验用户名/密码长度，能写入空密码或超长字符串；
    2. 更新昵称可超过数据库 VARCHAR(50)，直接 500；
    3. 登录和注册共用模型，加密码规则后会误伤老用户登录。
修复：
    拆分 Register/Login；注册密码至少 8 位；更新字段全部限长；统一 camelCase。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from schemas.common import CamelModel

USERNAME_PATTERN = r"^[A-Za-z0-9_\u4e00-\u9fa5-]+$"


class UserRegisterRequest(CamelModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(CamelModel):
    # 登录不限制密码长度，兼容历史用户；只做上限保护，避免超长 payload。
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserInfoBase(CamelModel):
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    gender: Optional[Literal["male", "female", "unknown"]] = Field(None, description="性别")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")


class UserInfoResponse(UserInfoBase):
    id: int
    username: str


class UserAuthResponse(CamelModel):
    token: str
    user_info: UserInfoResponse


class UserUpdateRequest(CamelModel):
    nickname: Optional[str] = Field(None, max_length=50)
    avatar: Optional[str] = Field(None, max_length=255)
    gender: Optional[Literal["male", "female", "unknown"]] = None
    bio: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)


class UserChangePasswordRequest(CamelModel):
    old_password: str = Field(..., max_length=128, description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")
