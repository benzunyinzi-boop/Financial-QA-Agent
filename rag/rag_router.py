"""
RAG 路由：根据用户角色路由到不同的向量库。

- customer：仅检索 public_kb
- agent：先检索 internal_kb（命中弱时回退/合并 public_kb）
"""
from rag.rag_service import RagSummarizeService
from utils.logger_handler import logger


class RagRouter:
    """单例：避免每次调用重新加载向量库"""

    _instance = None

    ROLE_KB_MAP = {
        "customer": ["public_kb"],
        "agent": ["internal_kb", "public_kb"],
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        logger.info("[RagRouter]初始化双库 RAG 服务...")
        self._services: dict[str, RagSummarizeService] = {
            "public_kb": RagSummarizeService(kb_name="public_kb"),
            "internal_kb": RagSummarizeService(kb_name="internal_kb"),
        }
        self._initialized = True
        logger.info("[RagRouter]双库 RAG 服务就绪")

    def search(self, query: str, role: str) -> str:
        kbs = self.ROLE_KB_MAP.get(role, ["public_kb"])

        # 客户：仅查公开库
        if role == "customer":
            return self._services["public_kb"].rag_summarize(query)

        # 客服：先查内部库；若内部库检索结果为空或不足，再查公开库合并
        results = []
        for kb in kbs:
            try:
                summary = self._services[kb].rag_summarize(query)
                if summary and summary.strip():
                    results.append(f"【{kb}】\n{summary}")
            except Exception as e:
                logger.error(f"[RagRouter]{kb} 检索失败：{str(e)}", exc_info=True)
                continue

        if not results:
            return "未在知识库中检索到相关内容。"
        return "\n\n".join(results)

    def search_single_kb(self, query: str, kb_name: str) -> str:
        """直接指定 kb 检索，用于工具内部精确控制（如合规检查只查 internal_kb）"""
        if kb_name not in self._services:
            raise ValueError(f"未知知识库：{kb_name}")
        return self._services[kb_name].rag_summarize(query)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    router = RagRouter()

    print("\n=== customer 视角：重疾险等待期 ===")
    print(router.search("重疾险等待期是多久", role="customer"))

    print("\n=== agent 视角：销售误导红线 ===")
    print(router.search("销售误导有哪些红线", role="agent"))
