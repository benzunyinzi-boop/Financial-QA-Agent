"""
RAGAS 评估脚本
评估当前 RAG 系统的检索和生成质量

使用方法：
  cd /Users/zhaoyinyin/AI/LangChain-ReAct-Agent
  source venv/bin/activate
  pip install ragas datasets
  python evaluation/run_ragas.py

评估指标：
  - Faithfulness（忠实度）：回答是否基于检索内容
  - Answer Relevancy（回答相关性）：回答是否切题
  - Context Precision（上下文精确度）：检索结果中有用信息的比例
  - Context Recall（上下文召回率）：是否检索到了所有需要的信息
"""
import os
import sys
import json
from datetime import datetime

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datasets import Dataset
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
from model.factory import chat_model, embed_model
from evaluation.dataset import EVAL_DATASET


def collect_rag_results():
    """
    对评估数据集中的每个问题，执行 RAG 检索 + 生成，收集结果
    """
    print("初始化 RAG 服务...")
    rag_service = RagSummarizeService()

    results = {
        "question": [],
        "ground_truth": [],
        "answer": [],
        "contexts": [],
        "category": [],
    }

    total = len(EVAL_DATASET)
    for i, item in enumerate(EVAL_DATASET):
        question = item["question"]
        print(f"[{i+1}/{total}] 处理: {question[:30]}...")

        try:
            # 检索文档
            docs = rag_service.retriever_docs(question)
            contexts = [doc.page_content for doc in docs]

            # 生成回答
            answer = rag_service.rag_summarize(question)

            results["question"].append(question)
            results["ground_truth"].append(item["ground_truth"])
            results["answer"].append(answer)
            results["contexts"].append(contexts)
            results["category"].append(item["category"])

        except Exception as e:
            print(f"  ⚠️ 错误: {e}")
            results["question"].append(question)
            results["ground_truth"].append(item["ground_truth"])
            results["answer"].append(f"[ERROR] {str(e)}")
            results["contexts"].append([])
            results["category"].append(item["category"])

    # 立即把收集结果存盘，避免后续评估失败时丢失
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(output_dir, f"raw_{timestamp}.json")
    raw_data = []
    for i in range(len(results["question"])):
        raw_data.append({
            "question": results["question"][i],
            "ground_truth": results["ground_truth"][i],
            "answer": results["answer"][i],
            "contexts": results["contexts"][i],
            "category": results["category"][i],
        })
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    print(f"💾 RAG 结果已存盘: {raw_path}")

    return results


def run_evaluation(results: dict):
    """
    使用 RAGAS 框架评估 RAG 质量
    """
    print("\n" + "=" * 60)
    print("开始 RAGAS 评估...")
    print("=" * 60)

    # 构建 HuggingFace Dataset 格式
    dataset = Dataset.from_dict({
        "question": results["question"],
        "ground_truth": results["ground_truth"],
        "answer": results["answer"],
        "contexts": results["contexts"],
    })

    # 使用项目自己的 LLM 和 Embedding 做评估（避免额外依赖 OpenAI）
    evaluator_llm = LangchainLLMWrapper(chat_model)
    evaluator_embeddings = LangchainEmbeddingsWrapper(embed_model)

    # 关键：低并发 + 长超时，避免 DashScope 限速导致 TimeoutError
    run_config = RunConfig(
        timeout=180,
        max_workers=2,
        max_retries=3,
    )

    # 执行评估
    evaluation_result = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=run_config,
    )

    return evaluation_result


