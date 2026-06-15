"""
轻量检索评测：只评检索质量（不评 LLM 生成），快速回归测试
用法：
  python evaluation/eval_retrieval.py
  python evaluation/eval_retrieval.py --top_k 10

评测指标：
  - Hit@K        召回率（Top-K 里至少有 1 条相关）
  - MRR          首条相关文档的平均倒数排名
  - Recall@K     Top-K 里相关文档占总相关数的比例（这里近似为 hit）
  - 延迟统计      P50 / P95
  - 分类别统计    各 category 的 Hit@K

判定相关性的两种模式（默认 keyword）：
  - keyword：用 jieba 分词从 ground_truth 提取关键词，chunk 命中 ≥ N 个关键词即为相关（快、免费）
  - llm：调用 LLM 判断每条 chunk 是否相关（慢、有成本，但准确）

注意：out_of_scope 类（如"今天天气怎么样"）本来就不应该召回知识库，
故不计入整体 hit_rate / MRR 统计，仅在分类别报告里展示。
"""
import os
import sys
import time
import json
import argparse
import re
from datetime import datetime
from collections import defaultdict, Counter
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from evaluation.dataset import EVAL_DATASET
from rag.rag_service import RagSummarizeService
from utils.logger_handler import logger


# 停用词（保险领域 + 通用虚词）
STOPWORDS = {
    "通常", "可以", "一般", "如果", "包括", "进行", "对于", "建议", "需要",
    "不能", "保险", "公司", "保险公司", "保险合同", "合同", "本系统",
    "什么", "以及", "或者", "但是", "因为", "所以", "对应", "当", "时",
    "the", "and", "for", "with",
}

