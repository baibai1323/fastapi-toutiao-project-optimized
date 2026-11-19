"""AI 对话代理：服务端保管 DashScope Key，真正流式转发 SSE。

[优化] 原代码：
    resp = await client.post(url, json=payload)      # 先缓冲完整响应
    return Response(resp.content, media_type="text/event-stream")
问题：
    1. 没有鉴权，任何人可刷爆 DashScope 账单；
    2. messages/model 完全由客户端控制；
    3. 上游全部生成完才返回，前端看到的是“假流式”；
    4. 上游 4xx/5xx 也会被包成 HTTP 200 的 SSE。
修复：
    - 必须登录 + 按用户限流；
    - Schema 限制消息条数/长度/模型白名单；
    - httpx stream 逐块转发；
    - 上游非 200 直接返回 502，不泄露上游响应体；
    - 无 Key 时默认走演示 SSE（X-AI-Mode: mock），便于他人 clone 后体验。
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from config.settings import (
    AI_MOCK_MODE,
    AI_RATE_LIMIT,
    AI_RATE_WINDOW,
    DASHSCOPE_API_KEY,
    DASHSCOPE_URL,
)
from models.users import User
from schemas.ai import ChatRequest
from utils.auth import get_current_user
from utils.rate_limit import hit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["AI"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_chunk(model: str, content: str, finish_reason: str | None = None) -> str:
    """把一段文本包装成 OpenAI 兼容的 SSE chunk。"""
    payload = {
        "id": "chatcmpl-mock",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _mock_stream(payload: ChatRequest):
    """无 Key 时的演示流：不调用外部服务，也不会产生费用。

    仍然走登录 + 限流，目的是让人看到“真实接口形态”，而不是前端本地假数据。
    """
    last_user = next(
        (m.content for m in reversed(payload.messages) if m.role == "user"),
        "",
    )
    preview = last_user.replace("\n", " ").strip()[:60] or "你的问题"
    text = (
        "（演示模式）当前没有配置 `DASHSCOPE_API_KEY`，"
        "下面展示的是一段**预设的流式回复**，不会调用真实模型。\n\n"
        f"你刚才问的是：**{preview}**\n\n"
        "这个模式主要用于让 clone 项目的人无需申请 Key 就能看到：\n"
        "1. 后端通过 SSE 逐块返回；\n"
        "2. 前端逐字渲染 Markdown；\n"
        "3. 未登录请求会被 401 拦截。\n\n"
        "配置真实 Key 后，请求会自动切换到通义千问。"
    )
    # 按字符切片，模拟模型逐 token 输出；延迟只为演示效果，不参与业务逻辑。
    for index in range(0, len(text), 8):
        yield _sse_chunk(payload.model, text[index : index + 8])
        await asyncio.sleep(0.035)
    yield _sse_chunk(payload.model, "", finish_reason="stop")
    yield "data: [DONE]\n\n"


@router.post(
    "/chat",
    summary="AI 对话（SSE 流式）",
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    if not await hit(f"rate:ai:{user.id}", AI_RATE_LIMIT, AI_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI 调用过于频繁，请稍后再试",
        )

    if not DASHSCOPE_API_KEY:
        if AI_MOCK_MODE:
            return StreamingResponse(
                _mock_stream(payload),
                media_type="text/event-stream",
                headers={**_SSE_HEADERS, "X-AI-Mode": "mock"},
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务未配置",
        )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-DashScope-SSE": "enable",
    }
    body = {
        "model": payload.model,
        "messages": [message.model_dump() for message in payload.messages],
        "stream": True,
    }

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
    )
    try:
        request = client.build_request("POST", DASHSCOPE_URL, json=body, headers=headers)
        upstream = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.warning("AI 上游连接失败: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 服务暂时不可用",
        ) from exc

    if upstream.status_code != 200:
        # 读完再关闭，避免连接泄漏；响应体只进日志，不回给客户端。
        error_body = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        logger.warning(
            "AI 上游返回 %s: %s", upstream.status_code, error_body[:500]
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 服务暂时不可用",
        )

    async def stream_body():
        try:
            async for chunk in upstream.aiter_bytes():
                if chunk:
                    yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(),
        media_type="text/event-stream",
        headers={**_SSE_HEADERS, "X-AI-Mode": "live"},
    )
