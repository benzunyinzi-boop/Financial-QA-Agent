"""
ReactAgent - 基于 LangGraph 的 ReAct 智能客服

迁移自旧的 langchain.initialize_agent，获得：
  - 原生流式输出（token 级，无需过滤 "Final Answer:"）
  - 对话记忆（通过 MemorySaver checkpointer，内存持久化）
  - 多工具并行调用支持
  - 人工介入（human-in-the-loop）能力

注：当前使用 MemorySaver（内存版），服务重启后对话历史会丢失。
     生产环境可升级为 AsyncSqliteSaver 或 PostgresSaver 实现跨重启持久化。
"""
from typing import AsyncGenerator, Optional

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from utils.logger_handler import logger
from agent.tools.agent_tools import (
    rag_summarize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
)


class ReactAgent:
    """
    LangGraph ReactAgent with in-memory conversation history.
    """

    def __init__(self):
        self.system_prompt = load_system_prompts()

        # MemorySaver：内存版 checkpointer，同一进程内多轮对话有效
        # 优点：零配置、无依赖、性能高
        # 缺点：服务重启后历史丢失
        self.checkpointer = MemorySaver()

        self.agent = create_react_agent(
            model=chat_model,
            tools=[
                rag_summarize, get_weather, get_user_location, get_user_id,
                get_current_month, fetch_external_data, fill_context_for_report,
            ],
            checkpointer=self.checkpointer,
            state_modifier=self.system_prompt,
        )

        logger.info("[Agent]LangGraph ReactAgent 初始化完成（MemorySaver 内存记忆）")

    async def execute_astream(
        self,
        query: str,
        thread_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        异步流式接口（FastAPI SSE 使用）

        :param query: 用户问题
        :param thread_id: 会话 ID（用于持久化记忆）。同一 thread_id 共享对话上下文。
        """
        config = {"configurable": {"thread_id": thread_id or "default"}}

        try:
            async for event in self.agent.astream_events(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
                version="v2",
            ):
                kind = event.get("event")

                # LLM 流式 token 输出
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = getattr(chunk, "content", "")
                    if content:
                        yield content

                # 工具开始调用
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "未知工具")
                    yield f"\n__tool_start__:{tool_name}\n"

                # 工具调用结束
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "未知工具")
                    yield f"\n__tool_end__:{tool_name}\n"

        except Exception as e:
            logger.error(f"[Agent astream]执行失败：{str(e)}", exc_info=True)
            yield f"\n抱歉，服务暂时不可用：{str(e)}"


if __name__ == '__main__':
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()

    async def main():
        agent = ReactAgent()

        print("=== 第 1 轮 ===")
        async for chunk in agent.execute_astream("扫地机器人主要功能有哪些？", thread_id="demo"):
            print(chunk, end="", flush=True)

        print("\n\n=== 第 2 轮（测试记忆）===")
        async for chunk in agent.execute_astream("我刚才问的是什么？", thread_id="demo"):
            print(chunk, end="", flush=True)
        print()

    asyncio.run(main())
