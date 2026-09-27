"""Context guardrails: Document prompt injection defense, confidence thresholds, context limits, and conflict detection."""

import re
from typing import Any, Tuple

from mcp_rag_agent.agent.models import RetrievedChunkOutput
from mcp_rag_agent.guardrails.models import (
    DecisionCategory,
    GuardrailViolation,
    ViolationType,
)

# Indirect prompt injection signatures found inside retrieved document text
_DOCUMENT_INJECTION_PATTERNS = [
    re.compile(
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|prompts)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:disregard|forget)\s+(?:all\s+)?(?:instructions|rules|policy\s+guidelines)",
        re.IGNORECASE,
    ),
    re.compile(r"\[\s*system(?:\s+instruction|\s+command)?\s*:.*?\]", re.IGNORECASE),
    re.compile(r"<\s*system\s*>.*?<\s*/\s*system\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"instead\s+of\s+answering.*?(?:output|say|print)", re.IGNORECASE),
    re.compile(r"new\s+instruction\s*:\s*", re.IGNORECASE),
]


def sanitize_document_text(content: str) -> Tuple[str, bool]:
    """Scan and neutralize indirect prompt injections inside retrieved document text."""
    sanitized = content
    injection_found = False

    for pattern in _DOCUMENT_INJECTION_PATTERNS:
        if pattern.search(sanitized):
            injection_found = True
            sanitized = pattern.sub("[POTENTIAL_PROMPT_INJECTION_FILTERED]", sanitized)

    return sanitized, injection_found


def check_conflicting_documents(
    chunks: list[RetrievedChunkOutput],
) -> Tuple[bool, list[str]]:
    """Inspect retrieved chunks for conflicting numerical or policy directives."""
    conflicts: list[str] = []
    if len(chunks) < 2:
        return False, conflicts

    # Example: Check for contradictory numbers associated with same subject (e.g. days of leave)
    days_mentions = {}
    for chunk in chunks:
        # Match phrases like "25 days", "30 days", "15 days"
        matches = re.findall(
            r"(\d+)\s*(?:working\s+)?days", chunk.content, re.IGNORECASE
        )
        if matches:
            days_mentions[chunk.document_name] = sorted(list(set(matches)))

    # If different documents cite different day allocations for similar contexts
    if len(days_mentions) > 1:
        doc_names = list(days_mentions.keys())
        for i in range(len(doc_names)):
            for j in range(i + 1, len(doc_names)):
                d1, d2 = doc_names[i], doc_names[j]
                if days_mentions[d1] != days_mentions[d2]:
                    conflicts.append(
                        f"Potential policy variance: '{d1}' mentions {days_mentions[d1]} days "
                        f"while '{d2}' mentions {days_mentions[d2]} days."
                    )

    has_conflicts = len(conflicts) > 0
    return has_conflicts, conflicts


def evaluate_retrieval_context(
    chunks: list[RetrievedChunkOutput],
    confidence_threshold: float = 0.015,
    min_vector_similarity: float = 0.50,
    max_context_chars: int = 4000,
) -> Tuple[str, float, DecisionCategory, list[GuardrailViolation], list[str]]:
    """Apply context guardrails: empty check, confidence threshold, injection sanitization, and truncation.

    Returns:
        sanitized_context: Formatted context string safe for LLM consumption.
        confidence_score: Computed retrieval confidence (0.0 to 1.0).
        decision: Preliminary decision category.
        violations: List of guardrail violations.
        warnings: List of advisory warnings.
    """
    violations: list[GuardrailViolation] = []
    warnings: list[str] = []

    # 1. Empty Retrieval Check
    if not chunks:
        violations.append(
            GuardrailViolation(
                violation_type=ViolationType.EMPTY_RETRIEVAL,
                message="No relevant policy documents were retrieved from the database.",
                severity="critical",
            )
        )
        return "", 0.0, DecisionCategory.INSUFFICIENT_EVIDENCE, violations, warnings

    # 2. Confidence & Low-Relevance Threshold Evaluation
    # Best candidate fusion score
    top_chunk = chunks[0]
    best_fusion_score = getattr(top_chunk, "fusion_score", 0.0)
    best_vector_score = getattr(top_chunk, "vector_score", None)

    # Compute a normalized confidence score between 0.0 and 1.0
    # RRF with k=60 produces scores around ~0.016 to 0.033
    normalized_confidence = min(1.0, max(0.0, best_fusion_score * 30.0))
    if best_vector_score is not None:
        normalized_confidence = max(normalized_confidence, float(best_vector_score))

    if best_fusion_score < confidence_threshold:
        violations.append(
            GuardrailViolation(
                violation_type=ViolationType.LOW_CONFIDENCE,
                message=f"Retrieval fusion score ({best_fusion_score:.4f}) is below confidence threshold ({confidence_threshold:.4f}).",
                severity="warning",
                details={
                    "fusion_score": best_fusion_score,
                    "threshold": confidence_threshold,
                },
            )
        )
        return (
            "",
            normalized_confidence,
            DecisionCategory.INSUFFICIENT_EVIDENCE,
            violations,
            warnings,
        )

    # 3. Document Prompt Injection Neutralization & Sandboxing
    sanitized_chunks = []
    for chunk in chunks:
        clean_text, injection_detected = sanitize_document_text(chunk.content)
        if injection_detected:
            violations.append(
                GuardrailViolation(
                    violation_type=ViolationType.PROMPT_INJECTION_DOCUMENT,
                    message=f"Indirect prompt injection attempt neutralized in document '{chunk.document_name}'.",
                    severity="critical",
                    details={
                        "document_name": chunk.document_name,
                        "chunk_id": chunk.chunk_id,
                    },
                )
            )
        # Sandbox within untrusted data boundaries
        sandboxed_chunk = (
            f'<retrieved_policy_chunk document="{chunk.document_name}" id="{chunk.chunk_id}" untrusted_data="true">\n'
            f"{clean_text.strip()}\n"
            f"</retrieved_policy_chunk>"
        )
        sanitized_chunks.append(sandboxed_chunk)

    # 4. Conflicting Document Detection
    has_conflicts, conflict_details = check_conflicting_documents(chunks)
    if has_conflicts:
        warnings.extend(conflict_details)
        violations.append(
            GuardrailViolation(
                violation_type=ViolationType.CONFLICTING_DOCUMENTS,
                message="Retrieved documents contain potentially conflicting policy directives.",
                severity="warning",
                details={"conflicts": conflict_details},
            )
        )

    # 5. Context Limit Truncation
    context_str = "\n\n".join(sanitized_chunks)
    if len(context_str) > max_context_chars:
        context_str = (
            context_str[:max_context_chars]
            + "\n\n[CONTEXT TRUNCATED DUE TO SAFETY LIMITS]"
        )
        warnings.append(
            f"Context truncated to maximum limit of {max_context_chars} characters."
        )
        violations.append(
            GuardrailViolation(
                violation_type=ViolationType.CONTEXT_LIMIT_EXCEEDED,
                message="Retrieved context exceeded maximum character allowance.",
                severity="warning",
                details={"max_context_chars": max_context_chars},
            )
        )

    decision = DecisionCategory.SUPPORTED_BY_EVIDENCE
    return context_str, normalized_confidence, decision, violations, warnings
