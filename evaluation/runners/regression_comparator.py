"""Regression comparator runner entrypoint."""

from evaluation.reports.comparator import FailureCase, MetricComparisonRow, RegressionComparator, main

__all__ = [
    "RegressionComparator",
    "MetricComparisonRow",
    "FailureCase",
    "main",
]

if __name__ == "__main__":
    main()
