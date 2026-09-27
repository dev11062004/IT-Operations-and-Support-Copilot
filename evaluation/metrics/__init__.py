"""Evaluation metrics package: Retrieval, Generation, and Operational metrics."""

from evaluation.metrics.generation import (
    compute_answer_correctness,
    compute_answer_relevancy,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
    compute_generation_metrics,
)
from evaluation.metrics.operational import (
    MODEL_PRICING_PER_1M,
    OperationalMetrics,
    compute_cost_usd,
    estimate_tokens,
    extract_operational_metrics,
)
from evaluation.metrics.ragas_evaluator import (
    RAGAS_AVAILABLE,
    RAGASEvaluator,
)
from evaluation.metrics.retrieval import (
    compute_hit_rate,
    compute_mrr,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_retrieval_metrics,
    normalize_doc_name,
)

__all__ = [
    # Legacy & RAGAS
    "RAGASEvaluator",
    "RAGAS_AVAILABLE",
    # Retrieval
    "compute_recall_at_k",
    "compute_precision_at_k",
    "compute_mrr",
    "compute_hit_rate",
    "compute_retrieval_metrics",
    "normalize_doc_name",
    # Generation
    "compute_answer_relevancy",
    "compute_answer_correctness",
    "compute_faithfulness",
    "compute_context_precision",
    "compute_context_recall",
    "compute_generation_metrics",
    # Operational
    "OperationalMetrics",
    "MODEL_PRICING_PER_1M",
    "estimate_tokens",
    "compute_cost_usd",
    "extract_operational_metrics",
]
