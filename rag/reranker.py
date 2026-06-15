"""
Rerank 精排服务：调用 DashScope gte-rerank-v2 对召回结果做精排。

设计要点：
1. 失败降级：rerank 异常时返回原向量结果（fallback_on_error=true），保证线上可用
2. 配置驱动：开关、模型、top_n 全在 config/rag.yml
3. 不破坏 metadata：只调整顺序，文档对象原样返回
"""
from typing import List
from http import HTTPStatus

import dashscope
from langchain_core.documents import Document

from utils.config_handler import rag_conf
from utils.logger_handler import logger


class RerankService:
    def __init__(self):
        self.conf = rag_conf.get("rerank", {})
        self.enabled = self.conf.get("enabled", False)
        self.model = self.conf.get("model", "gte-rerank-v2")
        self.top_n = self.conf.get("top_n", 3)
        self.fallback_on_error = self.conf.get("fallback_on_error", True)
        self.timeout = self.conf.get("timeout", 5)

    def rerank(self, query: str, docs: List[Document]) -> List[Document]:
        """
        对召回的文档做精排。

        :param query: 用户查询
        :param docs: 向量召回的候选文档列表
        :return: 精排后保留 top_n 个文档（按相关性降序）
        """
        if not self.enabled:
            return docs[: self.top_n]

        if not docs:
            return docs

        # rerank 输入：纯文本列表（保留原 docs 顺序便于 index 映射）
        documents_text = [d.page_content for d in docs]

        try:
            resp = dashscope.TextReRank.call(
                model=self.model,
                query=query,
                documents=documents_text,
                top_n=self.top_n,
                return_documents=False,    # 不重复返回原文，节省带宽
                timeout=self.timeout,
            )

            if resp.status_code != HTTPStatus.OK:
                raise RuntimeError(
                    f"DashScope rerank 返回非 200: code={resp.code}, "
                    f"msg={resp.message}, request_id={resp.request_id}"
                )

            # 按 rerank 返回顺序重排原 docs
            results = resp.output["results"]
            reranked: List[Document] = []
            for item in results:
                idx = item["index"]
                doc = docs[idx]
                # 把相关度分数写入 metadata，便于上层做阈值过滤或调试
                doc.metadata["rerank_score"] = item.get("relevance_score")
                reranked.append(doc)

            logger.info(
                f"[Rerank]查询='{query[:30]}...' "
                f"候选={len(docs)} → 精排={len(reranked)} "
                f"top1_score={reranked[0].metadata.get('rerank_score'):.4f}"
                if reranked else f"[Rerank]结果为空"
            )
            return reranked

        except Exception as e:
            logger.error(f"[Rerank]精排失败：{str(e)}", exc_info=True)
            if self.fallback_on_error:
                logger.warning(f"[Rerank]降级到向量召回结果（前 {self.top_n} 条）")
                return docs[: self.top_n]
            raise


# 全局单例
rerank_service = RerankService()


if __name__ == "__main__":
    # 简单冒烟测试
    test_docs = [
        Document(page_content="重疾险的等待期通常是90天或180天。"),
        Document(page_content="医疗险的免赔额一般是1万元。"),
        Document(page_content="重疾险等待期内出险不赔付。"),
        Document(page_content="保险条款变更需要书面通知。"),
    ]
    result = rerank_service.rerank("重疾险等待期是多久", test_docs)
    for i, d in enumerate(result):
        print(f"[{i}] score={d.metadata.get('rerank_score')} | {d.page_content}")
