"""Unit tests for Phase 13-F IT Support evaluation dataset, metric formulas, and regression comparator."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from evaluation.datasets.loader import (
    ITBenchmarkDataset,
    ITBenchmarkItem,
    load_benchmark_dataset,
    load_it_benchmark_dataset,
)
from evaluation.metrics.it_metrics import ITMetricResult, compute_it_metrics
from evaluation.reports.comparator import RegressionComparator
from evaluation.runners.eval_runner import (
    EvalRunItemResult,
    EvalRunSummary,
    ProductionEvalRunner,
)


def test_it_benchmark_dataset_loading():
    """Verify that the 105-scenario IT support benchmark loads with correct typing."""
    benchmark_path = Path("evaluation/datasets/v1_it_support_benchmark.json")
    assert benchmark_path.exists(), "Benchmark file must exist"

    dataset = load_it_benchmark_dataset(benchmark_path)
    assert isinstance(dataset, ITBenchmarkDataset)
    assert len(dataset) >= 100
    assert dataset.name == "IT Operations & Support Benchmark"
    assert dataset.version == "v1.0"

    # Verify first item structured fields
    first = dataset[0]
    assert isinstance(first, ITBenchmarkItem)
    assert first.id == "IT-001"
    assert first.category == "NETWORK"
    assert first.intent == "VPN_ISSUE"
    assert "1 - Remote Working.txt" in first.expected_documents
    assert first.expected_runbook == "RB-NET-VPN-001"

    # Test filtering
    vpn_dataset = dataset.filter_by_intent("VPN_ISSUE")
    assert len(vpn_dataset) > 0
    for item in vpn_dataset:
        assert item.intent == "VPN_ISSUE"


def test_malformed_benchmark_handling():
    """Verify error handling when loading invalid or missing benchmark datasets."""
    with pytest.raises(FileNotFoundError):
        load_it_benchmark_dataset("non_existent_dataset.json")

    with NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
        tmp.write('{"name": "broken", "items": [{"id": "bad"}]}')
        tmp_path = tmp.name

    try:
        with pytest.raises(Exception):
            load_it_benchmark_dataset(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_compute_it_metrics_precision():
    """Verify mathematical exactness of all IT-specific evaluation metrics."""
    test_evaluations = [
        # Item 1: Perfect VPN self-service runbook completion
        {
            "id": "IT-001",
            "expected_intent": "VPN_ISSUE",
            "predicted_intent": "VPN_ISSUE",
            "expected_runbook": "RB-NET-VPN-001",
            "actual_runbook": "RB-NET-VPN-001",
            "runbook_status": "completed",
            "expected_tools": ["search_policy_documents"],
            "actual_tools": ["search_policy_documents"],
            "expected_ticket_type": None,
            "actual_ticket_created": False,
            "expected_escalation": False,
            "actual_escalation": False,
            "is_unauthorized": False,
            "was_blocked": False,
        },
        # Item 2: Hardware issue creating ticket and escalating
        {
            "id": "IT-002",
            "expected_intent": "HARDWARE_ISSUE",
            "predicted_intent": "HARDWARE_ISSUE",
            "expected_runbook": "RB-HDW-DSP-009",
            "actual_runbook": "RB-HDW-DSP-009",
            "runbook_status": "escalated",
            "expected_tools": ["search_policy_documents", "get_device_info"],
            "actual_tools": ["search_policy_documents", "get_device_info"],
            "expected_ticket_type": "HARDWARE",
            "actual_ticket_created": True,
            "actual_ticket_type": "HARDWARE",
            "is_duplicate_ticket": False,
            "expected_escalation": True,
            "actual_escalation": True,
            "is_unauthorized": False,
            "was_blocked": False,
        },
        # Item 3: Intent & Runbook mismatch, unnecessary escalation
        {
            "id": "IT-003",
            "expected_intent": "WIFI_ISSUE",
            "predicted_intent": "NETWORK_OTHER",
            "expected_runbook": "RB-NET-WIFI-002",
            "actual_runbook": "RB-NET-VPN-001",
            "runbook_status": "completed",
            "expected_tools": ["search_policy_documents"],
            "actual_tools": ["search_policy_documents"],
            "expected_ticket_type": None,
            "actual_ticket_created": False,
            "expected_escalation": False,
            "actual_escalation": True,  # Unnecessary escalation
            "is_unauthorized": False,
            "was_blocked": False,
        },
        # Item 4: Unauthorized attack scenario correctly blocked
        {
            "id": "IT-004",
            "expected_intent": "GENERAL_IT_QUESTION",
            "predicted_intent": "GENERAL_IT_QUESTION",
            "expected_runbook": None,
            "actual_runbook": None,
            "runbook_status": None,
            "expected_tools": [],
            "actual_tools": [],
            "expected_ticket_type": None,
            "actual_ticket_created": False,
            "expected_escalation": False,
            "actual_escalation": False,
            "is_unauthorized": True,
            "was_blocked": True,
        },
    ]

    metrics = compute_it_metrics(test_evaluations)

    # 3 correct intents out of 4 -> 0.75
    assert metrics["intent_accuracy"] == 0.75
    # 2 correct runbooks out of 3 expected -> 2/3 = 0.6667
    assert metrics["runbook_selection_accuracy"] == pytest.approx(0.6667, abs=1e-4)
    # 2 completed runbooks out of 3 triggered -> 2/3 = 0.6667
    assert metrics["runbook_completion_rate"] == pytest.approx(0.6667, abs=1e-4)
    # 1 ticket created out of 1 expected -> 1.0
    assert metrics["ticket_creation_success_rate"] == 1.0
    assert metrics["ticket_classification_accuracy"] == 1.0
    assert metrics["duplicate_ticket_rate"] == 0.0
    # Escalation accuracy: 3 correct decisions out of 4 cases -> 0.75
    assert metrics["escalation_accuracy"] == 0.75
    # Unnecessary escalation: 1 out of 3 non-escalation cases -> 1/3 = 0.3333
    assert metrics["unnecessary_escalation_rate"] == pytest.approx(0.3333, abs=1e-4)
    assert metrics["missed_escalation_rate"] == 0.0
    # Unauthorized blocking: 1 out of 1 -> 1.0
    assert metrics["unauthorized_blocking_rate"] == 1.0


@pytest.mark.asyncio
async def test_offline_eval_runner_execution():
    """Verify end-to-end execution of the production evaluation runner in offline mode."""
    dataset = load_it_benchmark_dataset(
        "evaluation/datasets/v1_it_support_benchmark.json"
    )
    # Take top 5 items for fast unit test
    sample_dataset = ITBenchmarkDataset(
        name="Sample IT",
        version="v1.0",
        items=dataset.items[:5],
    )

    runner = ProductionEvalRunner(
        dataset_or_version=sample_dataset,
        mode="offline",
        run_name="test_offline_run",
    )
    summary = await runner.run_evaluation()

    assert summary.total_cases == 5
    assert summary.successful_cases == 5
    assert summary.error_cases == 0
    assert "intent_accuracy" in summary.it_metrics
    assert "runbook_completion_rate" in summary.it_metrics
    assert "recall@3" in summary.mean_metrics


def test_regression_comparator_failure_detection():
    """Verify regression comparator classifies all 9 IT failure categories."""
    baseline = EvalRunSummary(
        run_id="base_01",
        run_name="baseline",
        timestamp="2026-09-28T00:00:00",
        dataset_name="IT Operations & Support Benchmark",
        dataset_version="v1.0",
        total_cases=2,
        successful_cases=2,
        error_cases=0,
        mean_metrics={
            "recall@3": 1.0,
            "faithfulness": 0.99,
            "answer_correctness": 0.90,
            "total_latency_ms": 100.0,
        },
        it_metrics={
            "intent_accuracy": 1.0,
            "runbook_selection_accuracy": 1.0,
            "escalation_accuracy": 1.0,
            "unauthorized_blocking_rate": 1.0,
        },
        results=[],
    )

    current_item_regressed = EvalRunItemResult(
        id="IT-REG-01",
        question="How do I connect to VPN?",
        expected_answer="Use Cisco AnyConnect",
        category="NETWORK",
        relevant_documents=["1 - Remote Working.txt"],
        retrieved_documents=[],  # Retrieval miss
        retrieval_metrics={"recall@3": 0.0},
        generation_metrics={"faithfulness": 0.50},  # Low faithfulness
        operational_metrics={"total_latency_ms": 6000.0},  # Latency breach
        expected_intent="VPN_ISSUE",
        predicted_intent="HARDWARE_ISSUE",  # Wrong intent
        expected_runbook="RB-NET-VPN-001",
        actual_runbook="RB-HDW-DSP-009",  # Wrong runbook
        expected_escalation=False,
        actual_escalation=True,  # Wrong escalation
        is_unauthorized=True,
        was_blocked=False,  # Unauthorized action allowed!
    )

    current = EvalRunSummary(
        run_id="curr_01",
        run_name="current",
        timestamp="2026-09-28T01:00:00",
        dataset_name="IT Operations & Support Benchmark",
        dataset_version="v1.0",
        total_cases=1,
        successful_cases=1,
        error_cases=0,
        mean_metrics={
            "recall@3": 0.0,
            "faithfulness": 0.50,
            "total_latency_ms": 6000.0,
        },
        it_metrics={
            "intent_accuracy": 0.0,
            "runbook_selection_accuracy": 0.0,
            "escalation_accuracy": 0.0,
            "unauthorized_blocking_rate": 0.0,
        },
        results=[current_item_regressed],
    )

    comparator = RegressionComparator(
        baseline_summary_or_path=baseline, current_summary_or_path=current
    )
    failures = comparator.identify_failures()
    assert len(failures) > 0

    report_md = comparator.generate_markdown_report()
    assert "# RAG Regression Evaluation Report" in report_md
    assert "Intent Accuracy" in report_md
    assert "🔴 REGRESSED" in report_md
