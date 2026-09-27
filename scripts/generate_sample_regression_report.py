"""Script to generate a sample baseline and current run, and execute the RegressionComparator."""

from datetime import datetime
from pathlib import Path
from evaluation.reports.comparator import RegressionComparator
from evaluation.runners.eval_runner import EvalRunItemResult, EvalRunSummary

def main():
    reports_dir = Path("evaluation/reports")
    results_dir = Path("evaluation/results")
    reports_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Baseline Run (Legacy prompt / configuration)
    baseline_items = [
        EvalRunItemResult(
            id="BENCH-001",
            question="In the UK, how many days of annual leave do employees receive?",
            expected_answer="Full-time UK employees receive 25 days of paid annual leave per year.",
            category="Annual Leave",
            difficulty="easy",
            relevant_documents=["3 - Annual Leave.txt"],
            relevant_chunks=["UK Employees: Full-time employees receive 25 days"],
            retrieved_documents=["3 - Annual Leave.txt"],
            retrieved_contexts=["UK Employees: Full-time employees receive 25 days of paid annual leave per year."],
            generated_answer="In the UK, full-time employees receive 25 days of paid annual leave per year. [Reference: 3 - Annual Leave.txt]",
            decision="supported_by_evidence",
            retrieval_metrics={"recall@1": 1.0, "recall@3": 1.0, "precision@1": 1.0, "precision@3": 0.3333, "mrr": 1.0, "hit_rate@3": 1.0},
            generation_metrics={"answer_relevancy": 0.88, "answer_correctness": 0.85, "faithfulness": 0.95, "context_precision": 0.50, "context_recall": 1.0},
            operational_metrics={"retrieval_latency_ms": 32.0, "generation_latency_ms": 750.0, "total_latency_ms": 782.0, "prompt_tokens": 420, "completion_tokens": 45, "total_tokens": 465, "estimated_cost_usd": 0.00009},
        ),
        EvalRunItemResult(
            id="BENCH-002",
            question="Can unused annual leave be carried over for EU employees?",
            expected_answer="Yes, EU employees may carry over up to 5 days of unused annual leave.",
            category="Annual Leave",
            difficulty="easy",
            relevant_documents=["3 - Annual Leave.txt"],
            relevant_chunks=["EU Employees: Up to 5 days unused leave can be carried over"],
            retrieved_documents=["3 - Annual Leave.txt"],
            retrieved_contexts=["EU Employees: Up to 5 days unused leave can be carried over."],
            generated_answer="EU employees are allowed to carry over up to 5 days of unused leave. [Reference: 3 - Annual Leave.txt]",
            decision="supported_by_evidence",
            retrieval_metrics={"recall@1": 1.0, "recall@3": 1.0, "precision@1": 1.0, "precision@3": 0.3333, "mrr": 1.0, "hit_rate@3": 1.0},
            generation_metrics={"answer_relevancy": 0.85, "answer_correctness": 0.82, "faithfulness": 0.90, "context_precision": 0.50, "context_recall": 1.0},
            operational_metrics={"retrieval_latency_ms": 28.0, "generation_latency_ms": 710.0, "total_latency_ms": 738.0, "prompt_tokens": 395, "completion_tokens": 42, "total_tokens": 437, "estimated_cost_usd": 0.000084},
        ),
        EvalRunItemResult(
            id="BENCH-013",
            question="What is the policy for parental and maternity leave?",
            expected_answer="I couldn't find this information in the available policy content.",
            category="Annual Leave",
            difficulty="medium",
            relevant_documents=[],
            relevant_chunks=[],
            retrieved_documents=["3 - Annual Leave.txt"],
            retrieved_contexts=["UK Employees: 25 days. EU Employees: 30 days."],
            generated_answer="Maternity leave is 12 weeks for mothers.",  # Hallucinated guess in baseline!
            decision="insufficient_evidence",
            retrieval_metrics={"recall@1": 0.0, "recall@3": 0.0, "precision@1": 0.0, "precision@3": 0.0, "mrr": 0.0, "hit_rate@3": 0.0},
            generation_metrics={"answer_relevancy": 0.40, "answer_correctness": 0.20, "faithfulness": 0.15, "context_precision": 0.0, "context_recall": 0.0},
            operational_metrics={"retrieval_latency_ms": 30.0, "generation_latency_ms": 820.0, "total_latency_ms": 850.0, "prompt_tokens": 450, "completion_tokens": 35, "total_tokens": 485, "estimated_cost_usd": 0.000088},
        ),
    ]

    baseline_summary = EvalRunSummary(
        run_id="run_baseline_20260901",
        run_name="baseline_v1_legacy",
        timestamp="2026-09-01T12:00:00",
        dataset_name="Company XYZ Policy Benchmark",
        dataset_version="v1.0",
        mode="full",
        total_cases=3,
        successful_cases=3,
        error_cases=0,
        mean_metrics={
            "recall@1": 0.6667,
            "recall@3": 0.6667,
            "precision@1": 0.6667,
            "precision@3": 0.2222,
            "mrr": 0.6667,
            "hit_rate@3": 0.6667,
            "answer_relevancy": 0.7100,
            "answer_correctness": 0.6233,
            "faithfulness": 0.6667,
            "context_precision": 0.3333,
            "context_recall": 0.6667,
            "retrieval_latency_ms": 30.0,
            "generation_latency_ms": 760.0,
            "total_latency_ms": 790.0,
            "prompt_tokens": 421.6,
            "completion_tokens": 40.6,
            "total_tokens": 462.3,
            "estimated_cost_usd": 0.000087,
        },
        results=baseline_items,
    )

    # 2. Current Run (With Phase 6 Guardrails & Phase 7 Optimization)
    current_items = [
        baseline_items[0],  # Item 1 is good
        baseline_items[1],  # Item 2 is good
        EvalRunItemResult(
            id="BENCH-013",
            question="What is the policy for parental and maternity leave?",
            expected_answer="I couldn't find this information in the available policy content.",
            category="Annual Leave",
            difficulty="medium",
            relevant_documents=[],
            relevant_chunks=[],
            retrieved_documents=[],
            retrieved_contexts=[],
            generated_answer="I couldn't find this information in the available policy content. Please consult Company XYZ HR or your manager for guidance.",
            decision="insufficient_evidence",
            retrieval_metrics={"recall@1": 1.0, "recall@3": 1.0, "precision@1": 1.0, "precision@3": 1.0, "mrr": 1.0, "hit_rate@3": 1.0},
            generation_metrics={"answer_relevancy": 0.95, "answer_correctness": 1.0, "faithfulness": 1.0, "context_precision": 1.0, "context_recall": 1.0},
            operational_metrics={"retrieval_latency_ms": 18.0, "generation_latency_ms": 420.0, "total_latency_ms": 438.0, "prompt_tokens": 150, "completion_tokens": 28, "total_tokens": 178, "estimated_cost_usd": 0.000039},
        ),
    ]

    current_summary = EvalRunSummary(
        run_id="run_phase7_current",
        run_name="phase7_guardrails_optimized",
        timestamp="2026-09-23T09:30:00",
        dataset_name="Company XYZ Policy Benchmark",
        dataset_version="v1.0",
        mode="full",
        total_cases=3,
        successful_cases=3,
        error_cases=0,
        mean_metrics={
            "recall@1": 1.0000,
            "recall@3": 1.0000,
            "precision@1": 1.0000,
            "precision@3": 0.5555,
            "mrr": 1.0000,
            "hit_rate@3": 1.0000,
            "answer_relevancy": 0.8933,
            "answer_correctness": 0.8900,
            "faithfulness": 0.9500,
            "context_precision": 0.6667,
            "context_recall": 1.0000,
            "retrieval_latency_ms": 26.0,
            "generation_latency_ms": 626.6,
            "total_latency_ms": 652.6,
            "prompt_tokens": 321.6,
            "completion_tokens": 38.3,
            "total_tokens": 360.0,
            "estimated_cost_usd": 0.000071,
        },
        results=current_items,
    )

    # Save JSON files
    base_file = results_dir / "eval_run_baseline.json"
    curr_file = results_dir / "eval_run_current.json"

    with open(base_file, "w", encoding="utf-8") as f:
        f.write(baseline_summary.model_dump_json(indent=2))
    with open(curr_file, "w", encoding="utf-8") as f:
        f.write(current_summary.model_dump_json(indent=2))

    # Compare
    comparator = RegressionComparator(baseline_summary, current_summary)
    report_md = comparator.generate_markdown_report(output_path=reports_dir / "sample_regression_report.md")
    print(f"Generated sample regression report successfully!")

if __name__ == "__main__":
    main()
