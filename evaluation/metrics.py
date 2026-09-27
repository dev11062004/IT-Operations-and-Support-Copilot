"""Backward compatibility module for evaluation.metrics."""

from evaluation.metrics.ragas_evaluator import (
    RAGAS_AVAILABLE,
    RAGASEvaluator,
)

__all__ = ["RAGASEvaluator", "RAGAS_AVAILABLE"]
