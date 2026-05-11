"""
聊天 API 路由
提供 SSE 流式聊天接口
"""
import json
import asyncio
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.react_agent import ReactAgent
from utils.logger_handler import logger

router = APIRouter()

# 单例 Agent（在 main.py 的 lifespan 启动时初始化）
_agent_instance: Optional[ReactAgent] = None


def initialize_agent():
    """由 FastAPI lifespan 启动时调用"""
    global _agent_instance
    if _agent_instance is None:
        logger.info("[Chat]初始化 ReactAgent 单例")
        _agent_instance = ReactAgent()
    return _agent_instance


def get_agent() -> ReactAgent:
    if _agent_instance is None:
        raise RuntimeError("Agent 尚未初始化，请确保 FastAPI lifespan 正确配置")
    return _agent_instance


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


def sse_format(data: str) -> str:
    """格式化为 SSE 协议格式"""
    # 处理换行：SSE 协议中 data: 后只能是单行，多行需要每行加 data:
    lines = data.split("\n")
    return "\n".join(f"data: {line}" for line in lines) + "\n\n"


def sse_event(event_type: str, payload: dict) -> str:
    """格式化为带事件类型的 SSE"""
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """
    流式聊天接口（SSE）

    请求体：{ "conversation_id": "...", "message": "用户问题" }
    响应：Server-Sent Events 流
      - event: token   data: { "content": "..." }
      - event: tool    data: { "phase": "start"/"end", "name": "..." }
      - event: done    data: { "conversation_id": "..." }
      - event: error   data: { "message": "..." }
    """
    if not req.message or not req.message.strip():
        return StreamingResponse(
            iter([sse_event("error", {"message": "消息不能为空"})]),
            media_type="text/event-stream",
        )

    async def event_generator():
        try:
            agent = get_agent()
            # 把 conversation_id 作为 LangGraph thread_id 传入，启用对话记忆
            async for chunk in agent.execute_astream(req.message, thread_id=req.conversation_id):
                # 处理工具状态标记
                if chunk.startswith("\n__tool_start__:"):
                    tool_name = chunk.replace("\n__tool_start__:", "").strip()
                    yield sse_event("tool", {"phase": "start", "name": tool_name})
                elif chunk.startswith("\n__tool_end__:"):
                    tool_name = chunk.replace("\n__tool_end__:", "").strip()
                    yield sse_event("tool", {"phase": "end", "name": tool_name})
                else:
                    # 普通 token
                    yield sse_event("token", {"content": chunk})

                # 让出控制权，避免阻塞事件循环
                await asyncio.sleep(0)

            # 完成
            yield sse_event("done", {"conversation_id": req.conversation_id or ""})

        except Exception as e:
            logger.error(f"[Chat Stream]错误：{str(e)}", exc_info=True)
            yield sse_event("error", {"message": f"服务异常：{str(e)}"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )
