"""
聊天 API 路由
提供 SSE 流式聊天接口（支持双角色：customer / agent）
"""
import json
import asyncio
from typing import Optional, Literal
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.react_agent import ReactAgent
from utils.logger_handler import logger

router = APIRouter()

# 双 Agent 实例（在 main.py 的 lifespan 启动时初始化）
_customer_agent: Optional[ReactAgent] = None
_agent_agent: Optional[ReactAgent] = None


def initialize_agents():
    """由 FastAPI lifespan 启动时调用"""
    global _customer_agent, _agent_agent
    if _customer_agent is None:
        logger.info("[Chat]初始化双 Agent 实例...")
        _customer_agent = ReactAgent(role="customer")
        _agent_agent = ReactAgent(role="agent")
        logger.info("[Chat]双 Agent 就绪")


def get_agent(role: str) -> ReactAgent:
    if role == "customer":
        if _customer_agent is None:
            raise RuntimeError("Customer Agent 尚未初始化")
        return _customer_agent
    elif role == "agent":
        if _agent_agent is None:
            raise RuntimeError("Agent Agent 尚未初始化")
        return _agent_agent
    else:
        raise ValueError(f"未知角色：{role}")


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    role: Literal["customer", "agent"] = "customer"


def sse_format(data: str) -> str:
    """格式化为 SSE 协议格式"""
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

    请求体：{ "conversation_id": "...", "message": "用户问题", "role": "customer"/"agent" }
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
            agent = get_agent(req.role)
            # 角色隔离：thread_id 加 role 前缀，避免两角色共享对话历史
            thread_id = f"{req.role}:{req.conversation_id or 'default'}"

            async for chunk in agent.execute_astream(req.message, thread_id=thread_id):
                # 处理工具状态标记
                if chunk.startswith("\n__tool_start__:"):
                    tool_name = chunk.replace("\n__tool_start__:", "").strip()
                    yield sse_event("tool", {"phase": "start", "name": tool_name})
                elif chunk.startswith("\n__tool_end__:"):
                    tool_name = chunk.replace("\n__tool_end__:", "").strip()
                    yield sse_event("tool", {"phase": "end", "name": tool_name})
                else:
                    yield sse_event("token", {"content": chunk})

                await asyncio.sleep(0)

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
            "X-Accel-Buffering": "no",
        },
    )
