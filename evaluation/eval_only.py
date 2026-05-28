"""
仅评估版本：使用已经收集好的 RAG 结果直接跑 RAGAS（避免重复调 LLM 生成回答）
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

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

from model.factory import embed_model
from utils.config_handler import rag_conf


def main():
    # 加载已有的 RAG 结果
    raw_dir = os.path.join(os.path.dirname(__file__), "results")
    raw_files = sorted([f for f in os.listdir(raw_dir) if f.startswith("raw_")], reverse=True)
    if not raw_files:
        print("❌ 未找到 raw_*.json 文件，请先运行 run_ragas.py 生成结果")
        return

    raw_path = os.path.join(raw_dir, raw_files[0])
    print(f"📂 加载: {raw_path}")
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    print(f"📊 共 {len(raw_data)} 条样本")

    # 构造 dataset
    dataset = Dataset.from_dict({
        "question": [r["question"] for r in raw_data],
        "ground_truth": [r["ground_truth"] for r in raw_data],
        "answer": [r["answer"] for r in raw_data],
        "contexts": [r["contexts"] for r in raw_data],
    })

    # 评估专用的 LLM 实例：长超时 + 大 max_tokens（RAGAS 输出 JSON 比较长）
    eval_llm_raw = ChatOpenAI(
        model=rag_conf["chat_model_name"],
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0,         # 评估用 0 保证一致性
        timeout=180,           # 3 分钟超时
        max_tokens=4096,       # 长输出
        max_retries=3,
        streaming=False,
    )
    evaluator_llm = LangchainLLMWrapper(eval_llm_raw)
    evaluator_embeddings = LangchainEmbeddingsWrapper(embed_model)

    # 关键：低并发避免 DashScope 限速
    run_config = RunConfig(
        timeout=180,
        max_workers=2,
        max_retries=3,
    )

    print("🚀 开始评估（max_workers=2, timeout=180s, max_tokens=4096）...")
    eval_result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=run_config,
    )

    # 输出结果
    df = eval_result.to_pandas()
    df["category"] = [r["category"] for r in raw_data]
    df["question"] = [r["question"] for r in raw_data]

    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

    print("\n" + "=" * 60)
    print("📈 总体得分")
    print("=" * 60)
    overall = {}
    for m in metrics:
        if m in df.columns:
            score = df[m].mean(skipna=True)
            overall[m] = score
            valid = df[m].notna().sum()
            if score == score:  # not NaN
                bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
                status = "✅" if score >= 0.7 else "⚠️" if score >= 0.5 else "❌"
                print(f"  {status} {m:25s} {bar} {score:.4f}  (有效: {valid}/{len(df)})")
            else:
                print(f"  ⚠️ {m:25s} 全部失败")

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
                else:
                    print(f"    {m:25s}: 无有效数据")

    print("\n" + "=" * 60)
    print("🔍 低分样本")
    print("=" * 60)
    for m in metrics:
        if m not in df.columns:
            continue
        low = df[df[m] < 0.5].sort_values(m)
        if len(low) > 0:
            print(f"\n  [{m} < 0.5]")
            for _, row in low.head(8).iterrows():
                if row[m] == row[m]:
                    print(f"    [{row['category']:18s}] {row['question'][:35]:35s} ({row[m]:.2f})")

    # 保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    scores_path = os.path.join(output_dir, f"scores_{timestamp}.json")
    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump({k: float(v) if v == v else None for k, v in overall.items()},
                  f, ensure_ascii=False, indent=2)
    detail_path = os.path.join(output_dir, f"detail_{timestamp}.csv")
    df.to_csv(detail_path, index=False, encoding="utf-8-sig")
    print(f"\n💾 总体得分: {scores_path}")
    print(f"💾 详细结果: {detail_path}")


if __name__ == "__main__":
    main()
