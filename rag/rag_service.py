
"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复

检索链路：Hybrid Search（向量 + BM25） → Rerank 精排 → LLM 总结
两个能力均可通过 config/rag.yml 独立开关
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from rag.vector_store import VectorStoreService
from rag.reranker import rerank_service
from rag.hybrid_retriever import HybridRetriever
from utils.prompt_loader import load_rag_prompts
from utils.config_handler import rag_conf
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
from utils.logger_handler import logger


class RagSummarizeService(object):
    def __init__(self, kb_name: str = "public_kb"):
        self.kb_name = kb_name
        self.vector_store = VectorStoreService(kb_name=kb_name)

        # rerank 开启时，召回扩大到 retrieve_top_k；关闭时走默认 k
        self.rerank_conf = rag_conf.get("rerank", {})
        self.rerank_enabled = self.rerank_conf.get("enabled", False)
        retrieve_k = (
            self.rerank_conf.get("retrieve_top_k", 20)
            if self.rerank_enabled else None
        )

        # 构建检索器（hybrid 或 纯向量）
        self.retriever = self._build_retriever(retrieve_k)

        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self.prompt_template | self.model | StrOutputParser()

    def _build_retriever(self, retrieve_k):
        """根据配置构建 Hybrid 或纯向量 retriever"""
        vector_retriever = self.vector_store.get_retriever(k=retrieve_k)

        hybrid_conf = rag_conf.get("hybrid_search", {})
        if not hybrid_conf.get("enabled", False):
            return vector_retriever

        all_docs = self.vector_store.get_all_documents()
        return HybridRetriever(
            vector_retriever=vector_retriever,
            documents=all_docs,
            vector_weight=hybrid_conf.get("vector_weight", 0.6),
            bm25_weight=hybrid_conf.get("bm25_weight", 0.4),
            bm25_top_k=hybrid_conf.get("bm25_top_k", 20),
            fallback_on_error=hybrid_conf.get("fallback_on_error", True),
        )

    def retriever_docs(self, query: str) -> list[Document]:
        """
        召回 + rerank 精排（如果开启）。
        rerank 失败会自动降级到向量结果（见 RerankService.fallback_on_error）。
        """
        try:
            candidates = self.retriever.invoke(query)
        except Exception as e:
            if "no such table: collections" in str(e):
                logger.warning("[RAG检索]检测到chroma库异常，自动重建后重试一次")
                self.vector_store = VectorStoreService(kb_name=self.kb_name)
                retrieve_k = (
                    self.rerank_conf.get("retrieve_top_k", 20)
                    if self.rerank_enabled else None
                )
                self.retriever = self._build_retriever(retrieve_k)
                candidates = self.retriever.invoke(query)
            else:
                raise e

        if self.rerank_enabled:
            return rerank_service.rerank(query, candidates)
        return candidates

    def rag_summarize(self, query: str) -> str:

        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )


if __name__ == '__main__':
    rag = RagSummarizeService(kb_name="public_kb")

    print(rag.rag_summarize("重疾险等待期是多久"))
