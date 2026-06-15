"""
Hybrid Search 混合检索器：BM25（关键词） + 向量（语义）

设计要点：
1. 适用场景：保险产品名/条款编号这类关键词查询，BM25 命中准；
              自然语言（"我想知道理赔流程"）这类语义查询，向量准；
              两路加权融合，两类查询都有保底
2. 中文分词：使用 jieba（lcut），BM25 对中文按词项打分
3. 失败降级：BM25 构建/检索失败时，自动退化为纯向量检索（不影响可用性）
4. 限制：BM25 是内存索引，文档变更后需重启服务才会生效
"""
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

import jieba

from utils.logger_handler import logger


def chinese_tokenize(text: str) -> List[str]:
    """jieba 中文分词，过滤空白 token"""
    return [tok for tok in jieba.lcut(text) if tok.strip()]


class HybridRetriever:
    """
    封装向量 + BM25 的混合检索器，对外暴露 invoke(query) 方法
    """

    def __init__(
        self,
        vector_retriever: BaseRetriever,
        documents: List[Document],
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        bm25_top_k: int = 20,
        fallback_on_error: bool = True,
    ):
        self.vector_retriever = vector_retriever
        self.fallback_on_error = fallback_on_error
        self.bm25_enabled = False
        self.ensemble: Optional[EnsembleRetriever] = None

        if not documents:
            logger.warning(
                "[Hybrid]文档列表为空，BM25 索引未构建，将退化为纯向量检索"
            )
            return

        try:
            bm25 = BM25Retriever.from_documents(
                documents,
                preprocess_func=chinese_tokenize,
            )
            bm25.k = bm25_top_k

            self.ensemble = EnsembleRetriever(
                retrievers=[vector_retriever, bm25],
                weights=[vector_weight, bm25_weight],
            )
            self.bm25_enabled = True
            logger.info(
                f"[Hybrid]构建完成 文档数={len(documents)} "
                f"权重 向量={vector_weight} BM25={bm25_weight} "
                f"BM25_top_k={bm25_top_k}"
            )
        except Exception as e:
            logger.error(f"[Hybrid]BM25 构建失败：{str(e)}", exc_info=True)
            if not fallback_on_error:
                raise

    def invoke(self, query: str) -> List[Document]:
        """
        执行混合检索。BM25 失败时降级为纯向量检索。
        """
        if not self.bm25_enabled or self.ensemble is None:
            return self.vector_retriever.invoke(query)

        try:
            return self.ensemble.invoke(query)
        except Exception as e:
            logger.error(f"[Hybrid]混合检索失败：{str(e)}", exc_info=True)
            if self.fallback_on_error:
                logger.warning("[Hybrid]降级为纯向量检索")
                return self.vector_retriever.invoke(query)
            raise
