# Production RAG Evaluation Framework (Phase 7)

A modular, reproducible, and extensible evaluation harness for the MCP RAG Agent. Designed to defend retrieval and generation quality in production, track operational cost/latency, enforce regression baselines, and surface unbiased failure analyses.

---

## 1. Directory Structure

```
evaluation/
├── datasets/                       # Versioned benchmark datasets & schema
│   ├── __init__.py
│   ├── loader.py                   # BenchmarkItem, BenchmarkDataset models & loaders
│   └── v1_policy_benchmark.json    # Curated versioned golden benchmark (15 test cases)
├── metrics/                        # Quantitative metric evaluators
│   ├── __init__.py                 # Unified public API
│   ├── retrieval.py                # Recall@K, Precision@K, MRR, Hit Rate
│   ├── generation.py               # Faithfulness, Correctness, Relevancy, Context Prec/Recall
│   ├── operational.py              # Retrieval/Gen/Total latency, Token counts, Cost (USD)
│   └── ragas_evaluator.py          # Legacy RAGAS pipeline with graceful fallback
├── runners/                        # Test runners & evaluation execution
│   ├── __init__.py
│   └── eval_runner.py              # ProductionEvalRunner (full, retrieval_only, offline)
├── reports/                        # Regression comparisons & failure analysis
│   ├── __init__.py
│   ├── comparator.py               # RegressionComparator (Metric | Baseline | Current | Diff)
│   └── sample_regression_report.md # Generated sample regression artifact
├── METHODOLOGY.md                  # Comprehensive metric definitions & limitations
├── README.md                       # This documentation
├── metrics.py                      # Backward-compatible shim re-exporting RAGASEvaluator
├── answer_generator.py             # Legacy runner Phase 1
├── metrics_evaluator.py            # Legacy runner Phase 2
└── main.py                         # Legacy CLI entrypoint
```

---

## 2. Evaluation Tiers & Metrics

### A. Retrieval Metrics (`evaluation/metrics/retrieval.py`)
Measures the ranking quality and relevance of retrieved context against expected ground truth documents/chunks:
- **Recall@K**: Proportion of relevant documents successfully retrieved in top-$K$ candidates.
- **Precision@K**: Fraction of top-$K$ retrieved candidates that are actually relevant.
- **Mean Reciprocal Rank (MRR)**: Reciprocal rank ($\frac{1}{\text{rank}}$) of the first relevant retrieved document.
- **Hit Rate**: Binary indicator ($1$ or $0$) whether at least one relevant document was retrieved in top-$K$.

### B. Generation Metrics (`evaluation/metrics/generation.py`)
Measures factual grounding, correctness, and relevancy:
- **Faithfulness**: Verifies whether claims in the generated response are factually grounded in the retrieved context (detects hallucinations).
- **Answer Correctness**: Evaluates semantic agreement with the expected ground truth reference (weighted 50% token F1 + 50% exact numeric matching for strict policy adherence).
- **Answer Relevancy**: Assesses how directly and completely the response addresses the prompt.
- **Context Precision**: Signal-to-noise ratio evaluating whether relevant chunks are ranked higher in context than irrelevant ones.
- **Context Recall**: Ground truth coverage measuring whether the retrieved context contains all facts required to answer.

### C. Operational Metrics (`evaluation/metrics/operational.py`)
Tracks efficiency, resource consumption, and cost:
- **Retrieval Latency ($s$)**: Duration of vector/hybrid retrieval and reranking.
- **Generation Latency ($s$)**: Duration of LLM inference and guardrail checks.
- **Total Latency ($s$)**: End-to-end request duration.
- **Token Usage**: Prompt tokens, completion tokens, and total tokens.
- **Estimated Cost ($USD$)**: Calculated per-query using model rate cards (`gpt-4o-mini`, `gpt-4o`, `text-embedding-3-small`).

---

## 3. Versioned Benchmark Dataset

The Golden Benchmark is versioned in `evaluation/datasets/v1_policy_benchmark.json` and parsed via `evaluation.datasets.BenchmarkDataset`.