def print_report(evaluation_result, results: dict):
    """
    打印评估报告
    """
    print("\n")
    print("=" * 60)
    print("📊 RAG 评估报告")
    print("=" * 60)
    print(f"评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"评估样本数: {len(results['question'])}")
    print(f"RAG 配置: chunk_size=200, chunk_overlap=20, top_k=3")
    print(f"模型: qwen3-max, embedding: text-embedding-v4")
    print()

    # 转 DataFrame
    df = evaluation_result.to_pandas()

    # 计算总体得分（每列均值，忽略 NaN）
    metric_columns = [c for c in df.columns
                      if c in ["faithfulness", "answer_relevancy",
                               "context_precision", "context_recall"]]

    overall_scores = {}
    for col in metric_columns:
        overall_scores[col] = df[col].mean(skipna=True)

    print("📈 总体得分:")
    print("-" * 40)
    for metric, score in overall_scores.items():
        if score is None or (isinstance(score, float) and (score != score)):  # NaN 检查
            print(f"  ⚠️ {metric:25s}: 无有效数据")
            continue
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        status = "✅" if score >= 0.7 else "⚠️" if score >= 0.5 else "❌"
        print(f"  {status} {metric:25s} {bar} {score:.4f}")
    print()

    # 按类别统计
    print("📋 按场景分类统计:")
    print("-" * 40)
    df["question"] = results["question"]
    df["category"] = results["category"]

    for cat in sorted(set(results["category"])):
        cat_df = df[df["category"] == cat]
        print(f"\n  [{cat}] ({len(cat_df)} 条)")
        for col in metric_columns:
            mean_score = cat_df[col].mean(skipna=True)
            if mean_score is None or (isinstance(mean_score, float) and (mean_score != mean_score)):
                print(f"    {col:25s}: 无有效数据")
            else:
                print(f"    {col:25s}: {mean_score:.4f}")

    # 找出低分样本
    print("\n")
    print("🔍 低分样本（需要重点关注）:")
    print("-" * 40)
    for metric in metric_columns:
        low_scores = df[df[metric] < 0.5].sort_values(metric)
        if len(low_scores) > 0:
            print(f"\n  {metric} < 0.5 的问题:")
            for _, row in low_scores.head(5).iterrows():
                score = row[metric]
                if score == score:  # not NaN
                    print(f"    - [{row['category']}] {row['question'][:40]}... (score: {score:.2f})")

    return df, overall_scores


def save_results(evaluation_result, results: dict, df, overall_scores):
    """
    保存评估结果到文件
    """
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 保存总体得分
    scores = {k: float(v) if v == v else None for k, v in overall_scores.items()}  # NaN -> None
    scores["timestamp"] = timestamp
    scores["sample_count"] = len(results["question"])
    scores["config"] = {
        "chunk_size": 200,
        "chunk_overlap": 20,
        "top_k": 3,
        "model": "qwen3-max",
        "embedding": "text-embedding-v4",
    }

    scores_path = os.path.join(output_dir, f"scores_{timestamp}.json")
    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)
    print(f"\n💾 总体得分已保存: {scores_path}")

    # 保存详细结果
    detail_path = os.path.join(output_dir, f"detail_{timestamp}.csv")
    df.to_csv(detail_path, index=False, encoding="utf-8-sig")
    print(f"💾 详细结果已保存: {detail_path}")

    # 保存原始数据（含 contexts）
    raw_path = os.path.join(output_dir, f"raw_{timestamp}.json")
    raw_data = []
    for i in range(len(results["question"])):
        raw_data.append({
            "question": results["question"][i],
            "ground_truth": results["ground_truth"][i],
            "answer": results["answer"][i],
            "contexts": results["contexts"][i],
            "category": results["category"][i],
        })
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    print(f"💾 原始数据已保存: {raw_path}")


def main():
    print("=" * 60)
    print("🤖 扫地机器人智能客服 - RAG 质量评估")
    print("=" * 60)
    print()

    # Step 1: 收集 RAG 结果
    print("📝 Step 1: 收集 RAG 检索和生成结果...")
    results = collect_rag_results()
    print(f"✅ 完成，共 {len(results['question'])} 条")

    # Step 2: RAGAS 评估
    print("\n📊 Step 2: 运行 RAGAS 评估...")
    evaluation_result = run_evaluation(results)

    # Step 3: 打印报告
    df, overall_scores = print_report(evaluation_result, results)

    # Step 4: 保存结果
    save_results(evaluation_result, results, df, overall_scores)

    print("\n" + "=" * 60)
    print("✅ 评估完成！")
    print("=" * 60)

    # 给出优化建议
    print("\n💡 优化建议:")
    scores = {k: float(v) if v == v else 0 for k, v in overall_scores.items()}

    if scores.get("context_precision", 1) < 0.7:
        print("  - Context Precision 低：建议增加 Reranker 重排序，过滤无关检索结果")
    if scores.get("context_recall", 1) < 0.7:
        print("  - Context Recall 低：建议增大 Top-K（当前 3 → 5-8），或加 Query 改写")
    if scores.get("faithfulness", 1) < 0.8:
        print("  - Faithfulness 低：LLM 在编造内容，建议加强 prompt 约束或降低 temperature")
    if scores.get("answer_relevancy", 1) < 0.7:
        print("  - Answer Relevancy 低：回答跑题，检查 prompt 是否引导 LLM 聚焦问题")

    if all(v >= 0.8 for v in scores.values() if v > 0):
        print("  🎉 所有有效指标 >= 0.8，RAG 质量良好！")


if __name__ == "__main__":
    main()
