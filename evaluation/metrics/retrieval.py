"""Retrieval quality metrics: Recall@K, Precision@K, Mean Reciprocal Rank (MRR), and Hit Rate."""

import re
from typing import Dict, List, Set, Union


def normalize_doc_name(name: str) -> str:
    """Normalize document filenames and titles for deterministic comparison."""
    if not name:
        return ""
    # Strip extensions and replace unicode dashes / whitespace
    clean = re.sub(r"\.(txt|pdf|docx|md|html)$", "", name.strip(), flags=re.IGNORECASE)
    clean = re.sub(r"[\u2013\u2014\-_]+", " ", clean)
    clean = " ".join(clean.lower().split())
    return clean


def _matches_any_relevant(doc: str, relevant_normalized: Set[str]) -> bool:
    """Check if retrieved doc name matches any ground truth relevant document."""
    norm = normalize_doc_name(doc)
    if norm in relevant_normalized:
        return True
    # Fuzzy substring containment (e.g. 'annual leave' matching '3 annual leave')
    for rel in relevant_normalized:
        if len(rel) >= 4 and (rel in norm or norm in rel):
            return True
    return False


def compute_recall_at_k(
    retrieved_docs: List[str],
    relevant_docs: List[str],
    k: int = 3,
) -> float:
    """Compute Recall@K: proportion of ground-truth relevant documents retrieved in top-K.

    Args:
        retrieved_docs: Ordered list of retrieved document filenames/IDs.
        relevant_docs: List of ground-truth relevant document filenames/IDs.
        k: Cutoff rank (default: 3).

    Returns:
        Recall@K score between 0.0 and 1.0.
    """
    if not relevant_docs:
        # If question has no relevant docs (e.g. out-of-domain or ungrounded),
        # return 1.0 if retriever correctly returned nothing, else 0.0
        return 1.0 if not retrieved_docs else 0.0

    top_k = retrieved_docs[:k]
    rel_norm = {normalize_doc_name(d) for d in relevant_docs if d}

    hits = sum(1 for d in rel_norm if any(_matches_any_relevant(r, {d}) for r in top_k))
    return min(1.0, hits / len(rel_norm))


def compute_precision_at_k(
    retrieved_docs: List[str],
    relevant_docs: List[str],
    k: int = 3,
) -> float:
    """Compute Precision@K: proportion of top-K retrieved documents that are relevant.

    Args:
        retrieved_docs: Ordered list of retrieved document filenames/IDs.
        relevant_docs: List of ground-truth relevant document filenames/IDs.
        k: Cutoff rank (default: 3).

    Returns:
        Precision@K score between 0.0 and 1.0.
    """
    if k <= 0:
        return 0.0
    if not relevant_docs:
        return 1.0 if not retrieved_docs else 0.0

    top_k = retrieved_docs[:k]
    if not top_k:
        return 0.0

    rel_norm = {normalize_doc_name(d) for d in relevant_docs if d}
    relevant_hits = sum(1 for d in top_k if _matches_any_relevant(d, rel_norm))
    return min(1.0, relevant_hits / k)


def compute_mrr(
    retrieved_docs: List[str],
    relevant_docs: List[str],
) -> float:
    """Compute Mean Reciprocal Rank (MRR): 1 / rank of the first relevant document.

    Args:
        retrieved_docs: Ordered list of retrieved document filenames/IDs.
        relevant_docs: List of ground-truth relevant document filenames/IDs.

    Returns:
        Reciprocal rank score between 0.0 and 1.0 (0.0 if no relevant doc retrieved).
    """
    if not relevant_docs:
        return 1.0 if not retrieved_docs else 0.0

    rel_norm = {normalize_doc_name(d) for d in relevant_docs if d}
    for rank_idx, doc in enumerate(retrieved_docs, start=1):
        if _matches_any_relevant(doc, rel_norm):
            return 1.0 / rank_idx

    return 0.0


def compute_hit_rate(
    retrieved_docs: List[str],
    relevant_docs: List[str],
    k: int = 3,
) -> float:
    """Compute Hit Rate@K: 1.0 if at least one relevant document appears in top-K, else 0.0.

    Args:
        retrieved_docs: Ordered list of retrieved document filenames/IDs.
        relevant_docs: List of ground-truth relevant document filenames/IDs.
        k: Cutoff rank (default: 3).

    Returns:
        1.0 for a hit, 0.0 for a miss.
    """
    if not relevant_docs:
        return 1.0 if not retrieved_docs else 0.0

    top_k = retrieved_docs[:k]
    rel_norm = {normalize_doc_name(d) for d in relevant_docs if d}
    for doc in top_k:
        if _matches_any_relevant(doc, rel_norm):
            return 1.0

    return 0.0


def compute_retrieval_metrics(
    retrieved_docs: List[str],
    relevant_docs: List[str],
    k_list: Union[List[int], tuple] = (1, 3, 5),
) -> Dict[str, float]:
    """Calculate all standard retrieval metrics across multiple K cutoffs.

    Args:
        retrieved_docs: Ordered list of retrieved documents.
        relevant_docs: List of ground-truth relevant documents.
        k_list: List of K values to evaluate.

    Returns:
        Dictionary mapping metric names (e.g. 'recall@3', 'mrr') to float scores.
    """
    metrics: Dict[str, float] = {}

    for k in k_list:
        metrics[f"recall@{k}"] = round(compute_recall_at_k(retrieved_docs, relevant_docs, k=k), 4)
        metrics[f"precision@{k}"] = round(compute_precision_at_k(retrieved_docs, relevant_docs, k=k), 4)
        metrics[f"hit_rate@{k}"] = round(compute_hit_rate(retrieved_docs, relevant_docs, k=k), 4)

    metrics["mrr"] = round(compute_mrr(retrieved_docs, relevant_docs), 4)
    return metrics
