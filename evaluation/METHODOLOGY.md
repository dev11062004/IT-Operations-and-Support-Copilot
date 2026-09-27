# Production RAG Evaluation Methodology & Limitations

## 1. Overview & Evaluation Philosophy

The objective of the **Phase 7 Production RAG Evaluation Framework** is to establish an objective, repeatable, and automated measurement system that decouples **retrieval quality** from **generation fidelity**, while tracking **operational efficiency** (latencies, token counts, and API costs).

In enterprise AI engineering, an answer can fail in three distinct layers:
1. **Retrieval Failure**: The search subsystem fails to locate the necessary source passages.
2. **Synthesis/Grounding Failure**: The retrieved passages contain the facts, but the LLM hallucinates ungrounded details or ignores the evidence.
3. **Operational Failure**: The system takes too long, exceeds token limits, or costs too much to sustain in production.

This framework measures all three layers independently, provides automated regression comparison across prompts/models, and strictly reports all failure cases without selective cherry-picking.

---

## 2. Mathematical Metric Formulations

### 2.1 Retrieval Metrics

Let:
- $\mathcal{R}$ be the set of ground-truth relevant documents for a given query.
- $\mathcal{C}_K = [d_1, d_2, \dots, d_K]$ be the ordered list of top-$K$ retrieved candidate documents.

#### Recall@K
The proportion of ground-truth relevant documents retrieved in the top-$K$ candidates:
$$\text{Recall@K} = \frac{|\mathcal{C}_K \cap \mathcal{R}|}{|\mathcal{R}|}$$
- **Range:** $[0.0, 1.0]$.
- **Target:** $\ge 0.85$ at $K=3$.

#### Precision@K
The proportion of retrieved top-$K$ documents that are truly relevant:
$$\text{Precision@K} = \frac{|\mathcal{C}_K \cap \mathcal{R}|}{K}$$
- **Range:** $[0.0, 1.0]$.
- **Target:** $\ge 0.60$ at $K=3$.

