from typing import AsyncGenerator, Literal, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from model.factory import chat_model
from utils.prompt_loader import load_prompt_by_role
from agent.tools.agent_tools import build_tools_for_role
from utils.logger_handler import logger


class ReactAgent:
    def __init__(self, role: Literal["customer", "agent"] = "customer"):
        self.role = role
        self.system_prompt = load_prompt_by_role(role)
        self.checkpointer = MemorySaver()

        logger.info(f"[ReactAgent]初始化 {role} Agent...")
        self.agent = create_react_agent(
            model=chat_model,
            tools=build_tools_for_role(role),
            checkpointer=self.checkpointer,
            state_modifier=self.system_prompt,
        )
        logger.info(f"[ReactAgent]{role} Agent 就绪")

    async def execute_astream(
        self,
        query: str,
        thread_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """异步流式接口（FastAPI SSE 使用）"""
        config = {"configurable": {"thread_id": thread_id or "default"}}

        try:
            async for event in self.agent.astream_events(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
                version="v2",
            ):
                kind = event.get("event")

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = getattr(chunk, "content", "")
                    if content:
                        yield content

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "未知工具")
                    yield f"\n__tool_start__:{tool_name}\n"

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

    async def test():
        customer_agent = ReactAgent(role="customer")

        print("\n=== 客户视角：重疾险等待期 ===")
        async for chunk in customer_agent.execute_astream("重疾险等待期是多久", thread_id="t1"):
            print(chunk, end="", flush=True)
        print()

        agent_agent = ReactAgent(role="agent")
        print("\n=== 客服视角：销售误导红线 ===")
        async for chunk in agent_agent.execute_astream("销售误导有哪些红线", thread_id="t2"):
            print(chunk, end="", flush=True)
        print()

    asyncio.run(test())
