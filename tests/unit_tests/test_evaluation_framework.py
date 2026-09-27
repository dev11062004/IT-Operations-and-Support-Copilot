"""Unit test suite for Phase 7: Production RAG Evaluation Framework.

Tests:
1. Retrieval metrics (Recall@K, Precision@K, MRR, Hit Rate)
2. Generation metrics (Relevancy, Correctness, Faithfulness, Context Precision/Recall)
3. Operational metrics (Latency tracking, token estimation, cost calculation)
4. Versioned benchmark dataset loading & schema validation
5. Regression comparison (Metric | Baseline | Current | Difference) & Failure Analysis
6. Production evaluation runner (retrieval-only & full modes)
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evaluation.datasets.loader import (
    BenchmarkDataset,
    BenchmarkItem,
    convert_excel_to_benchmark,
    load_benchmark_dataset,
)
from evaluation.metrics.generation import (
    compute_answer_correctness,
    compute_answer_relevancy,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
    compute_generation_metrics,
)
from evaluation.metrics.operational import (
    compute_cost_usd,
    estimate_tokens,
    extract_operational_metrics,
)
from evaluation.metrics.retrieval import (
    compute_hit_rate,
    compute_mrr,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_retrieval_metrics,
    normalize_doc_name,
)
from evaluation.reports.comparator import (
    FailureCase,
    MetricComparisonRow,
    RegressionComparator,
)
from evaluation.runners.eval_runner import (
    EvalRunItemResult,
    EvalRunSummary,
    ProductionEvalRunner,
)

# ============================================================================
# 1. RETRIEVAL METRICS TESTS
# ============================================================================


class TestRetrievalMetrics:
    """Verify Recall@K, Precision@K, MRR, and Hit Rate calculations."""

    def test_doc_normalization(self):
        """Document names are normalized across extensions, case, and unicode dashes."""
        assert normalize_doc_name("3 - Annual Leave.txt") == "3 annual leave"
        assert normalize_doc_name("2 \u2013 Expenses.pdf") == "2 expenses"
        assert normalize_doc_name("Remote_Working") == "remote working"

    def test_recall_at_k(self):
        """Recall@K calculates proportion of relevant documents found in top-K."""
        retrieved = [
            "3 - Annual Leave.txt",
            "1 - Remote Working.txt",
            "2 - Expenses.txt",
        ]
        relevant = ["3 - Annual Leave.txt", "4 - IT Security.txt"]

        # K=1: 1 hit out of 2 relevant
        assert compute_recall_at_k(retrieved, relevant, k=1) == 0.50
        # K=3: still 1 hit out of 2 relevant
        assert compute_recall_at_k(retrieved, relevant, k=3) == 0.50
        # If all relevant retrieved in top 2
        assert compute_recall_at_k(retrieved, ["3 - Annual Leave.txt"], k=1) == 1.0
        # Zero relevant docs retrieved
        assert (
            compute_recall_at_k(
                ["5 - Sustainability.txt"], ["3 - Annual Leave.txt"], k=1
            )
            == 0.0
        )

    def test_precision_at_k(self):
        """Precision@K calculates proportion of top-K results that are relevant."""
        retrieved = [
            "3 - Annual Leave.txt",
            "1 - Remote Working.txt",
            "2 - Expenses.txt",
        ]
        relevant = ["3 - Annual Leave.txt"]

        # K=1: 1 relevant / 1 retrieved = 1.0
        assert compute_precision_at_k(retrieved, relevant, k=1) == 1.0
        # K=2: 1 relevant / 2 retrieved = 0.50
        assert compute_precision_at_k(retrieved, relevant, k=2) == 0.50
        # K=3: 1 relevant / 3 retrieved = 0.3333...
        assert abs(compute_precision_at_k(retrieved, relevant, k=3) - 0.3333) < 0.01

    def test_mrr(self):
        """MRR computes reciprocal rank of the first relevant document."""
        # Rank 1 hit -> 1.0
        assert compute_mrr(["A.txt", "B.txt"], ["A.txt"]) == 1.0
        # Rank 2 hit -> 0.50
        assert compute_mrr(["Noise.txt", "A.txt"], ["A.txt"]) == 0.50
        # Rank 3 hit -> 0.3333
        assert (
            abs(compute_mrr(["Noise1.txt", "Noise2.txt", "A.txt"], ["A.txt"]) - 0.3333)
            < 0.01
        )
        # No hit -> 0.0
        assert compute_mrr(["Noise1.txt", "Noise2.txt"], ["A.txt"]) == 0.0

    def test_hit_rate(self):
        """Hit Rate is 1.0 if at least one relevant doc is in top-K, else 0.0."""
        retrieved = ["Noise.txt", "Relevant.txt", "Other.txt"]
        assert compute_hit_rate(retrieved, ["Relevant.txt"], k=1) == 0.0
        assert compute_hit_rate(retrieved, ["Relevant.txt"], k=2) == 1.0
        assert compute_hit_rate(retrieved, ["Missing.txt"], k=3) == 0.0

    def test_compute_all_retrieval_metrics(self):
        """Batch retrieval calculator generates all standard keys."""
        metrics = compute_retrieval_metrics(
            retrieved_docs=["DocA.txt", "DocB.txt"],
            relevant_docs=["DocA.txt"],
            k_list=(1, 3),
        )
        assert "recall@1" in metrics
        assert "recall@3" in metrics
        assert "precision@1" in metrics
        assert "mrr" in metrics
        assert "hit_rate@1" in metrics
        assert metrics["recall@1"] == 1.0
        assert metrics["mrr"] == 1.0


# ============================================================================
# 2. GENERATION METRICS TESTS
# ============================================================================


class TestGenerationMetrics:
    """Verify Faithfulness, Correctness, Relevancy, and Context Precision/Recall."""

    def test_faithfulness_grounded_answer(self):
        """Answer whose statements are supported by context achieves 1.0 faithfulness."""
        context = [
            "Full-time UK employees receive 25 days of paid annual leave each year."
        ]
        grounded_answer = (
            "In the UK, employees are entitled to 25 days of annual leave."
        )
        score = compute_faithfulness(grounded_answer, context)
        assert score == 1.0

    def test_faithfulness_detects_hallucination(self):
        """Answer making claims unsupported by context achieves low faithfulness score."""
        context = [
            "Remote work is permitted up to 3 days per week with line manager approval."
        ]
        hallucinated_answer = "Employees receive $10,000 for purchasing gold watches and 6 months off for Caribbean cruises."
        score = compute_faithfulness(hallucinated_answer, context)
        assert score < 0.40

    def test_faithfulness_refusal_standard(self):
        """A valid grounded refusal correctly scores 1.0 faithfulness."""
        refusal = "I couldn't find this information in the available policy content."
        assert compute_faithfulness(refusal, []) == 1.0

    def test_answer_correctness(self):
        """Answer agreeing with ground truth achieves high correctness score."""
        gt = "Passwords must be at least 12 characters long and changed every 90 days."
        pred = "You must change passwords every 90 days, and they must be at least 12 characters."
        score = compute_answer_correctness(pred, gt)
        assert score > 0.70

        # Numeric mismatch is penalized
        wrong_pred = "Passwords must be changed every 30 days and be 8 characters."
        wrong_score = compute_answer_correctness(wrong_pred, gt)
        assert wrong_score < 0.50

    def test_context_precision_and_recall(self):
        """Context precision measures signal-to-noise; recall measures fact coverage."""
        chunks = [
            "Employees receive 25 days of annual leave.",
            "Recycling bins are located on every floor.",
        ]
        gt = "25 days of annual leave."

        # 1 of 2 chunks contains the fact
        prec = compute_context_precision(chunks, gt)
        assert prec == 0.50

        # The context contains all facts
        rec = compute_context_recall(chunks, gt)
        assert rec >= 0.80

    def test_compute_generation_metrics_bundle(self):
        """Bundle computes all 5 generation metrics with valid bounds."""
        res = compute_generation_metrics(
            question="How many remote days are allowed?",
            generated_answer="Employees can work remotely up to 3 days per week.",
            ground_truth="Up to three days per week.",
            retrieved_contexts=[
                "Employees may work remotely up to three days per week."
            ],
        )
        assert 0.0 <= res["answer_relevancy"] <= 1.0
        assert 0.0 <= res["answer_correctness"] <= 1.0
        assert 0.0 <= res["faithfulness"] <= 1.0
        assert 0.0 <= res["context_precision"] <= 1.0
        assert 0.0 <= res["context_recall"] <= 1.0


# ============================================================================
# 3. OPERATIONAL METRICS TESTS
# ============================================================================


class TestOperationalMetrics:
    """Verify token estimation, cost calculation, and latency aggregation."""

    def test_estimate_tokens(self):
        """Token estimation provides reasonable positive counts."""
        text = "In the UK, how many days of annual leave do employees receive?"
        count = estimate_tokens(text)
        assert 10 <= count <= 20

    def test_compute_cost_usd(self):
        """Cost calculation accurately multiplies token usage by rate cards."""
        # 1,000,000 prompt tokens in gpt-4o-mini = $0.150
        cost = compute_cost_usd(
            model_name="gpt-4o-mini",
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        assert cost == 0.150

        # Small practical request: 500 prompt, 100 completion tokens
        small_cost = compute_cost_usd(
            model_name="gpt-4o-mini",
            prompt_tokens=500,
            completion_tokens=100,
            embedding_model="text-embedding-3-small",
            embedding_tokens=50,
        )
        assert small_cost > 0.0
        assert small_cost < 0.001

    def test_extract_operational_metrics(self):
        """Operational metrics assembler captures latencies and calculates cost."""
        op = extract_operational_metrics(
            query="Who must approve remote work?",
            generated_answer="Your line manager.",
            retrieval_latency_ms=45.2,
            model_latency_ms=180.5,
            total_latency_ms=235.0,
            context_text="Remote work must be approved by line managers.",
            model_name="gpt-4o-mini",
        )
        assert op.retrieval_latency_ms == 45.2
        assert op.generation_latency_ms == 180.5
        assert op.total_latency_ms == 235.0
        assert op.prompt_tokens > 0
        assert op.completion_tokens > 0
        assert op.estimated_cost_usd > 0.0


# ============================================================================
# 4. DATASET LOADER TESTS
# ============================================================================


class TestDatasetLoader:
    """Verify versioned benchmark dataset loading and schema validation."""

    def test_load_canonical_v1_benchmark(self):
        """Canonical v1 benchmark loads cleanly with required schema fields."""
        dataset = load_benchmark_dataset("v1")
        assert isinstance(dataset, BenchmarkDataset)
        assert dataset.version == "v1.0"
        assert len(dataset) >= 10

        item = dataset[0]
        assert isinstance(item, BenchmarkItem)
        assert item.id.startswith("BENCH-")
        assert len(item.question) > 5
        assert len(item.expected_answer) > 0
        assert item.category in {
            "Annual Leave",
            "IT Security",
            "Expenses",
            "Remote Working",
            "Sustainability",
            "Out-of-Domain",
        }
        assert item.difficulty in {"easy", "medium", "hard"}

    def test_filter_by_category_and_difficulty(self):
        """BenchmarkDataset supports filtering by category or difficulty."""
        dataset = load_benchmark_dataset("v1")
        leave_items = dataset.filter_by_category("Annual Leave")
        assert len(leave_items) > 0
        assert all(it.category == "Annual Leave" for it in leave_items)

        easy_items = dataset.filter_by_difficulty("easy")
        assert len(easy_items) > 0
        assert all(it.difficulty == "easy" for it in easy_items)

    def test_dataset_to_dataframe(self):
        """Benchmark dataset converts cleanly to a pandas DataFrame."""
        dataset = load_benchmark_dataset("v1")
        df = dataset.to_dataframe()
        assert len(df) == len(dataset)
        assert "question" in df.columns
        assert "expected_answer" in df.columns
        assert "relevant_documents" in df.columns


# ============================================================================
# 5. REGRESSION COMPARATOR & FAILURE ANALYSIS TESTS
# ============================================================================


class TestRegressionComparator:
    """Verify metric delta calculations, failure categorization, and report formatting."""

    @pytest.fixture
    def mock_eval_summaries(self):
        """Create baseline and current EvalRunSummary objects."""
        item1 = EvalRunItemResult(
            id="BENCH-001",
            question="In the UK, how many days annual leave?",
            expected_answer="25 days",
            category="Annual Leave",
            difficulty="easy",
            relevant_documents=["3 - Annual Leave.txt"],
            retrieved_documents=["3 - Annual Leave.txt"],
            retrieved_contexts=["UK Employees receive 25 days leave."],
            generated_answer="UK employees receive 25 days annual leave.",
            decision="supported_by_evidence",
            retrieval_metrics={
                "recall@3": 1.0,
                "precision@3": 0.3333,
                "mrr": 1.0,
                "hit_rate@3": 1.0,
            },
            generation_metrics={
                "answer_correctness": 0.90,
                "faithfulness": 1.0,
                "answer_relevancy": 0.95,
            },
            operational_metrics={
                "total_latency_ms": 120.0,
                "estimated_cost_usd": 0.0002,
            },
        )
        # Failing item: low correctness and ungrounded
        item2_fail = EvalRunItemResult(
            id="BENCH-002",
            question="Can unused leave be carried over for EU employees?",
            expected_answer="Yes, up to 5 days.",
            category="Annual Leave",
            difficulty="easy",
            relevant_documents=["3 - Annual Leave.txt"],
            retrieved_documents=["1 - Remote Working.txt"],  # Retrieval miss!
            retrieved_contexts=["Remote work allowed 3 days."],
            generated_answer="Employees get unlimited holidays.",  # Hallucination!
            decision="insufficient_evidence",
            retrieval_metrics={
                "recall@3": 0.0,
                "precision@3": 0.0,
                "mrr": 0.0,
                "hit_rate@3": 0.0,
            },
            generation_metrics={
                "answer_correctness": 0.10,
                "faithfulness": 0.20,
                "answer_relevancy": 0.30,
            },
            operational_metrics={
                "total_latency_ms": 6000.0,
                "estimated_cost_usd": 0.0003,
            },
        )

        baseline = EvalRunSummary(
            run_id="run_baseline_01",
            run_name="baseline_v1",
            timestamp="2026-09-23T00:00:00",
            dataset_name="Test Benchmark",
            dataset_version="v1.0",
            mode="full",
            total_cases=2,
            successful_cases=2,
            error_cases=0,
            mean_metrics={
                "recall@3": 0.8000,
                "precision@3": 0.3000,
                "mrr": 0.8500,
                "answer_correctness": 0.7000,
                "faithfulness": 0.8500,
                "total_latency_ms": 250.0,
            },
            results=[item1],
        )

        current = EvalRunSummary(
            run_id="run_current_02",
            run_name="experiment_v2",
            timestamp="2026-09-23T01:00:00",
            dataset_name="Test Benchmark",
            dataset_version="v1.0",
            mode="full",
            total_cases=2,
            successful_cases=2,
            error_cases=0,
            mean_metrics={
                "recall@3": 0.5000,  # Regressed
                "precision@3": 0.3500,  # Improved
                "mrr": 0.8500,  # Unchanged
                "answer_correctness": 0.5000,  # Regressed
                "faithfulness": 0.6000,  # Regressed
                "total_latency_ms": 180.0,  # Improved (faster)
            },
            results=[item1, item2_fail],
        )

        return baseline, current

    def test_comparator_metric_differences(self, mock_eval_summaries):
        """Comparator accurately computes baseline, current, difference, and status indicators."""
        baseline, current = mock_eval_summaries
        comparator = RegressionComparator(baseline, current)
        rows = comparator.compute_metric_table()

        assert len(rows) > 0
        row_dict = {r.metric: r for r in rows}

        # Recall@3 regressed from 0.80 to 0.50 (-0.30)
        assert "Recall@3" in row_dict
        r3 = row_dict["Recall@3"]
        assert r3.baseline == 0.80
        assert r3.current == 0.50
        assert r3.difference == -0.30
        assert "REGRESSED" in r3.status

        # Total latency improved from 250ms to 180ms (-70ms)
        assert "Total Latency (ms)" in row_dict
        lat = row_dict["Total Latency (ms)"]
        assert lat.difference == -70.0
        assert "IMPROVED" in lat.status

    def test_comparator_identifies_all_failures(self, mock_eval_summaries):
        """Comparator catches underperforming questions and categorizes failures without cherry-picking."""
        baseline, current = mock_eval_summaries
        comparator = RegressionComparator(baseline, current)
        failures = comparator.identify_failures()

        assert len(failures) == 1
        f = failures[0]
        assert f.id == "BENCH-002"
        # Since recall was 0.0, category should be RETRIEVAL_MISS
        assert f.failure_category == "RETRIEVAL_MISS"
        assert "Expected: ['3 - Annual Leave.txt']" in f.diagnosis
        assert "unlimited holidays" in f.generated_answer

    def test_markdown_report_formatting(self, mock_eval_summaries):
        """Comparator renders GitHub-flavored Markdown with comparison table and failure details."""
        baseline, current = mock_eval_summaries
        comparator = RegressionComparator(baseline, current)
        report = comparator.generate_markdown_report()

        assert "# RAG Regression Evaluation Report" in report
        assert (
            "| Category | Metric | Baseline | Current | Difference | Status |" in report
        )
        assert "## 2. Failure Analysis (Zero Cherry-Picking)" in report
        assert "BENCH-002" in report
        assert "<details><summary>Retrieved Context Snippet</summary>" in report


# ============================================================================
# 6. PRODUCTION EVALUATION RUNNER TESTS
# ============================================================================


class TestProductionEvalRunner:
    """Verify evaluation runner execution modes."""

    @pytest.mark.asyncio
    async def test_runner_retrieval_only_mode(self):
        """Retrieval-only mode tests retriever without calling LLM generation."""
        mock_output = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.document_name = "3 - Annual Leave.txt"
        mock_chunk.content = "UK employees receive 25 days."
        mock_output.chunks = [mock_chunk]
        mock_output.retrieval_latency_ms = 15.0
        mock_output.error_message = None

        with patch(
            "evaluation.runners.eval_runner.search_policy_documents_typed",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = mock_output

            # Mini dataset
            mini_dataset = BenchmarkDataset(
                name="Mini Test",
                version="test",
                items=[
                    BenchmarkItem(
                        id="TEST-01",
                        question="How many days leave?",
                        expected_answer="25 days",
                        relevant_documents=["3 - Annual Leave.txt"],
                        category="Annual Leave",
                        difficulty="easy",
                    )
                ],
            )

            runner = ProductionEvalRunner(
                dataset_or_version=mini_dataset,
                mode="retrieval_only",
                top_k=3,
                run_name="unit_test_run",
            )
            summary = await runner.run_evaluation()

            assert summary.total_cases == 1
            assert summary.successful_cases == 1
            assert summary.error_cases == 0
            assert summary.mean_metrics["recall@3"] == 1.0
            assert summary.mean_metrics["hit_rate@3"] == 1.0
            assert (
                summary.results[0].generated_answer is None
            )  # no LLM call in retrieval_only mode
