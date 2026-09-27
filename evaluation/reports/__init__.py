"""Evaluation reports and regression comparison package."""

from evaluation.reports.comparator import (
    FailureCase,
    MetricComparisonRow,
    RegressionComparator,
)

__all__ = [
    "RegressionComparator",
    "MetricComparisonRow",
    "FailureCase",
]