### Schema (`BenchmarkItem`)
```json
{
  "id": "bench_001",
  "question": "In the UK, how many days of annual leave do employees receive?",
  "expected_answer": "In the UK, full-time employees are entitled to 25 days of paid annual leave per year, plus public and bank holidays.",
  "relevant_documents": ["3 - Annual Leave.txt"],
  "relevant_chunks": ["annual leave entitlement uk 25 days"],
  "category": "leave_policy",
  "difficulty": "easy",
  "metadata": {"requires_numeric": true}
}
```

### Dataset Distribution (v1)
- **15 Total Test Cases**:
  - `leave_policy` (3 easy, 1 medium, 1 hard multi-hop)
  - `remote_work` (3 easy/medium)
  - `it_security` (2 easy/medium)
  - `travel_expenses` (2 easy)
  - `negative_control` / `refusal` (2 negative controls testing unmentioned policies like helicopter flights and maternity top-up)
  - `out_of_domain` (2 tests evaluating guardrails against off-topic/adversarial questions)

---

## 4. Running Evaluations

### CLI Execution

#### Full Evaluation Run
```bash
python -m evaluation.runners.eval_runner \
  --dataset evaluation/datasets/v1_policy_benchmark.json \
  --output evaluation/results/run_current.json \
  --mode full
```

#### Retrieval-Only Evaluation (No LLM generation cost)
```bash
python -m evaluation.runners.eval_runner \
  --dataset evaluation/datasets/v1_policy_benchmark.json \
  --output evaluation/results/retrieval_benchmark.json \
  --mode retrieval_only \
  --top-k 5
```

#### Offline Evaluation (Compute metrics on existing results)
```bash
python -m evaluation.runners.eval_runner \
  --dataset evaluation/datasets/v1_policy_benchmark.json \
  --output evaluation/results/scored_run.json \
  --mode offline
```

---

## 5. Regression Testing & Reporting

To compare a modified retriever, model, or prompt against a baseline:

```bash
python -m evaluation.reports.comparator \
  --baseline evaluation/results/baseline_run.json \
  --current evaluation/results/current_run.json \
  --output evaluation/reports/regression_report.md
```

### Sample Output Format

```markdown
| Metric | Baseline | Current | Difference | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Retrieval Recall@5** | 0.9000 | 0.9500 | +0.0500 | IMPROVED |
| **Retrieval Precision@5** | 0.4500 | 0.4800 | +0.0300 | IMPROVED |
| **Mean Reciprocal Rank (MRR)** | 0.8500 | 0.9200 | +0.0700 | IMPROVED |
| **Hit Rate** | 0.9500 | 1.0000 | +0.0500 | IMPROVED |
| **Faithfulness** | 0.9100 | 0.9400 | +0.0300 | IMPROVED |
| **Answer Correctness** | 0.8200 | 0.8800 | +0.0600 | IMPROVED |
| **Answer Relevancy** | 0.8900 | 0.9300 | +0.0400 | IMPROVED |
| **Retrieval Latency (s)** | 0.3500 | 0.3100 | -0.0400 | IMPROVED |
| **Generation Latency (s)** | 1.2000 | 1.1500 | -0.0500 | IMPROVED |
| **Total Latency (s)** | 1.5500 | 1.4600 | -0.0900 | IMPROVED |
| **Total Estimated Cost ($)** | $0.0034 | $0.0031 | -0.0003 | IMPROVED |
```

### Zero-Cherry-Picking Failure Analysis
The comparator automatically analyzes and categorizes every sub-optimal result:
- `RETRIEVAL_MISS`: No relevant documents retrieved.
- `LOW_RECALL`: Relevant document found, but missing key chunks.
- `HALLUCINATION`: Generated claims unsupported by retrieved context.
- `UNGROUNDED_REFUSAL`: Agent refused to answer even though context was available.
- `NUMERIC_MISMATCH`: Numeric values in answer differed from reference policy.
- `GUARDRAIL_BYPASS`: Out-of-scope query was answered rather than safely refused.
- `LATENCY_BREACH`: Request exceeded operational latency threshold.

---

## 6. Legacy RAGAS Runner Compatibility

The legacy two-phase pipeline (`main.py`, `answer_generator.py`, `metrics_evaluator.py`) is fully preserved:
```bash
python evaluation/main.py
```
If `ragas` is installed, it runs standard RAGAS evaluations. If `ragas` is unavailable (e.g. C-extension build issues on Python 3.14), the framework falls back seamlessly to the native evaluators in `evaluation.metrics.generation`.
