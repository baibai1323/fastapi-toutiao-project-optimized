"""AI 对话请求 Schema。

[优化] 原代码：
    class ChatRequest(BaseModel):
        messages: list
        model: str = "qwen-plus"
问题：
    1. messages 完全无类型/长度限制，可以塞任意 JSON；
    2. model 由客户端任意指定，可调用高价模型/不存在的模型；
    3. 没有限制历史消息条数，prompt 可以无限长。
修复：
    限制 role/content/条数，模型只允许白名单。
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from schemas.common import CamelModel


class ChatMessage(CamelModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequest(CamelModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=20)
    model: Literal["qwen-plus", "qwen-turbo", "qwen-max"] = "qwen-plus"