#### Mean Reciprocal Rank (MRR)
Measures the rank position of the first relevant document returned:
$$\text{RR} = \begin{cases} \frac{1}{\text{rank}_1} & \text{if } \exists d \in \mathcal{C} \text{ s.t. } d \in \mathcal{R} \\ 0.0 & \text{otherwise} \end{cases}$$
$$\text{MRR} = \frac{1}{N} \sum_{i=1}^N \text{RR}_i$$
- **Range:** $[0.0, 1.0]$.
- **Target:** $\ge 0.90$ (indicating the primary source document is almost always rank #1).

#### Hit Rate@K
Binary indicator of whether at least one relevant document was retrieved:
$$\text{Hit Rate@K} = \mathbb{I}(|\mathcal{C}_K \cap \mathcal{R}| > 0)$$
- **Range:** $0.0$ or $1.0$.
- **Target:** $\ge 0.95$ at $K=3$.

---

### 2.2 Generation Quality Metrics

#### Faithfulness (Grounding Fidelity)
Measures whether the claims in the generated response can be derived directly from the retrieved context passages (hallucination detection):
$$\text{Faithfulness} = \frac{|\text{Supported Claims in Answer}|}{|\text{Total Claims in Answer}|}$$
- If the agent emits a grounded refusal for missing information, Faithfulness is $1.0$.
- **Target:** $\ge 0.90$.

#### Answer Correctness
Measures the semantic and factual agreement between the generated answer and the ground-truth reference answer, combining token $F_1$ score with numerical exact match:
$$\text{Correctness} = 0.6 \cdot F_1(\text{Tokens}) + 0.4 \cdot \text{Accuracy}(\text{Numbers})$$
- **Target:** $\ge 0.70$.

#### Answer Relevancy
Measures how directly and concisely the answer addresses the specific user inquiry:
$$\text{Relevancy} = \frac{|\text{Query Concept Tokens} \cap \text{Answer Tokens}|}{|\text{Query Concept Tokens}|}$$
- **Target:** $\ge 0.85$.

#### Context Precision
Measures the signal-to-noise ratio in retrieved passages:
$$\text{Context Precision} = \frac{|\text{Retrieved Chunks with Ground Truth Evidence}|}{|\text{Total Retrieved Chunks}|}$$
- **Target:** $\ge 0.65$.

#### Context Recall
Measures whether all facts in the reference answer are present across the retrieved chunks:
$$\text{Context Recall} = \frac{|\text{Reference Facts Present in Context}|}{|\text{Total Reference Facts}|}$$
- **Target:** $\ge 0.85$.

---

### 2.3 Operational Metrics

#### Latencies
- $\text{Retrieval Latency } (T_{\text{ret}})$: Time spent executing vector search, full-text search, and RRF fusion (ms).
- $\text{Generation Latency } (T_{\text{gen}})$: Time spent waiting for LLM completion (ms).
- $\text{Total Latency } (T_{\text{tot}})$: Total roundtrip user latency ($T_{\text{ret}} + T_{\text{gen}} + \text{guardrails}$).

#### Cost Estimation
Calculated using token counts and model pricing tables:
$$\text{Cost} = \frac{\text{Prompt Tokens}}{10^6} \cdot P_{\text{input}} + \frac{\text{Completion Tokens}}{10^6} \cdot P_{\text{output}} + \frac{\text{Query Tokens}}{10^6} \cdot P_{\text{embed}}$$
For `gpt-4o-mini`:
- $P_{\text{input}} = \$0.150$ per 1M tokens
- $P_{\text{output}} = \$0.600$ per 1M tokens
- $P_{\text{embed}} = \$0.020$ per 1M tokens (`text-embedding-3-small`)

---

## 3. Benchmark Dataset Construction

The versioned evaluation dataset (`evaluation/datasets/v1_policy_benchmark.json`) contains:
- **Canonical In-Domain Questions**: Direct policy lookups across 5 core corporate domains (Annual Leave, IT Security, Expenses, Remote Working, Sustainability).
- **Multi-Hop / Comparative Questions**: Comparing policies across jurisdictions (e.g. UK vs EU vs US annual leave allowances).
- **Grounded Refusal Cases**: Negative controls asking for policies not in the corpus (maternity leave, personal holiday flights) where the agent MUST refuse.
- **Out-of-Domain Inquiries**: Non-policy queries (e.g. Python coding algorithms) that must trigger category C redirects without retrieval.

---

## 4. Regression Testing Protocol

To benchmark a proposed change (e.g. modifying system prompts, tweaking chunk size, changing rerankers, or updating model weights):
1. **Run Baseline**:
   ```bash
   python -m evaluation.runners.eval_runner --mode full --dataset v1 --run-name baseline_v1
   ```
2. **Run Current Experiment**:
   ```bash
   python -m evaluation.runners.eval_runner --mode full --dataset v1 --run-name prompt_update_v2
   ```
3. **Compare**:
   ```bash
   python -m evaluation.reports.comparator --baseline evaluation/results/eval_run_<time>_baseline_v1.json --current evaluation/results/eval_run_<time>_prompt_update_v2.json --output evaluation/reports/regression_report.md
   ```
4. **Inspect Failure Analysis**: Review all cases classified under `RETRIEVAL_MISS`, `LOW_FAITHFULNESS`, `INCORRECT_ANSWER`, `CITATION_FABRICATION`, or `LATENCY_BREACH`.

---

## 5. Known Limitations & Engineering Boundaries

1. **No Absolute Zero Hallucination**: No evaluation metric or guardrail can mathematically guarantee 0% hallucination across open-ended natural language generation.
2. **Lexical Overlap vs. Deep Semantic Paraphrase**: Factual token overlap checks are reliable for numbers, policy limits, dates, and names, but may slightly under-score completely paraphrased answers.
3. **LLM Judge Non-Determinism**: When using LLM-as-a-judge (RAGAS `gpt-4o-mini`), run-to-run metric variance of $\pm 2\%$ is expected even at `temperature=0.0`.
4. **Evaluation Thread Isolation**: Each evaluation question receives an isolated `eval_<uuid>` thread ID to guarantee that multi-turn session memory does not pollute independent benchmark test cases.
