"""Production evaluation runner executing full, retrieval-only, or offline RAG benchmarks."""

import argparse
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from pydantic import BaseModel, Field

from evaluation.datasets.loader import BenchmarkDataset, BenchmarkItem, load_benchmark_dataset
from evaluation.metrics.generation import compute_generation_metrics
from evaluation.metrics.operational import extract_operational_metrics
from evaluation.metrics.retrieval import compute_retrieval_metrics
from mcp_rag_agent.agent.create_agent import create_rag_agent_instance
from mcp_rag_agent.agent.models import SearchDocumentsInput, SearchDocumentsOutput
from mcp_rag_agent.core.config import config
from mcp_rag_agent.mcp_server.tools import search_policy_documents_typed

logger = logging.getLogger("ProductionEvalRunner")


class EvalRunItemResult(BaseModel):
    """Evaluation result for an individual benchmark item."""
    id: str = Field(..., description="Benchmark item ID")
    question: str = Field(..., description="Evaluation question")
    expected_answer: str = Field(..., description="Ground truth reference answer")
    category: str = Field(..., description="Domain category")
    difficulty: str = Field(..., description="Difficulty rating")
    relevant_documents: List[str] = Field(default_factory=list, description="Ground truth relevant documents")
    relevant_chunks: List[str] = Field(default_factory=list, description="Ground truth relevant chunks")
    retrieved_documents: List[str] = Field(default_factory=list, description="Documents retrieved during search")
    retrieved_contexts: List[str] = Field(default_factory=list, description="Text chunks retrieved")
    generated_answer: Optional[str] = Field(None, description="Answer produced by the RAG agent")
    decision: Optional[str] = Field(None, description="Guardrail grounding decision taxonomy")
    # Metrics
    retrieval_metrics: Dict[str, float] = Field(default_factory=dict, description="Recall@K, Precision@K, MRR, HitRate")
    generation_metrics: Dict[str, float] = Field(default_factory=dict, description="Relevancy, correctness, faithfulness, context precision/recall")
    operational_metrics: Dict[str, Any] = Field(default_factory=dict, description="Latencies, token usage, cost")
    error: Optional[str] = Field(None, description="Error message if evaluation encountered a failure")


class EvalRunSummary(BaseModel):
    """Aggregated summary of an evaluation benchmark execution."""
    run_id: str = Field(..., description="Unique run identifier")
    run_name: str = Field("default", description="Human-readable run label")
    timestamp: str = Field(..., description="ISO 8601 execution timestamp")
    dataset_name: str = Field(..., description="Benchmark dataset name")
    dataset_version: str = Field(..., description="Benchmark dataset version")
    mode: str = Field("full", description="Evaluation mode: full, retrieval_only, or offline")
    total_cases: int = Field(0, description="Total number of evaluated test cases")
    successful_cases: int = Field(0, description="Number of test cases without execution errors")
    error_cases: int = Field(0, description="Number of failed test cases")
    mean_metrics: Dict[str, float] = Field(default_factory=dict, description="Averaged retrieval, generation, and latency metrics")
    results: List[EvalRunItemResult] = Field(default_factory=list, description="Per-item evaluation results")

    def to_dataframe(self) -> pd.DataFrame:
        """Flatten item results into a pandas DataFrame."""
        flat_records = []
        for r in self.results:
            row = {
                "id": r.id,
                "question": r.question,
                "category": r.category,
                "difficulty": r.difficulty,
                "expected_answer": r.expected_answer,
                "generated_answer": r.generated_answer,
                "decision": r.decision,
                "error": r.error,
            }
            # Flatten retrieval metrics
            for k, v in r.retrieval_metrics.items():
                row[f"retrieval_{k}"] = v
            # Flatten generation metrics
            for k, v in r.generation_metrics.items():
                row[f"generation_{k}"] = v
            # Flatten operational metrics
            for k, v in r.operational_metrics.items():
                row[f"operational_{k}"] = v
            flat_records.append(row)
        return pd.DataFrame(flat_records)


