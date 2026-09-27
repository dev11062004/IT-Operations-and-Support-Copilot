# RAG Regression Evaluation Report

> **Generated:** 2026-09-23 09:28:01  
> **Baseline Run:** `baseline_v1_legacy` (`run_baseline_20260901`)  
> **Current Run:** `phase7_guardrails_optimized` (`run_phase7_current`)  
> **Dataset:** `Company XYZ Policy Benchmark` (`v1.0`) | Cases: 3  

---

## 1. Executive Summary & Quality Delta

| Category | Metric | Baseline | Current | Difference | Status |
|---|---|---|---|---|---|
| Retrieval | **Recall@1** | 0.6667 | 1.0000 | `+0.3333` | 🟢 IMPROVED |
| Retrieval | **Recall@3** | 0.6667 | 1.0000 | `+0.3333` | 🟢 IMPROVED |
| Retrieval | **Precision@1** | 0.6667 | 1.0000 | `+0.3333` | 🟢 IMPROVED |
| Retrieval | **Precision@3** | 0.2222 | 0.5555 | `+0.3333` | 🟢 IMPROVED |
| Retrieval | **MRR (Mean Reciprocal Rank)** | 0.6667 | 1.0000 | `+0.3333` | 🟢 IMPROVED |
| Retrieval | **Hit Rate@3** | 0.6667 | 1.0000 | `+0.3333` | 🟢 IMPROVED |
| Generation | **Answer Relevancy** | 0.7100 | 0.8933 | `+0.1833` | 🟢 IMPROVED |
| Generation | **Answer Correctness** | 0.6233 | 0.8900 | `+0.2667` | 🟢 IMPROVED |
| Generation | **Faithfulness (Grounding)** | 0.6667 | 0.9500 | `+0.2833` | 🟢 IMPROVED |
| Generation | **Context Precision** | 0.3333 | 0.6667 | `+0.3334` | 🟢 IMPROVED |
| Generation | **Context Recall** | 0.6667 | 1.0000 | `+0.3333` | 🟢 IMPROVED |
| Operational | **Retrieval Latency (ms)** | 30.0000 | 26.0000 | `-4.0000` | ⚪ UNCHANGED |
| Operational | **Generation Latency (ms)** | 760.0000 | 626.6000 | `-133.4000` | 🟢 IMPROVED |
| Operational | **Total Latency (ms)** | 790.0000 | 652.6000 | `-137.4000` | 🟢 IMPROVED |
| Operational | **Avg Prompt Tokens** | 421.6000 | 321.6000 | `-100.0000` | 🟢 IMPROVED |
| Operational | **Avg Completion Tokens** | 40.6000 | 38.3000 | `-2.3000` | ⚪ UNCHANGED |
| Operational | **Avg Total Tokens** | 462.3000 | 360.0000 | `-102.3000` | 🟢 IMPROVED |
| Operational | **Cost per Query ($)** | 0.0001 | 0.0001 | `-0.0000` | ⚪ UNCHANGED |

---

## 2. Failure Analysis (Zero Cherry-Picking)

> [!WARNING]
> Production evaluations must expose underperforming edge cases rather than selectively displaying successes.
> Total Detected Failure Cases: **0 / 3**

🎉 **No quality regressions or failure cases detected against thresholds!**

---

## 3. Evaluation Methodology & SLA Thresholds
- **Recall Threshold:** $\ge 0.50$
- **Faithfulness Threshold:** $\ge 0.70$
- **Correctness Threshold:** $\ge 0.60$
- **Latency SLA:** $\le 5000$ ms
