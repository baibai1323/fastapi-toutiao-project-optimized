"""集中配置。

[优化] 原代码把数据库地址、Redis 地址、CORS、Token 过期时间分散写死在各处：
    REDIS_HOST = "localhost"
    expires_at = datetime.now() + timedelta(days=7)
    allow_origins=["*"]
问题：
    1. 本地/测试/生产只能改代码；
    2. DEBUG、Token 时长、限流阈值无法按环境调整；
    3. 生产容易误用开发配置。
修复：
    统一从环境变量读取，并提供安全的默认值；所有模块只依赖本文件。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _get_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


APP_NAME = os.getenv("APP_NAME", "XWZX News API")
APP_VERSION = "2.0.0"
DEBUG = _get_bool("DEBUG", False)

DATABASE_URL = os.getenv("DATABASE_URL", "")
SQL_ECHO = _get_bool("SQL_ECHO", False)
DB_POOL_SIZE = _get_int("DB_POOL_SIZE", 10)
DB_MAX_OVERFLOW = _get_int("DB_MAX_OVERFLOW", 20)
DB_POOL_RECYCLE = _get_int("DB_POOL_RECYCLE", 1800)

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REDIS_TIMEOUT = float(os.getenv("REDIS_TIMEOUT", "1.0"))

CORS_ORIGINS = _get_list(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

TOKEN_TTL_DAYS = _get_int("TOKEN_TTL_DAYS", 7)
LOGIN_RATE_LIMIT = _get_int("LOGIN_RATE_LIMIT", 5)
LOGIN_RATE_WINDOW = _get_int("LOGIN_RATE_WINDOW", 300)

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_URL = os.getenv(
    "DASHSCOPE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
)
# [优化] 没有 Key 时默认走“演示模式”，返回预设的 SSE，方便别人 clone 后直接体验。
# 配置了真实 Key 时始终调用真实模型；把 AI_MOCK_MODE 设为 false 可强制关闭演示。
AI_MOCK_MODE = _get_bool("AI_MOCK_MODE", True)
AI_RATE_LIMIT = _get_int("AI_RATE_LIMIT", 30)
AI_RATE_WINDOW = _get_int("AI_RATE_WINDOW", 3600)
AI_ALLOWED_MODELS = _get_list("AI_ALLOWED_MODELS", "qwen-plus,qwen-turbo,qwen-max")