class ProductionEvalRunner:
    """Unified evaluation orchestrator for measuring retrieval and generation quality."""

    def __init__(
        self,
        dataset_or_version: Union[str, Path, BenchmarkDataset] = "v1",
        agent: Optional[Any] = None,
        top_k: int = 3,
        run_name: str = "eval_run",
        mode: str = "full",
        output_dir: Optional[Path] = None,
    ):
        """Initialize evaluation runner.

        Args:
            dataset_or_version: BenchmarkDataset instance, version name (e.g. 'v1'), or Path.
            agent: Optional pre-configured agent instance.
            top_k: Retrieval candidate limit (default: 3).
            run_name: Label for this evaluation run.
            mode: 'full' (end-to-end), 'retrieval_only' (retrieval metrics only), or 'offline'.
            output_dir: Directory where result artifacts are stored.
        """
        if isinstance(dataset_or_version, BenchmarkDataset):
            self.dataset = dataset_or_version
        else:
            self.dataset = load_benchmark_dataset(dataset_or_version)

        self._agent = agent
        self.top_k = top_k
        self.run_name = run_name
        self.mode = mode.lower()
        self.output_dir = output_dir or (Path("evaluation/results"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def get_agent(self) -> Any:
        """Lazily initialize agent instance."""
        if self._agent is None and self.mode == "full":
            self._agent = await create_rag_agent_instance()
        return self._agent

    async def evaluate_item_retrieval_only(self, item: BenchmarkItem) -> EvalRunItemResult:
        """Evaluate retrieval performance without executing LLM generation."""
        t_start = time.perf_counter()
        try:
            tool_input = SearchDocumentsInput(query=item.question, top_k=self.top_k)
            output: SearchDocumentsOutput = await search_policy_documents_typed(tool_input)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            retrieved_docs = [c.document_name for c in output.chunks if c.document_name]
            retrieved_chunks = [c.content for c in output.chunks]

            ret_metrics = compute_retrieval_metrics(
                retrieved_docs=retrieved_docs,
                relevant_docs=item.relevant_documents,
                k_list=(1, 3, 5),
            )

            op_metrics = {
                "retrieval_latency_ms": round(output.retrieval_latency_ms or latency_ms, 2),
                "generation_latency_ms": 0.0,
                "total_latency_ms": round(latency_ms, 2),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            }

            return EvalRunItemResult(
                id=item.id,
                question=item.question,
                expected_answer=item.expected_answer,
                category=item.category,
                difficulty=item.difficulty,
                relevant_documents=item.relevant_documents,
                relevant_chunks=item.relevant_chunks,
                retrieved_documents=retrieved_docs,
                retrieved_contexts=retrieved_chunks,
                generated_answer=None,
                decision=None,
                retrieval_metrics=ret_metrics,
                generation_metrics={},
                operational_metrics=op_metrics,
                error=output.error_message,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            return EvalRunItemResult(
                id=item.id,
                question=item.question,
                expected_answer=item.expected_answer,
                category=item.category,
                difficulty=item.difficulty,
                relevant_documents=item.relevant_documents,
                relevant_chunks=item.relevant_chunks,
                retrieved_documents=[],
                retrieved_contexts=[],
                generated_answer=None,
                decision="system_failure",
                retrieval_metrics={"recall@3": 0.0, "precision@3": 0.0, "mrr": 0.0, "hit_rate@3": 0.0},
                generation_metrics={},
                operational_metrics={"total_latency_ms": round(latency_ms, 2)},
                error=str(e),
            )

    async def evaluate_item_full(self, item: BenchmarkItem) -> EvalRunItemResult:
        """Evaluate full end-to-end RAG pipeline (retrieval + generation + operational)."""
        t_start = time.perf_counter()
        isolated_thread = f"eval_{uuid.uuid4().hex[:12]}"

        try:
            agent = await self.get_agent()
            response = await agent.ainvoke(
                {
                    "messages": [{"role": "user", "content": item.question}],
                    "thread_id": isolated_thread,
                },
                config={"configurable": {"thread_id": isolated_thread}},
            )

            total_elapsed_ms = (time.perf_counter() - t_start) * 1000.0

            # Extract generated answer
            messages = response.get("messages", [])
            final_msg = messages[-1] if messages else None
            generated_answer = str(getattr(final_msg, "content", "")) if final_msg else ""

            # Extract retrieved documents and chunks
            retrieved_doc_ids = response.get("retrieved_document_ids", [])
            retrieved_chunks: List[str] = []
            retrieved_docs: List[str] = []

            for msg in messages:
                content = str(getattr(msg, "content", ""))
                # If tool message, extract document names
                if hasattr(msg, "name") and msg.name in {"search_policy_documents", "search_documents"}:
                    retrieved_chunks.append(content)
                    import re
                    matches = re.findall(r"Document #\d+:\s*([^\(\n]+)", content)
                    for m in matches:
                        if m.strip() not in retrieved_docs:
                            retrieved_docs.append(m.strip())

            # If no docs extracted from tool content, fallback to retrieved_doc_ids
            if not retrieved_docs and retrieved_doc_ids:
                retrieved_docs = list(retrieved_doc_ids)

            decision = response.get("decision", "supported_by_evidence")
            ret_latency_ms = float(response.get("retrieval_latency_ms", 0.0))
            model_latency_ms = float(response.get("model_latency_ms", 0.0))

            # 1. Retrieval Metrics
            ret_metrics = compute_retrieval_metrics(
                retrieved_docs=retrieved_docs,
                relevant_docs=item.relevant_documents,
                k_list=(1, 3, 5),
            )

            # 2. Generation Metrics
            gen_metrics = compute_generation_metrics(
                question=item.question,
                generated_answer=generated_answer,
                ground_truth=item.expected_answer,
                retrieved_contexts=retrieved_chunks,
            )

            # 3. Operational Metrics
            op = extract_operational_metrics(
                query=item.question,
                generated_answer=generated_answer,
                retrieval_latency_ms=ret_latency_ms,
                model_latency_ms=model_latency_ms,
                total_latency_ms=total_elapsed_ms,
                context_text=" ".join(retrieved_chunks),
                model_name=config.model_name,
                embedding_model=config.embedding_model,
            )

            return EvalRunItemResult(
                id=item.id,
                question=item.question,
                expected_answer=item.expected_answer,
                category=item.category,
                difficulty=item.difficulty,
                relevant_documents=item.relevant_documents,
                relevant_chunks=item.relevant_chunks,
                retrieved_documents=retrieved_docs,
                retrieved_contexts=retrieved_chunks,
                generated_answer=generated_answer,
                decision=decision,
                retrieval_metrics=ret_metrics,
                generation_metrics=gen_metrics,
                operational_metrics=op.model_dump(),
                error=None,
            )

        except Exception as e:
            total_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            return EvalRunItemResult(
                id=item.id,
                question=item.question,
                expected_answer=item.expected_answer,
                category=item.category,
                difficulty=item.difficulty,
                relevant_documents=item.relevant_documents,
                relevant_chunks=item.relevant_chunks,
                retrieved_documents=[],
                retrieved_contexts=[],
                generated_answer="",
                decision="system_failure",
                retrieval_metrics={"recall@3": 0.0, "precision@3": 0.0, "mrr": 0.0, "hit_rate@3": 0.0},
                generation_metrics={"answer_relevancy": 0.0, "answer_correctness": 0.0, "faithfulness": 0.0, "context_precision": 0.0, "context_recall": 0.0},
                operational_metrics={"total_latency_ms": round(total_elapsed_ms, 2), "estimated_cost_usd": 0.0},
                error=str(e),
            )

    async def run_evaluation(self) -> EvalRunSummary:
        """Execute full evaluation loop over benchmark dataset and persist outputs."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"eval_{timestamp}_{uuid.uuid4().hex[:6]}"
        total = len(self.dataset)

        print("=" * 80)
        print(f"RUNNING RAG EVALUATION: '{self.run_name}' (Mode: {self.mode.upper()})")
        print(f"Dataset: {self.dataset.name} ({self.dataset.version}) | Test Cases: {total}")
        print("=" * 80)

        item_results: List[EvalRunItemResult] = []

        for idx, item in enumerate(self.dataset.items, start=1):
            print(f"[{idx:02d}/{total:02d}] Evaluating: {item.question[:65]}...")

            if self.mode == "retrieval_only":
                res = await self.evaluate_item_retrieval_only(item)
            else:
                res = await self.evaluate_item_full(item)

            item_results.append(res)

            # Log metric status
            if res.error:
                print(f"  ❌ ERROR: {res.error}")
            else:
                rec3 = res.retrieval_metrics.get("recall@3", 0.0)
                prec3 = res.retrieval_metrics.get("precision@3", 0.0)
                corr = res.generation_metrics.get("answer_correctness", None)
                faith = res.generation_metrics.get("faithfulness", None)
                gen_info = f" | Correctness: {corr:.2f} | Faithfulness: {faith:.2f}" if corr is not None else ""
                print(f"  ✓ Recall@3: {rec3:.2f} | Prec@3: {prec3:.2f}{gen_info}")

        # Compute aggregate mean metrics
        successful = [r for r in item_results if not r.error]
        mean_metrics: Dict[str, float] = {}

        if successful:
            # Aggregate retrieval metrics
            for k in ["recall@1", "recall@3", "recall@5", "precision@1", "precision@3", "precision@5", "mrr", "hit_rate@1", "hit_rate@3", "hit_rate@5"]:
                vals = [r.retrieval_metrics.get(k, 0.0) for r in successful if k in r.retrieval_metrics]
                if vals:
                    mean_metrics[k] = round(sum(vals) / len(vals), 4)

            # Aggregate generation metrics
            for k in ["answer_relevancy", "answer_correctness", "faithfulness", "context_precision", "context_recall"]:
                vals = [r.generation_metrics.get(k, 0.0) for r in successful if k in r.generation_metrics]
                if vals:
                    mean_metrics[k] = round(sum(vals) / len(vals), 4)

            # Aggregate operational metrics
            for k in ["retrieval_latency_ms", "generation_latency_ms", "total_latency_ms", "prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost_usd"]:
                vals = [float(r.operational_metrics.get(k, 0.0)) for r in successful if k in r.operational_metrics]
                if vals:
                    mean_metrics[k] = round(sum(vals) / len(vals), 4 if "cost" in k else 2)

        summary = EvalRunSummary(
            run_id=run_id,
            run_name=self.run_name,
            timestamp=timestamp,
            dataset_name=self.dataset.name,
            dataset_version=self.dataset.version,
            mode=self.mode,
            total_cases=total,
            successful_cases=len(successful),
            error_cases=total - len(successful),
            mean_metrics=mean_metrics,
            results=item_results,
        )

        # Persist JSON and CSV artifacts
        json_path = self.output_dir / f"eval_run_{timestamp}_{self.run_name}.json"
        csv_path = self.output_dir / f"eval_run_{timestamp}_{self.run_name}.csv"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, indent=2, ensure_ascii=False)

        summary.to_dataframe().to_csv(csv_path, index=False)

        print("\n" + "=" * 80)
        print("EVALUATION RUN COMPLETE")
        print(f"Results saved to:\n  JSON: {json_path}\n  CSV:  {csv_path}")
        print("=" * 80)

        return summary


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run Production RAG Evaluation Benchmark.")
    parser.add_argument("--dataset", default="v1", help="Dataset version or path (default: 'v1')")
    parser.add_argument("--mode", default="full", choices=["full", "retrieval_only", "offline"], help="Evaluation mode")
    parser.add_argument("--run-name", default="benchmark_run", help="Identifier tag for this run")
    parser.add_argument("--top-k", type=int, default=3, help="Top-K retrieval candidate cutoff")
    args = parser.parse_args()

    runner = ProductionEvalRunner(
        dataset_or_version=args.dataset,
        top_k=args.top_k,
        run_name=args.run_name,
        mode=args.mode,
    )
    asyncio.run(runner.run_evaluation())


if __name__ == "__main__":
    main()
