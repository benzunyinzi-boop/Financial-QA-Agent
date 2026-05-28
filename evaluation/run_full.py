"""
完整 RAGAS 评估流程：collect (生成 RAG 结果) + eval (用 RAGAS 评估)
关键修复：
  - 用专用的评估 LLM (max_tokens=4096)，避免 LLMDidNotFinishException
  - max_workers=2，避免 DashScope 限速
  - timeout=180s
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# ===== 强制确保 API Key 加载 =====
assert os.getenv("DASHSCOPE_API_KEY"), "请先设置 DASHSCOPE_API_KEY 环境变量"

from datasets import Dataset
from langchain_openai import ChatOpenAI
from ragas import evaluate, RunConfig
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from rag.rag_service import RagSummarizeService
from model.factory import embed_model
from utils.config_handler import rag_conf
from evaluation.dataset import EVAL_DATASET


def collect():
    """Collect 阶段：调用 RAG，收集 question/answer/contexts"""
    print("=" * 60)
    print("📝 Step 1: Collect RAG 结果")
    print("=" * 60)

    rag_service = RagSummarizeService()

    # 验证向量库非空
    count = rag_service.vector_store.vector_store._collection.count()
    print(f"📚 向量库文档数: {count}")
    if count == 0:
        print("❌ 向量库为空！请先初始化")
        sys.exit(1)

    raw_data = []
    total = len(EVAL_DATASET)
    for i, item in enumerate(EVAL_DATASET):
        question = item["question"]
        print(f"[{i+1}/{total}] {question[:30]}...", end=" ", flush=True)

        try:
            docs = rag_service.retriever_docs(question)
            contexts = [d.page_content for d in docs]
            answer = rag_service.rag_summarize(question)

            print(f"✓ ({len(contexts)} contexts)")
            raw_data.append({
                "question": question,
                "ground_truth": item["ground_truth"],
                "answer": answer,
                "contexts": contexts,
                "category": item["category"],
            })
        except Exception as e:
            print(f"❌ {e}")
            raw_data.append({
                "question": question,
                "ground_truth": item["ground_truth"],
                "answer": f"[ERROR] {e}",
                "contexts": [],
                "category": item["category"],
            })

    # 立即存盘
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(output_dir, f"raw_{timestamp}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    # 统计
    empty_count = sum(1 for d in raw_data if len(d["contexts"]) == 0)
    print(f"\n💾 已保存: {raw_path}")
    print(f"📊 空 contexts: {empty_count}/{total}")

    return raw_data, timestamp


def evaluate_with_ragas(raw_data, timestamp):
    """RAGAS 评估阶段"""
    print("\n" + "=" * 60)
    print("📊 Step 2: RAGAS 评估")
    print("=" * 60)

    dataset = Dataset.from_dict({
        "question": [r["question"] for r in raw_data],
        "ground_truth": [r["ground_truth"] for r in raw_data],
        "answer": [r["answer"] for r in raw_data],
        "contexts": [r["contexts"] for r in raw_data],
    })

    # 评估专用 LLM：长超时 + 大 max_tokens
    eval_llm_raw = ChatOpenAI(
        model=rag_conf["chat_model_name"],
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0,
        timeout=180,
        max_tokens=4096,
        max_retries=3,
        streaming=False,
    )
    evaluator_llm = LangchainLLMWrapper(eval_llm_raw)
    evaluator_embeddings = LangchainEmbeddingsWrapper(embed_model)

    run_config = RunConfig(timeout=180, max_workers=2, max_retries=3)

    print("⏳ 评估中（约 15-30 分钟）...")
    eval_result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=run_config,
    )

    return eval_result


def report(eval_result, raw_data, timestamp):
    """打印报告 + 保存"""
    df = eval_result.to_pandas()
    df["category"] = [r["category"] for r in raw_data]
    df["question"] = [r["question"] for r in raw_data]

    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

    print("\n" + "=" * 60)
    print("📈 总体得分")
    print("=" * 60)
    overall = {}
    for m in metrics:
        if m not in df.columns:
            continue
        score = df[m].mean(skipna=True)
        overall[m] = score
        valid = df[m].notna().sum()
        if score == score:
            bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
            status = "✅" if score >= 0.7 else "⚠️" if score >= 0.5 else "❌"
            print(f"  {status} {m:25s} {bar} {score:.4f}  (有效: {valid}/{len(df)})")

    print("\n" + "=" * 60)
    print("📋 按场景分类")
    print("=" * 60)
    for cat in sorted(df["category"].unique()):
        cat_df = df[df["category"] == cat]
        print(f"\n  [{cat}] ({len(cat_df)} 条)")
        for m in metrics:
            if m in cat_df.columns:
                score = cat_df[m].mean(skipna=True)
                if score == score:
                    print(f"    {m:25s}: {score:.4f}")

    print("\n" + "=" * 60)
    print("🔍 低分样本（< 0.5）")
    print("=" * 60)
    for m in metrics:
        if m not in df.columns:
            continue
        low = df[df[m] < 0.5].sort_values(m)
        if len(low) > 0:
            print(f"\n  [{m}]")
            for _, row in low.head(8).iterrows():
                if row[m] == row[m]:
                    print(f"    [{row['category']:18s}] {row['question'][:35]:35s} ({row[m]:.2f})")

    # 保存
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    scores_path = os.path.join(output_dir, f"scores_{timestamp}.json")
    detail_path = os.path.join(output_dir, f"detail_{timestamp}.csv")

    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump({k: float(v) if v == v else None for k, v in overall.items()},
                  f, ensure_ascii=False, indent=2)
    df.to_csv(detail_path, index=False, encoding="utf-8-sig")

    print(f"\n💾 总体得分: {scores_path}")
    print(f"💾 详细结果: {detail_path}")

    return overall


def main():
    raw_data, timestamp = collect()
    eval_result = evaluate_with_ragas(raw_data, timestamp)
    report(eval_result, raw_data, timestamp)


if __name__ == "__main__":
    main()
