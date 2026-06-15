"""
Rerank 精排服务：调用 DashScope gte-rerank-v2 对召回结果做精排。

设计要点：
1. 失败降级：rerank 异常时返回原向量结果（fallback_on_error=true），保证线上可用
2. 配置驱动：开关、模型、top_n 全在 config/rag.yml
3. 不破坏 metadata：只调整顺序，文档对象原样返回
4. LRU 缓存：相同 (query + docs 内容) 命中缓存，省 API 调用
   - 缓存值仅存索引 + 分数，不存 Document 对象
   - 默认 256 条 LRU，evaluate 时反复跑同一题集能显著省钱
"""
import hashlib
from collections import OrderedDict
from typing import List, Tuple
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

        # LRU 缓存：key = hash(query + docs内容), value = List[(index, score)]
        self.cache_enabled = self.conf.get("cache_enabled", True)
        self.cache_size = self.conf.get("cache_size", 256)
        self._cache: "OrderedDict[str, List[Tuple[int, float]]]" = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0

    @staticmethod
    def _make_cache_key(query: str, docs_text: List[str]) -> str:
        """生成缓存 key：query + docs 内容的 MD5"""
        h = hashlib.md5()
        h.update(query.encode("utf-8"))
        h.update(b"\x00")
        for t in docs_text:
            h.update(t.encode("utf-8"))
            h.update(b"\x01")
        return h.hexdigest()

    def _cache_get(self, key: str):
        if not self.cache_enabled:
            return None
        cached = self._cache.get(key)
        if cached is not None:
            # LRU：访问后移到末尾
            self._cache.move_to_end(key)
            self._cache_hits += 1
            return cached
        self._cache_misses += 1
        return None

    def _cache_set(self, key: str, value: List[Tuple[int, float]]):
        if not self.cache_enabled:
            return
        self._cache[key] = value
        self._cache.move_to_end(key)
        # 容量上限淘汰最旧的
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def cache_stats(self) -> dict:
        total = self._cache_hits + self._cache_misses
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": self._cache_hits / total if total else 0.0,
            "size": len(self._cache),
            "capacity": self.cache_size,
        }

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

        documents_text = [d.page_content for d in docs]
        cache_key = self._make_cache_key(query, documents_text) if self.cache_enabled else None

        # 命中缓存：用缓存的 (index, score) 重建结果
        if cache_key:
            cached = self._cache_get(cache_key)
            if cached is not None:
                reranked = []
                for idx, score in cached:
                    if 0 <= idx < len(docs):
                        doc = docs[idx]
                        doc.metadata["rerank_score"] = score
                        reranked.append(doc)
                if reranked:
                    logger.info(
                        f"[Rerank]缓存命中 query='{query[:30]}...' "
                        f"返回 {len(reranked)} 条"
                    )
                    return reranked

        try:
            resp = dashscope.TextReRank.call(
                model=self.model,
                query=query,
                documents=documents_text,
                top_n=self.top_n,
                return_documents=False,
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
            cache_value: List[Tuple[int, float]] = []
            for item in results:
                idx = item["index"]
                score = item.get("relevance_score")
                doc = docs[idx]
                doc.metadata["rerank_score"] = score
                reranked.append(doc)
                cache_value.append((idx, score))

            # 写缓存
            if cache_key:
                self._cache_set(cache_key, cache_value)

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
    # 冒烟测试 + 缓存命中验证
    test_docs = [
        Document(page_content="重疾险的等待期通常是90天或180天。"),
        Document(page_content="医疗险的免赔额一般是1万元。"),
        Document(page_content="重疾险等待期内出险不赔付。"),
        Document(page_content="保险条款变更需要书面通知。"),
    ]

    print("=== 第 1 次（缓存 miss）===")
    result = rerank_service.rerank("重疾险等待期是多久", test_docs)
    for i, d in enumerate(result):
        print(f"[{i}] score={d.metadata.get('rerank_score')} | {d.page_content}")

    print()
    print("=== 第 2 次（应缓存命中）===")
    result = rerank_service.rerank("重疾险等待期是多久", test_docs)
    for i, d in enumerate(result):
        print(f"[{i}] score={d.metadata.get('rerank_score')} | {d.page_content}")

    print()
    print(f"缓存统计: {rerank_service.cache_stats()}")
