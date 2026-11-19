"""密码哈希与 Token 生成。

[优化] 原代码：
    token = str(uuid.uuid4())                 # 明文入库
    expires_at = datetime.now() + timedelta(days=7)
    def get_hash_password(...):               # 同步 CPU 操作
        return pwd_context.hash(password)
问题：
    1. UUID4 可预测性虽低，但明文存库，一旦拖库即可冒充所有用户；
    2. 固定 7 天过期，不能配置；
    3. pbkdf2 哈希在 async 路由中同步执行，会阻塞事件循环。
修复：
    - secrets.token_urlsafe(32) 生成高熵 Token，数据库只存 SHA-256；
    - 过期时间走配置；
    - 哈希/校验放到线程池（anyio.to_thread.run_sync）。
"""

from __future__ import annotations

import hashlib
import secrets

import anyio
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], default="pbkdf2_sha256")


def get_hash_password(password: str) -> str:
    """同步哈希，仅供脚本/测试使用；请求内请用 async 版本。"""
    return pwd_context.hash(password)


def get_verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


async def hash_password_async(password: str) -> str:
    return await anyio.to_thread.run_sync(get_hash_password, password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await anyio.to_thread.run_sync(
        get_verify_password, plain_password, hashed_password
    )


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
