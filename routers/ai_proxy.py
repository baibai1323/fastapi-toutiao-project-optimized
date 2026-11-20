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

# SSE（Server-Sent Events，服务端推送事件）是“服务器一直开着连接、反复往
# 客户端写一小段文本”的协议。下面三个响应头是流式场景的常规配置：
# no-cache 防中间缓存攒包，keep-alive 保持长连接，
# X-Accel-Buffering: no 让 Nginx 不要缓冲，否则前端要等全部生成完才看到字。
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


# 这个函数负责“分帧”：SSE 协议要求每条消息以 "data: " 开头、以空行结尾，
# 这里统一拼装，避免调用方各写一套格式导致前端解析失败。
def _sse_chunk(model: str, content: str, finish_reason: str | None = None) -> str:
    """把一段文本包装成 OpenAI 兼容的 SSE chunk。"""
    # 做什么：按 OpenAI 流式接口的 JSON 结构（id/object/model/choices）组装
    #     一个增量块，再套上 SSE 的 "data: ...\n\n" 外壳，让前端可以用
    #     现成的 OpenAI SDK 或解析器直接消费。
    # 参数 model：模型名，原样回填，前端据此确认响应来自哪个模型。
    # 参数 content：本次推送的文本片段，允许为空串（表示只带结束标记）。
    # 参数 finish_reason：为 "stop" 表示这是最后一片，前端据此收尾。
    # 返回：str，一段完整的 SSE 文本帧，可直接写进响应流。
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
    # 把 ensure_ascii 设成 False，中文就按原样输出而不是 \uXXXX 转义，省带宽也好排查。
    # 结尾必须留一个空行，SSE 客户端靠“空行”切分消息。
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# 生成器函数：用 yield 一段段“吐”数据，FastAPI 会把它接到 StreamingResponse
# 上，所以调用方看到的是逐步到达的文本，而不是一次性返回。
async def _mock_stream(payload: ChatRequest):
    """无 Key 时的演示流：不调用外部服务，也不会产生费用。

    仍然走登录 + 限流，目的是让人看到“真实接口形态”，而不是前端本地假数据。
    做什么：从最后一条 user 消息里截一段预览拼进固定文案，再按固定节奏
        分片吐出去，模拟真实模型的逐字输出。
    参数：
        payload: 聊天请求体，这里只用到 model（回填用）和 messages。
    返回：
        异步生成器，逐帧 yield SSE 文本帧；最后一帧 finish_reason 为
        stop，再补一条 data: [DONE] 作为流结束标记。
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
    """AI 对话主入口：鉴权、限流、分流到演示流或真实上游，再原样流式转发。

    做什么：先确认调用者已登录（依赖注入会解析 Authorization 头里的
        Bearer Token），再按“用户 + 时间窗口”限流；没有配置上游 Key 时
        走本地演示流，配置了就把请求转给 DashScope，并保持边收边发的
        流式体验，而不是等上游全部生成完再一次性返回。
    参数：
        payload: 聊天请求体，含 model 模型名与 messages 消息列表。
        user: 当前登录用户，由 get_current_user 自动注入，限流按 user.id 计。
    返回：
        StreamingResponse，媒体类型 text/event-stream；失败时抛
        HTTPException：429 表示限流，503 表示未配置，502 表示上游故障。
    """
    # 固定窗口限流：同一个用户在 AI_RATE_WINDOW 秒内最多调用 AI_RATE_LIMIT 次。
    # 计数存在 Redis 里，多进程部署时也能共享同一份计数。
    if not await hit(f"rate:ai:{user.id}", AI_RATE_LIMIT, AI_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI 调用过于频繁，请稍后再试",
        )

    # mock（模拟）模式：没有 Key 时不去调外部服务，返回一段预设的流式文本，
    # 让 clone 项目的人不申请 Key 也能体验完整链路；同时保留登录与限流，
    # 保证形态和真实调用一致。若显式关掉了 mock，才返回 503。
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

    # 真实上游的请求头：Bearer Token 放 Key，Accept 与 X-DashScope-SSE
    # 告诉 DashScope 本次要按 SSE 协议返回，而不是等生成完给一个整包。
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-DashScope-SSE": "enable",
    }
    # model_dump() 把 Pydantic 模型转成普通 dict，才能序列化成 JSON 发出去；
    # 把 stream 设为 True 是向上游声明“请按流式返回”，别等全部生成完再给整包。
    body = {
        "model": payload.model,
        "messages": [message.model_dump() for message in payload.messages],
        "stream": True,
    }

    # 超时按阶段拆开：connect/write/pool 各 10 秒，read 给 60 秒。
    # 读超时必须放宽，因为模型生成一段长回答可能要几十秒，卡太死会被误判超时。
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
        """真正搬运字节的生成器：从上游读一块就往下游写一块。

        做什么：遍历上游的原始字节流，非空才转发；用 try/finally 保证
            无论正常结束、客户端断开还是中途报错，两个连接都会被关闭，
            不会把 httpx 连接池占满（连接泄漏最终会让服务卡死）。
        参数：
            无。它通过闭包直接使用外层的 upstream 与 client。
        返回：
            异步生成器，逐块 yield bytes，由 StreamingResponse 负责写回。
        """
        try:
            async for chunk in upstream.aiter_bytes():
                # 上游偶尔会发空块（心跳/分帧残留），转给前端会让解析器报错。
                if chunk:
                    yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    # X-AI-Mode: live 告诉前端这次是真实调用；mock 时则为 mock。
    # 两个值前端只用于展示提示，不影响协议本身。
    return StreamingResponse(
        stream_body(),
        media_type="text/event-stream",
        headers={**_SSE_HEADERS, "X-AI-Mode": "live"},
    )
