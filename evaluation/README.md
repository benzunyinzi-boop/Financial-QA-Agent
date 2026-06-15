# 保险助手 RAG 评测体系

## 评测组件

| 文件 | 用途 | 速度 | 成本 |
|------|------|------|------|
| `dataset.py` | 评测黄金集（35 题保险领域） | - | - |
| **`eval_retrieval.py`** | **轻量检索评测**（Hit@K / MRR） | 30s 完成 | 免费 |
| `run_full.py` | RAGAS 完整评测（4 维度） | 5-10min | 调 LLM 几十次 |
| `eval_only.py` | 复用已有结果跑 RAGAS | 2-3min | 调 LLM 几十次 |

## 推荐工作流

```
改 retriever / rerank / chunk 配置
      ↓
跑 eval_retrieval.py（30s）→ 看 Hit@K / MRR 是否提升
      ↓
改动有效 → 跑 run_full.py（10min）做 RAGAS 全维度评测
      ↓
对比前后报告，决定是否上线
```

## 数据集结构

35 题，4 个类别：

| 类别 | 占比 | 说明 |
|------|------|------|
| `knowledge_direct` | 40% | 直接命中条款（等待期/免赔额/犹豫期） |
| `multi_chunk` | 25% | 需综合多片段（险种对比、配置建议） |
| `out_of_scope` | 20% | 范围外/对抗（股票/天气/数学题） |
| `fuzzy_query` | 15% | 模糊口语化（"出险了怎么办"） |

## 快速开始

```bash
# 进入项目根目录
cd /opt/Financial-QA-Agent

# 1. 轻量检索评测（快速回归）
python -m evaluation.eval_retrieval

# 跑指定知识库
python -m evaluation.eval_retrieval --kb internal_kb

# 调严判定阈值（关键词命中数）
python -m evaluation.eval_retrieval --min_hits 3

# 2. RAGAS 全维度评测（4 个指标）
python -m evaluation.run_full

# 3. 复用已有 RAG 结果，只跑 RAGAS（省 LLM 调用）
python -m evaluation.eval_only
```

## 指标含义

### 检索评测（eval_retrieval.py）

- **Hit@K**：Top-K 召回结果中至少有 1 条相关，越高越好
- **MRR**（Mean Reciprocal Rank）：首条相关文档的倒数排名平均值，1.0 = 永远排第 1
- **first_rank**：首条相关文档的排名，越小越好
- **延迟 P50/P95**：中位数 / 95 分位数延迟

### RAGAS（run_full.py）

- **faithfulness**：答案与 context 的忠实度（不脑补）
- **answer_relevancy**：答案与问题的相关性
- **context_precision**：检索到的 context 精确度
- **context_recall**：检索到的 context 召回率

## 结果存放

`evaluation/results/`：
- `eval_retrieval_YYYYMMDD_HHMMSS.json` 检索评测报告
- `raw_YYYYMMDD_HHMMSS.json` RAG 原始结果（供 eval_only 复用）
- `ragas_YYYYMMDD_HHMMSS.csv` RAGAS 评分

## 持续改进

每次改动后跑 `eval_retrieval.py`，对比前后报告：

```bash
# 改之前
python -m evaluation.eval_retrieval > before.txt

# 改 config/rag.yml 或 retriever 代码

# 改之后
python -m evaluation.eval_retrieval > after.txt

# 对比
diff before.txt after.txt
```

**金标准**：每次改动 Hit@K 应该 ≥ 之前，MRR 应该 ≥ 之前。如果倒退说明改坏了。

## 扩展数据集

`dataset.py` 是 Python 列表，每条加一项即可：

```python
{
    "question": "新问题",
    "ground_truth": "标准答案（提取关键词用）",
    "category": "knowledge_direct",  # 4 选 1
}
```

建议保险线上后从真实用户提问中抽样补充黄金集，定期 review。
