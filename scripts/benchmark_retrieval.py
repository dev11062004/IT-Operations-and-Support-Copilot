"""Retrieval latency benchmarking script comparing baseline vs advanced retrieval."""

import asyncio
import statistics
import time
from unittest.mock import AsyncMock, MagicMock

from mcp_rag_agent.core.config import config
from mcp_rag_agent.retrieval.pipeline import AdvancedRetriever
from mcp_rag_agent.retrieval.reranker import NoOpReranker, CrossEncoderReranker


def create_mock_retrieval_environment(num_documents: int = 50):
    """Create a high-fidelity in-memory mock environment for deterministic latency benchmarking."""
    mock_mongo = MagicMock()
    mock_emb = MagicMock()
    mock_emb.generate = AsyncMock(return_value=[0.05] * 256)

    # Simulated candidate documents
    mock_docs = [
        {
            "_id": f"id_{i}",
            "chunk_id": f"doc_policy_c{i}",
            "document_id": "doc_policy",
            "name": "Company_Policy.docx",
            "content": f"Policy clause {i}: Employees may work remotely up to 3 days per week with manager approval.",
            "score": round(0.95 - (i * 0.01), 3),
            "text_score": round(15.0 - (i * 0.2), 2),
            "metadata": {
                "chunk_id": f"doc_policy_c{i}",
                "document_id": "doc_policy",
                "filename": "Company_Policy.docx",
                "section": f"Section {i // 5}",
                "page_number": (i // 10) + 1,
            }
        }
        for i in range(num_documents)
    ]

    mock_mongo.vector_search.side_effect = lambda **kwargs: mock_docs[:kwargs.get("limit", 10)]
    mock_mongo.text_search.side_effect = lambda **kwargs: mock_docs[:kwargs.get("limit", 10)]

    return mock_mongo, mock_emb


async def run_baseline_search(mock_mongo, mock_emb, query: str, top_k: int) -> float:
    """Simulate baseline retrieval without preprocessing, over-fetching, or stage metrics."""
    t0 = time.perf_counter()
    query_vec = await mock_emb.generate(query)
    vec_results = mock_mongo.vector_search(
        collection_name="vectors",
        index_name="vector_index",
        vector_field="embedding",
        query_vector=query_vec,
        limit=top_k,
    )
    kw_results = mock_mongo.text_search(
        collection_name="vectors",
        index_name="text_index",
        query_text=query,
        limit=top_k,
    )
    # Simple unweighted union
    seen = set()
    final = []
    for doc in vec_results + kw_results:
        cid = doc["_id"]
        if cid not in seen:
            seen.add(cid)
            final.append(doc)
            if len(final) == top_k:
                break
    t_total = (time.perf_counter() - t0) * 1000.0
    return t_total


async def run_advanced_search(retriever: AdvancedRetriever, query: str, top_k: int) -> tuple[float, dict]:
    """Run advanced retrieval pipeline with over-fetching, RRF fusion, and metrics."""
    result = await retriever.retrieve(query=query, top_k=top_k, debug=True)
    return result.latency.total_latency_ms, result.latency.model_dump()


async def main():
    print("=" * 70)
    print("MCP RAG Agent - Phase 3: Retrieval Latency Benchmark")
    print("=" * 70)

    num_iterations = 25
    queries = [
        "What is the remote work policy?",
        "How many sick leave days are permitted annually?",
        "Explain health insurance deductible and HSA rollover rules",
        "Code of conduct and non-disclosure agreement requirements",
        "Expense reimbursement guidelines for travel and meals",
    ]

    mock_mongo, mock_emb = create_mock_retrieval_environment()

    advanced_retriever = AdvancedRetriever(
        mongo_client=mock_mongo,
        embedding_generator=mock_emb,
        reranker=NoOpReranker(),
        oversample_factor=3,
        rrf_k=60,
    )

    baseline_latencies: list[float] = []
    advanced_latencies: list[float] = []
    stage_breakdowns: list[dict] = []

    print(f"\nRunning {num_iterations} benchmark iterations across {len(queries)} queries...")

    for i in range(num_iterations):
        q = queries[i % len(queries)]
        # 1. Baseline
        t_base = await run_baseline_search(mock_mongo, mock_emb, q, top_k=5)
        baseline_latencies.append(t_base)

        # 2. Advanced
        t_adv, stages = await run_advanced_search(advanced_retriever, q, top_k=5)
        advanced_latencies.append(t_adv)
        stage_breakdowns.append(stages)

    # Compute percentiles
    def calc_stats(times: list[float]):
        sorted_times = sorted(times)
        mean_val = statistics.mean(times)
        median_val = statistics.median(times)
        p90_idx = int(0.90 * len(sorted_times))
        p99_idx = int(0.99 * len(sorted_times))
        return {
            "mean": round(mean_val, 2),
            "p50": round(median_val, 2),
            "p90": round(sorted_times[min(p90_idx, len(sorted_times) - 1)], 2),
            "p99": round(sorted_times[min(p99_idx, len(sorted_times) - 1)], 2),
        }

    base_stats = calc_stats(baseline_latencies)
    adv_stats = calc_stats(advanced_latencies)

    # Compute average stage latencies for Advanced
    avg_stages = {
        k: round(statistics.mean(s[k] for s in stage_breakdowns), 2)
        for k in stage_breakdowns[0]
    }

    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS SUMMARY (Latency in milliseconds)")
    print("=" * 70)
    print(f"{'Metric':<25} | {'Baseline Retrieval':<18} | {'Advanced Retrieval':<18}")
    print("-" * 70)
    print(f"{'Mean Latency':<25} | {base_stats['mean']:>14.2f} ms | {adv_stats['mean']:>14.2f} ms")
    print(f"{'P50 (Median)':<25} | {base_stats['p50']:>14.2f} ms | {adv_stats['p50']:>14.2f} ms")
    print(f"{'P90 Percentile':<25} | {base_stats['p90']:>14.2f} ms | {adv_stats['p90']:>14.2f} ms")
    print(f"{'P99 Percentile':<25} | {base_stats['p99']:>14.2f} ms | {adv_stats['p99']:>14.2f} ms")
    print("-" * 70)

    print("\nADVANCED RETRIEVAL STAGE LATENCY BREAKDOWN (Average)")
    print("-" * 70)
    print(f"1. Query Preprocessing & Normalization: {avg_stages['query_preprocessing_ms']:.2f} ms")
    print(f"2. Vector Search (Over-fetched 3x):     {avg_stages['vector_search_ms']:.2f} ms")
    print(f"3. Keyword Search (Over-fetched 3x):    {avg_stages['keyword_search_ms']:.2f} ms")
    print(f"4. RRF Fusion & Deduplication:         {avg_stages['fusion_ms']:.2f} ms")
    print(f"5. Reranker Evaluation (NoOp):          {avg_stages['rerank_ms']:.2f} ms")
    print(f"-> Total End-to-End Latency:           {avg_stages['total_latency_ms']:.2f} ms")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
