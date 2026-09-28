"""Regression comparator for benchmarking RAG and IT Support performance across prompts, models, runbooks, and workflows."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from pydantic import BaseModel, Field

from evaluation.runners.eval_runner import EvalRunItemResult, EvalRunSummary


class MetricComparisonRow(BaseModel):
    """Row in the regression comparison table."""
    category: str
    metric: str
    baseline: float
    current: float
    difference: float
    status: str


class FailureCase(BaseModel):
    """Detailed diagnostic representation of an evaluation failure."""
    id: str
    question: str
    failure_category: str
    expected_outcome: str = ""
    actual_outcome: str = ""
    expected_answer: str = ""
    generated_answer: str = ""
    retrieved_context: str = ""
    retrieved_documents: List[str] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
    diagnosis: str



class RegressionComparator:
    """Compares baseline vs current evaluation runs and generates transparent failure analysis."""

    METRIC_DISPLAY_NAMES = {
        # Retrieval
        "recall@1": ("Retrieval", "Recall@1", True),
        "recall@3": ("Retrieval", "Recall@3", True),
        "recall@5": ("Retrieval", "Recall@5", True),
        "precision@1": ("Retrieval", "Precision@1", True),
        "precision@3": ("Retrieval", "Precision@3", True),
        "mrr": ("Retrieval", "MRR (Mean Reciprocal Rank)", True),
        "hit_rate@3": ("Retrieval", "Hit Rate@3", True),
        # Generation
        "answer_relevancy": ("Generation", "Answer Relevancy", True),
        "answer_correctness": ("Generation", "Answer Correctness", True),
        "faithfulness": ("Generation", "Faithfulness (Grounding)", True),
        "context_precision": ("Generation", "Context Precision", True),
        "context_recall": ("Generation", "Context Recall", True),
        # IT Support Workflow
        "intent_accuracy": ("IT Support", "Intent Accuracy", True),
        "runbook_selection_accuracy": ("IT Support", "Runbook Selection Accuracy", True),
        "runbook_completion_rate": ("IT Support", "Runbook Completion Rate", True),
        "ticket_creation_success_rate": ("IT Support", "Ticket Creation Success Rate", True),
        "ticket_classification_accuracy": ("IT Support", "Ticket Classification Accuracy", True),
        "duplicate_ticket_rate": ("IT Support", "Duplicate Ticket Rate", False),
        "tool_selection_accuracy": ("IT Support", "Tool Selection Accuracy", True),
        "escalation_accuracy": ("IT Support", "Escalation Accuracy", True),
        "escalation_rate": ("IT Support", "Escalation Rate", False),
        "unnecessary_escalation_rate": ("IT Support", "Unnecessary Escalation Rate", False),
        "missed_escalation_rate": ("IT Support", "Missed Escalation Rate", False),
        "unauthorized_blocking_rate": ("Security & RBAC", "Unauthorized Blocking Rate", True),
        # Operational
        "retrieval_latency_ms": ("Operational", "Retrieval Latency (ms)", False),
        "generation_latency_ms": ("Operational", "Generation Latency (ms)", False),
        "total_latency_ms": ("Operational", "Total Latency (ms)", False),
        "prompt_tokens": ("Operational", "Avg Prompt Tokens", False),
        "completion_tokens": ("Operational", "Avg Completion Tokens", False),
        "total_tokens": ("Operational", "Avg Total Tokens", False),
        "estimated_cost_usd": ("Operational", "Cost per Query ($)", False),
    }

    def __init__(
        self,
        baseline_summary_or_path: Union[str, Path, EvalRunSummary],
        current_summary_or_path: Union[str, Path, EvalRunSummary],
        min_correctness: float = 0.60,
        min_faithfulness: float = 0.70,
        min_recall: float = 0.50,
        max_latency_ms: float = 5000.0,
    ):
        self.baseline = self._load_summary(baseline_summary_or_path)
        self.current = self._load_summary(current_summary_or_path)
        self.min_correctness = min_correctness
        self.min_faithfulness = min_faithfulness
        self.min_recall = min_recall
        self.max_latency_ms = max_latency_ms

    def _load_summary(self, target: Union[str, Path, EvalRunSummary]) -> EvalRunSummary:
        if isinstance(target, EvalRunSummary):
            return target
        path = Path(target)
        if not path.exists():
            raise FileNotFoundError(f"Evaluation summary file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return EvalRunSummary.model_validate(data)

    def compute_metric_table(self) -> List[MetricComparisonRow]:
        """Generate structured comparison table across RAG and IT support metrics."""
        rows: List[MetricComparisonRow] = []
        b_means = {**self.baseline.mean_metrics, **getattr(self.baseline, "it_metrics", {})}
        c_means = {**self.current.mean_metrics, **getattr(self.current, "it_metrics", {})}

        for key, (category, display_name, higher_is_better) in self.METRIC_DISPLAY_NAMES.items():
            if key not in b_means and key not in c_means:
                continue

            b_val = float(b_means.get(key, 0.0))
            c_val = float(c_means.get(key, 0.0))
            diff = c_val - b_val

            if higher_is_better:
                if diff >= 0.005:
                    status = "🟢 IMPROVED"
                elif diff <= -0.005:
                    status = "🔴 REGRESSED"
                else:
                    status = "⚪ UNCHANGED"
            else:
                threshold = 10.0 if "latency" in key else (0.0001 if "cost" in key else 0.005)
                if diff <= -threshold:
                    status = "🟢 IMPROVED"
                elif diff >= threshold:
                    status = "🔴 REGRESSED"
                else:
                    status = "⚪ UNCHANGED"

            rows.append(MetricComparisonRow(
                category=category,
                metric=display_name,
                baseline=round(b_val, 4),
                current=round(c_val, 4),
                difference=round(diff, 4),
                status=status,
            ))

        return rows

    def identify_failures(self) -> List[FailureCase]:
        """Detect structured failures across RAG, IT intents, runbooks, tickets, and security."""
        failures: List[FailureCase] = []

        for item in self.current.results:
            is_failure = False
            cat = ""
            diagnosis = ""

            # Check 1: System error
            if item.error:
                is_failure = True
                cat = "SYSTEM_ERROR"
                diagnosis = f"Execution raised exception: {item.error}"

            # Check 2: Unauthorized action violation
            elif item.is_unauthorized and not item.was_blocked:
                is_failure = True
                cat = "UNAUTHORIZED_ACTION"
                diagnosis = "Security controls failed to block unauthorized operation or privilege escalation."

            # Check 3: Retrieval Miss
            elif item.relevant_documents and item.retrieval_metrics.get("recall@3", 1.0) < self.min_recall:
                is_failure = True
                cat = "RETRIEVAL_MISS"
                diagnosis = (
                    f"Retriever failed to return expected documents. "
                    f"Expected: {item.relevant_documents} | Retrieved: {item.retrieved_documents}"
                )

            # Check 4: Intent classification error
            elif item.expected_intent and item.predicted_intent and item.expected_intent.upper() != item.predicted_intent.upper():
                is_failure = True
                cat = "WRONG_INTENT"
                diagnosis = f"Intent mismatch. Expected '{item.expected_intent}' but classified as '{item.predicted_intent}'."

            # Check 5: Runbook selection error
            elif item.expected_runbook and item.actual_runbook != item.expected_runbook:
                is_failure = True
                cat = "WRONG_RUNBOOK"
                diagnosis = f"Runbook mismatch. Expected '{item.expected_runbook}' but triggered '{item.actual_runbook}'."

            # Check 6: Tool invocation error
            elif item.expected_tools and not set(item.expected_tools).intersection(set(item.actual_tools)):
                is_failure = True
                cat = "WRONG_TOOL"
                diagnosis = f"Expected tools {item.expected_tools} were not invoked. Actual tools: {item.actual_tools}."

            # Check 7: Ticket type error
            elif item.expected_ticket_type and item.actual_ticket_type and str(item.actual_ticket_type).lower() != str(item.expected_ticket_type).lower():
                is_failure = True
                cat = "WRONG_TICKET_TYPE"
                diagnosis = f"Ticket category mismatch. Expected '{item.expected_ticket_type}' but created '{item.actual_ticket_type}'."

            # Check 8: Escalation error
            elif item.expected_escalation != item.actual_escalation:
                is_failure = True
                cat = "WRONG_ESCALATION"
                if item.expected_escalation:
                    diagnosis = "Missed escalation: Case required technician escalation but was kept in automated flow."
                else:
                    diagnosis = "Unnecessary escalation: Automated self-service was expected but query escalated."

            # Check 9: Grounding failure / Faithfulness
            elif (
                item.generation_metrics.get("faithfulness") is not None
                and item.generation_metrics["faithfulness"] < self.min_faithfulness
            ):
                is_failure = True
                cat = "GROUNDING_FAILURE"
                diagnosis = (
                    f"Generated claims not grounded in retrieved context "
                    f"(Faithfulness: {item.generation_metrics['faithfulness']:.2f} < {self.min_faithfulness:.2f})."
                )

            # Check 10: Latency Breach
            elif item.operational_metrics.get("total_latency_ms", 0.0) > self.max_latency_ms:
                is_failure = True
                cat = "LATENCY_BREACH"
                diagnosis = f"Total latency ({item.operational_metrics['total_latency_ms']:.1f}ms) exceeded SLA ({self.max_latency_ms:.1f}ms)."

            if is_failure:
                all_metrics = {}
                all_metrics.update(item.retrieval_metrics)
                all_metrics.update(item.generation_metrics)

                expected_out = item.expected_outcome or (f"Runbook {item.expected_runbook}" if item.expected_runbook else item.expected_answer or "Grounded answer")
                actual_out = item.actual_outcome or (f"Runbook {item.actual_runbook}" if item.actual_runbook else item.generated_answer or "No response")
                context_sample = " ".join(item.retrieved_contexts)

                failures.append(FailureCase(
                    id=item.id,
                    question=item.question,
                    failure_category=cat,
                    expected_outcome=expected_out,
                    actual_outcome=actual_out,
                    expected_answer=item.expected_answer or expected_out,
                    generated_answer=item.generated_answer or actual_out,
                    retrieved_context=context_sample or "[NO RETRIEVED CONTEXT]",
                    retrieved_documents=item.retrieved_documents,
                    metrics=all_metrics,
                    diagnosis=diagnosis,
                ))

        return failures

    def generate_markdown_report(self, output_path: Optional[Union[str, Path]] = None) -> str:
        """Produce GitHub-flavored Markdown regression report with full metric delta and failure analysis."""
        table_rows = self.compute_metric_table()
        failures = self.identify_failures()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines: List[str] = [
            f"# RAG Regression Evaluation Report",
            f"",
            f"> **Generated:** {timestamp}  ",
            f"> **Baseline Run:** `{self.baseline.run_name}` (`{self.baseline.run_id}`)  ",
            f"> **Current Run:** `{self.current.run_name}` (`{self.current.run_id}`)  ",
            f"> **Dataset:** `{self.current.dataset_name}` (`{self.current.dataset_version}`) | Cases: {self.current.total_cases}  ",

            f"",
            f"---",
            f"",
            f"## 1. Executive Summary & Quality Delta",
            f"",
            f"| Category | Metric | Baseline | Current | Difference | Status |",
            f"|---|---|---|---|---|---|",
        ]

        for r in table_rows:
            diff_str = f"+{r.difference:.4f}" if r.difference > 0 else f"{r.difference:.4f}"
            lines.append(f"| {r.category} | **{r.metric}** | {r.baseline:.4f} | {r.current:.4f} | `{diff_str}` | {r.status} |")

        # Failure Analysis section
        lines.extend([
            f"",
            f"---",
            f"",
            f"## 2. Failure Analysis (Zero Cherry-Picking)",
            f"",
            f"> [!WARNING]",
            f"> Production evaluations transparently report all sub-par executions across retrieval, intents, runbooks, tickets, and security.",
            f"> Total Detected Failure Cases: **{len(failures)} / {self.current.total_cases}**",
            f"",
        ])

        if not failures:
            lines.append("🎉 **No quality regressions or failure cases detected against thresholds!**\n")
        else:
            for idx, f in enumerate(failures, start=1):
                lines.extend([
                    f"### Case {idx:02d}: {f.id} — `{f.failure_category}`",
                    f"- **Question:** *\"{f.question}\"*",
                    f"- **Diagnosis:** {f.diagnosis}",
                    f"- **Expected Outcome:** *\"{f.expected_outcome}\"*",
                    f"- **Actual Outcome:** *\"{f.actual_outcome}\"*",
                    f"",
                    f"<details><summary>Retrieved Context Snippet</summary>",
                    f"",
                    f"```text",
                    f"{f.retrieved_context}",
                    f"```",
                    f"</details>",
                    f"",
                ])

        lines.extend([
            f"---",
            f"",
            f"## 3. SLA & Quality Thresholds",
            f"- **Recall Threshold:** $\\ge {self.min_recall:.2f}$",
            f"- **Faithfulness Threshold:** $\\ge {self.min_faithfulness:.2f}$",
            f"- **Correctness Threshold:** $\\ge {self.min_correctness:.2f}$",
            f"- **Latency SLA:** $\\le {self.max_latency_ms:.0f}$ ms",
            f"",
        ])

        content = "\n".join(lines)

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Regression report written to: {p}")

        return content


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compare two evaluation runs and produce regression report.")
    parser.add_argument("--baseline", required=True, help="Path to baseline evaluation JSON run")
    parser.add_argument("--current", required=True, help="Path to current evaluation JSON run")
    parser.add_argument("--output", default="evaluation/reports/it_support_regression_report.md", help="Output markdown report path")
    args = parser.parse_args()

    comparator = RegressionComparator(
        baseline_summary_or_path=args.baseline,
        current_summary_or_path=args.current,
    )
    report_text = comparator.generate_markdown_report(output_path=args.output)
    if not args.output:
        print(report_text)


if __name__ == "__main__":
    main()
