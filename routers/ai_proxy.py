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
    - 上游非 200 直接返回 502，不泄露上游响应体。
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from config.settings import (
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


@router.post(
    "/chat",
    summary="AI 对话（SSE 流式）",
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    if not DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务未配置",
        )

    if not await hit(f"rate:ai:{user.id}", AI_RATE_LIMIT, AI_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI 调用过于频繁，请稍后再试",
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
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