DIGIT_RE = re.compile(r"\d{2,}")


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """
    从 ground_truth 用 jieba 分词提取关键词。
    优先保留：长度≥2 的实词 + 数字（多见于"15 天"、"30 日"等保险数字）
    """
    import jieba

    # 1) jieba 分词
    tokens = [t.strip() for t in jieba.lcut(text) if t.strip()]
    candidates = [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]

    # 2) 单独抽取数字（jieba 切数字可能不稳定）
    nums = [n for n in DIGIT_RE.findall(text) if n not in STOPWORDS]

    all_tokens = candidates + nums

    # 3) 综合排序：(频次, 长度) — 长 token 信息密度高
    freq = Counter(all_tokens)
    ranked = sorted(freq.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
    return [t for t, _ in ranked[:top_n]]


def is_relevant_keyword(chunk: str, keywords: list[str], min_hits: int = 2) -> bool:
    """关键词命中数 ≥ min_hits 视为相关"""
    if not keywords:
        return False
    hits = sum(1 for kw in keywords if kw in chunk)
    return hits >= min_hits


def evaluate_one(question: str, ground_truth: str, docs: list, min_hits: int = 2) -> dict:
    """对单条 query 计算 Hit / MRR"""
    keywords = extract_keywords(ground_truth, top_n=10)

    relevances = [is_relevant_keyword(d.page_content, keywords, min_hits) for d in docs]

    hit = any(relevances)
    first_rank = next((i + 1 for i, r in enumerate(relevances) if r), 0)
    mrr = 1.0 / first_rank if first_rank > 0 else 0.0

    return {
        "hit": hit,
        "mrr": mrr,
        "first_rank": first_rank,
        "keywords": keywords,
        "relevances": relevances,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top_k", type=int, default=None,
                        help="召回数量，默认走 rag.yml 配置")
    parser.add_argument("--min_hits", type=int, default=2,
                        help="关键词命中阈值（≥N 个关键词视为相关）")
    parser.add_argument("--kb", type=str, default="public_kb",
                        help="知识库名（public_kb / internal_kb）")
    parser.add_argument("--output_dir", type=str,
                        default=os.path.join(os.path.dirname(__file__), "results"))
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 70)
    print(f"📊 轻量检索评测 - {args.kb}")
    print(f"   样本数: {len(EVAL_DATASET)} | 关键词阈值: {args.min_hits}")
    print("=" * 70)

    service = RagSummarizeService(kb_name=args.kb)
    count = service.vector_store.vector_store._collection.count()
    print(f"📚 向量库文档数: {count}")
    if count == 0:
        print("❌ 向量库为空！")
        sys.exit(1)
    print()

    results = []
    latencies = []
    cat_stats = defaultdict(lambda: {"hit": 0, "total": 0, "mrr_sum": 0.0})

    for i, item in enumerate(EVAL_DATASET):
        question = item["question"]
        ground_truth = item["ground_truth"]
        category = item.get("category", "unknown")

        t0 = time.time()
        try:
            docs = service.retriever_docs(question)
        except Exception as e:
            logger.error(f"[评测]检索失败 q={question}: {e}")
            docs = []
        latency = time.time() - t0
        latencies.append(latency)

        eval_result = evaluate_one(question, ground_truth, docs, args.min_hits)

        cat_stats[category]["total"] += 1
        if eval_result["hit"]:
            cat_stats[category]["hit"] += 1
        cat_stats[category]["mrr_sum"] += eval_result["mrr"]

        status = "✓" if eval_result["hit"] else "✗"
        print(f"[{i+1:>2}/{len(EVAL_DATASET)}] {status} "
              f"rank={eval_result['first_rank']} mrr={eval_result['mrr']:.2f} "
              f"lat={latency:.2f}s | {question[:30]}")

        results.append({
            "question": question,
            "category": category,
            "ground_truth": ground_truth,
            "hit": eval_result["hit"],
            "first_rank": eval_result["first_rank"],
            "mrr": eval_result["mrr"],
            "keywords": eval_result["keywords"],
            "latency": latency,
            "top_docs": [
                {
                    "rank": j + 1,
                    "relevant": eval_result["relevances"][j],
                    "score": d.metadata.get("rerank_score"),
                    "content": d.page_content[:200],
                    "source": d.metadata.get("source_file"),
                }
                for j, d in enumerate(docs)
            ],
        })

    # ========== 汇总指标（排除 out_of_scope）==========
    # out_of_scope 本来就不该召回，参与 hit_rate 会误导
    in_scope_results = [r for r in results if r["category"] != "out_of_scope"]
    in_scope_total = len(in_scope_results)
    in_scope_hits = sum(1 for r in in_scope_results if r["hit"])
    in_scope_mrr = mean(r["mrr"] for r in in_scope_results) if in_scope_results else 0.0

    print()
    print("=" * 70)
    print(f"📈 整体指标（排除 {len(results) - in_scope_total} 条 out_of_scope 题）")
    print("=" * 70)
    print(f"  Hit@K:    {in_scope_hits}/{in_scope_total} = {in_scope_hits/in_scope_total:.1%}")
    print(f"  MRR:      {in_scope_mrr:.3f}")
    print(f"  延迟 P50: {median(latencies):.2f}s")
    print(f"  延迟 P95: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}s")
    print(f"  延迟 平均: {mean(latencies):.2f}s")

    print()
    print("📊 分类别表现")
    print("-" * 70)
    print(f"  {'category':<22} {'hit':>10} {'rate':>8} {'mrr':>8}")
    print("-" * 70)
    for cat, stat in sorted(cat_stats.items()):
        rate = stat["hit"] / stat["total"] if stat["total"] else 0
        cat_mrr = stat["mrr_sum"] / stat["total"] if stat["total"] else 0
        marker = "  (期望低)" if cat == "out_of_scope" else ""
        print(f"  {cat:<22} {stat['hit']:>4}/{stat['total']:<5} "
              f"{rate:>7.1%} {cat_mrr:>8.3f}{marker}")

    # ========== 保存报告 ==========
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(args.output_dir, f"eval_retrieval_{timestamp}.json")

    summary = {
        "timestamp": timestamp,
        "kb": args.kb,
        "doc_count": count,
        "sample_count_total": len(results),
        "sample_count_in_scope": in_scope_total,
        "min_hits": args.min_hits,
        "metrics": {
            "hit_at_k": in_scope_hits / in_scope_total if in_scope_total else 0,
            "mrr": in_scope_mrr,
            "latency_p50": median(latencies),
            "latency_p95": sorted(latencies)[int(len(latencies) * 0.95)],
            "latency_avg": mean(latencies),
        },
        "by_category": {
            cat: {
                "total": stat["total"],
                "hit": stat["hit"],
                "rate": stat["hit"] / stat["total"] if stat["total"] else 0,
                "mrr": stat["mrr_sum"] / stat["total"] if stat["total"] else 0,
            }
            for cat, stat in cat_stats.items()
        },
        "details": results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print(f"📁 报告已保存: {report_path}")
    print()
    print("💡 用途：每次改 retriever / chunk / rerank 配置后跑一次，对比报告判断改动是否有效")


if __name__ == "__main__":
    main()
