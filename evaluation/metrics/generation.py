"""Generation quality metrics: Answer Relevancy, Answer Correctness, Faithfulness, Context Precision, and Context Recall."""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("GenerationMetrics")

# Common English stopwords to exclude during lexical overlap analysis
_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've",
    "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me",
    "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on",
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't",
    "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while",
    "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't",
    "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
    "reference", "references", "section", "policy"
}


def _extract_content_tokens(text: str) -> List[str]:
    """Extract lowercased non-stopword tokens of length >= 3."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\$]{3,}\b", text.lower())
    return [t for t in tokens if t not in _STOPWORDS]


def _extract_numbers(text: str) -> List[str]:
    """Extract numeric values, percentages, and currencies."""
    return re.findall(r"\b\d+(?:\.\d+)?%?\b|\$\d+", text)


def compute_faithfulness(generated_answer: str, retrieved_contexts: List[str]) -> float:
    """Measure the proportion of claims in the generated answer supported by retrieved contexts.

    A score of 1.0 indicates 0 ungrounded claims (zero hallucinations).
    """
    if not generated_answer or not generated_answer.strip():
        return 0.0

    # If answer is a valid refusal standard, it is completely faithful to missing evidence
    lowered = generated_answer.lower()
    if (
        "couldn't find this information" in lowered
        or "could not find this information" in lowered
        or "outside my knowledge scope" in lowered
    ):
        return 1.0

    if not retrieved_contexts:
        return 0.0

    full_context = " ".join(retrieved_contexts).lower()
    context_tokens = set(_extract_content_tokens(full_context))
    context_numbers = set(_extract_numbers(full_context))

    # Split answer into sentence-level claims
    sentences = [s.strip() for s in re.split(r"[.\n;!?]+", generated_answer) if len(s.strip()) > 5]
    if not sentences:
        sentences = [generated_answer.strip()]

    supported_claims = 0
    for sentence in sentences:
        s_tokens = _extract_content_tokens(sentence)
        s_numbers = _extract_numbers(sentence)

        if not s_tokens:
            supported_claims += 1
            continue

        token_hits = sum(1 for t in s_tokens if t in context_tokens or t in full_context)
        token_ratio = token_hits / len(s_tokens)

        # Numbers must match strictly if present
        if s_numbers:
            num_hits = sum(1 for n in s_numbers if n in context_numbers or n in full_context)
            num_ratio = num_hits / len(s_numbers)
            is_supported = (token_ratio >= 0.50) and (num_ratio >= 0.80)
        else:
            is_supported = token_ratio >= 0.50

        if is_supported:
            supported_claims += 1

    return round(supported_claims / len(sentences), 4)


def compute_answer_correctness(generated_answer: str, ground_truth: str) -> float:
    """Measure factual agreement between generated answer and ground-truth reference answer."""
    if not generated_answer or not ground_truth:
        return 0.0

    ans_tokens = set(_extract_content_tokens(generated_answer))
    ref_tokens = set(_extract_content_tokens(ground_truth))

    ans_numbers = set(_extract_numbers(generated_answer))
    ref_numbers = set(_extract_numbers(ground_truth))

    if not ref_tokens:
        return 1.0 if not ans_tokens else 0.5

    # Token overlap: Jaccard & Precision/Recall blend
    overlap = len(ans_tokens & ref_tokens)
    recall = overlap / len(ref_tokens)
    precision = overlap / len(ans_tokens) if ans_tokens else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Numerical alignment
    if ref_numbers:
        num_overlap = len(ans_numbers & ref_numbers)
        num_score = num_overlap / len(ref_numbers)
        score = (0.5 * f1) + (0.5 * num_score)
    else:
        score = f1

    # Check for direct refusal match
    if "couldn't find this information" in ground_truth.lower() and "couldn't find this information" in generated_answer.lower():
        score = 1.0

    return min(1.0, max(0.0, round(score, 4)))


def compute_context_precision(retrieved_contexts: List[str], ground_truth: str) -> float:
    """Measure the signal-to-noise ratio: proportion of retrieved chunks containing ground truth facts."""
    if not retrieved_contexts:
        return 0.0
    if not ground_truth:
        return 1.0

    ref_tokens = set(_extract_content_tokens(ground_truth))
    if not ref_tokens:
        return 1.0

    relevant_chunks = 0
    for chunk in retrieved_contexts:
        chunk_tokens = set(_extract_content_tokens(chunk))
        overlap = len(chunk_tokens & ref_tokens)
        if (overlap / len(ref_tokens)) >= 0.25:
            relevant_chunks += 1

    return round(relevant_chunks / len(retrieved_contexts), 4)


def compute_context_recall(retrieved_contexts: List[str], ground_truth: str) -> float:
    """Measure whether the retrieved context contains all facts needed to answer the reference."""
    if not ground_truth:
        return 1.0
    if not retrieved_contexts:
        return 0.0

    ref_tokens = set(_extract_content_tokens(ground_truth))
    ref_numbers = set(_extract_numbers(ground_truth))

    if not ref_tokens and not ref_numbers:
        return 1.0

    full_context = " ".join(retrieved_contexts).lower()
    context_tokens = set(_extract_content_tokens(full_context))
    context_numbers = set(_extract_numbers(full_context))

    token_hits = sum(1 for t in ref_tokens if t in context_tokens or t in full_context)
    token_score = token_hits / len(ref_tokens) if ref_tokens else 1.0

    if ref_numbers:
        num_hits = sum(1 for n in ref_numbers if n in context_numbers or n in full_context)
        num_score = num_hits / len(ref_numbers)
        recall = (0.7 * token_score) + (0.3 * num_score)
    else:
        recall = token_score

    return min(1.0, max(0.0, round(recall, 4)))


def compute_answer_relevancy(question: str, generated_answer: str) -> float:
    """Measure whether the generated answer is directly responsive to the question."""
    if not question or not generated_answer:
        return 0.0

    q_tokens = set(_extract_content_tokens(question))
    a_tokens = set(_extract_content_tokens(generated_answer))

    if not q_tokens:
        return 1.0

    overlap = len(q_tokens & a_tokens)
    score = overlap / len(q_tokens)

    # If answer contains valid refusal or out of scope answer to non-policy query
    if "couldn't find this information" in generated_answer.lower() or "outside my knowledge scope" in generated_answer.lower():
        score = max(score, 0.85)

    return min(1.0, max(0.0, round(score, 4)))


def compute_generation_metrics(
    question: str,
    generated_answer: str,
    ground_truth: str,
    retrieved_contexts: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Compute all 5 core generation quality metrics."""
    contexts = retrieved_contexts or []
    return {
        "answer_relevancy": compute_answer_relevancy(question, generated_answer),
        "answer_correctness": compute_answer_correctness(generated_answer, ground_truth),
        "faithfulness": compute_faithfulness(generated_answer, contexts),
        "context_precision": compute_context_precision(contexts, ground_truth),
        "context_recall": compute_context_recall(contexts, ground_truth),
    }
