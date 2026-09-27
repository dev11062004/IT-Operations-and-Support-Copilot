"""Output guardrails: Citation validation, source existence verification, answer grounding, and sensitive data protection."""

import re
from typing import Optional, Tuple

from mcp_rag_agent.agent.models import RetrievedChunkOutput
from mcp_rag_agent.guardrails.models import (
    DecisionCategory,
    GuardrailViolation,
    ViolationType,
)

# Standard refusal string for insufficient evidence or ungrounded responses
GROUNDED_REFUSAL_MESSAGE = (
    "I couldn't find this information in the available policy content."
)

# Sensitive data masking patterns
_SENSITIVE_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "sk-***REDACTED***"),
    (
        re.compile(r"mongodb(?:\+srv)?:\/\/[^@\s]+@", re.IGNORECASE),
        "mongodb://***REDACTED***@",
    ),
    (
        re.compile(r"(?:bearer\s+)[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
        "Bearer ***REDACTED***",
    ),
    (
        re.compile(
            r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE
        ),
        "password='***REDACTED***'",
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "***@REDACTED.COM",
    ),
]

# Citations regex patterns
_CITATION_LINE_RE = re.compile(r"^\s*(?:\d+[\.\)]|\-|\*)\s*(.+)$", re.MULTILINE)
_BRACKET_CITATION_RE = re.compile(
    r"\[(?:Reference|Source|Doc|Citation):\s*([^\]]+)\]", re.IGNORECASE
)
_SOURCE_PREFIX_RE = re.compile(
    r"^(?:Source|Reference):\s*(.+)$", re.IGNORECASE | re.MULTILINE
)

# Common English stopwords to ignore when computing lexical grounding score
_STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can't",
    "cannot",
    "could",
    "couldn't",
    "did",
    "didn't",
    "do",
    "does",
    "doesn't",
    "doing",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "hadn't",
    "has",
    "hasn't",
    "have",
    "haven't",
    "having",
    "he",
    "he'd",
    "he'll",
    "he's",
    "her",
    "here",
    "here's",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "how's",
    "i",
    "i'd",
    "i'll",
    "i'm",
    "i've",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "itself",
    "let's",
    "me",
    "more",
    "most",
    "mustn't",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "shan't",
    "she",
    "she'd",
    "she'll",
    "she's",
    "should",
    "shouldn't",
    "so",
    "some",
    "such",
    "than",
    "that",
    "that's",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "there's",
    "these",
    "they",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasn't",
    "we",
    "we'd",
    "we'll",
    "we're",
    "we've",
    "were",
    "weren't",
    "what",
    "what's",
    "when",
    "when's",
    "where",
    "where's",
    "which",
    "while",
    "who",
    "who's",
    "whom",
    "why",
    "why's",
    "with",
    "won't",
    "would",
    "wouldn't",
    "you",
    "you'd",
    "you'll",
    "you're",
    "you've",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "reference",
    "references",
    "section",
    "policy",
    "according",
}


def mask_sensitive_data(text: str) -> str:
    """Mask credentials, API keys, bearer tokens, passwords, and emails from text or logs."""
    if not isinstance(text, str):
        return str(text)
    masked = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


def extract_citations_from_text(answer_text: str) -> list[str]:
    """Extract cited document names, titles, or filenames from answer text."""
    citations: list[str] = []

    # 1. Section references: Reference: or References:
    if "Reference:" in answer_text or "References:" in answer_text:
        ref_part = answer_text.split("Reference:")[-1]
        if "References:" in answer_text:
            ref_part = answer_text.split("References:")[-1]
        lines = _CITATION_LINE_RE.findall(ref_part)
        for line in lines:
            clean = line.strip().rstrip(".").strip()
            if clean and len(clean) < 150:
                citations.append(clean)

    # 2. Bracket references [Reference: ...]
    for match in _BRACKET_CITATION_RE.findall(answer_text):
        clean = match.strip().rstrip(".").strip()
        if clean and len(clean) < 150:
            citations.append(clean)

    # 3. Source: ... prefix lines
    for match in _SOURCE_PREFIX_RE.findall(answer_text):
        clean = match.strip().rstrip(".").strip()
        if clean and len(clean) < 150 and clean not in citations:
            citations.append(clean)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for c in citations:
        norm = c.lower()
        if norm not in seen:
            seen.add(norm)
            deduped.append(c)

    return deduped


def _normalize_name(name: str) -> str:
    """Normalize file or document name for fuzzy comparison."""
    # Strip extensions and non-alphanumeric chars
    n = re.sub(r"\.(pdf|docx|txt|md|html)$", "", name, flags=re.IGNORECASE)
    n = re.sub(r"[\-_\s\.]+", " ", n).strip().lower()
    return n


def validate_citations(
    citations: list[str],
    retrieved_chunks: list[RetrievedChunkOutput],
) -> Tuple[list[str], list[str], list[GuardrailViolation]]:
    """Validate that every cited document actually exists in the retrieved chunks.

    Returns:
        validated_citations: Citations that match retrieved documents.
        rejected_citations: Citations that do not match any retrieved document (fabricated).
        violations: Guardrail violations for any fabricated or non-existent citations.
    """
    validated: list[str] = []
    rejected: list[str] = []
    violations: list[GuardrailViolation] = []

    if not citations:
        return validated, rejected, violations

    # Build known documents index from chunks
    known_docs = set()
    known_normalized = set()
    known_ids = set()

    for chunk in retrieved_chunks:
        if chunk.document_name:
            known_docs.add(chunk.document_name)
            known_normalized.add(_normalize_name(chunk.document_name))
        if chunk.document_id:
            known_ids.add(chunk.document_id)
            known_ids.add(_normalize_name(chunk.document_id))

    for cite in citations:
        cite_norm = _normalize_name(cite)
        is_valid = False

        # Direct match or normalized match
        if cite in known_docs or cite_norm in known_normalized:
            is_valid = True
        elif any(
            cite_norm in kn or kn in cite_norm for kn in known_normalized if len(kn) > 3
        ):
            is_valid = True
        elif cite in known_ids or cite_norm in known_ids:
            is_valid = True

        if is_valid:
            validated.append(cite)
        else:
            rejected.append(cite)
            violations.append(
                GuardrailViolation(
                    violation_type=ViolationType.FABRICATED_CITATION,
                    message=f"Citation '{cite}' does not exist in the retrieved document set.",
                    severity="critical",
                    details={"citation": cite, "retrieved_documents": list(known_docs)},
                )
            )

    return validated, rejected, violations


def calculate_grounding_score(answer_text: str, context_text: str) -> float:
    """Calculate lexical and factual overlap score between answer and retrieved context.

    Returns a score between 0.0 and 1.0 representing proportion of answer content
    tokens/entities present in the context.
    """
    if not answer_text.strip():
        return 0.0

    # If answer explicitly acknowledges missing information, it is grounded as a refusal
    lowered_ans = answer_text.lower()
    if (
        "couldn't find this information" in lowered_ans
        or "could not find this information" in lowered_ans
        or "outside the scope" in lowered_ans
        or "not mentioned in the policy" in lowered_ans
    ):
        return 1.0

    if not context_text.strip():
        return 0.0

    # Extract non-stopword content words (length >= 3)
    ans_tokens = re.findall(r"\b[a-zA-Z0-9_\-\$]{3,}\b", answer_text.lower())
    content_tokens = [t for t in ans_tokens if t not in _STOPWORDS]

    if not content_tokens:
        return 1.0

    context_lower = context_text.lower()
    context_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\$]{3,}\b", context_lower))

    # Also check numbers specifically (crucial for policy limits, days, amounts)
    ans_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", answer_text))
    ctx_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", context_text))

    supported_count = sum(
        1 for t in content_tokens if t in context_tokens or t in context_lower
    )
    token_score = supported_count / len(content_tokens)

    # If numbers were cited in the answer, verify they exist in the context
    if ans_numbers:
        num_supported = sum(1 for n in ans_numbers if n in ctx_numbers)
        num_score = num_supported / len(ans_numbers)
        # Weighted combination: 70% token overlap + 30% numerical verification
        final_score = (0.7 * token_score) + (0.3 * num_score)
    else:
        final_score = token_score

    return min(1.0, max(0.0, final_score))


def evaluate_output_grounding(
    answer_text: str,
    retrieved_chunks: list[RetrievedChunkOutput],
    min_grounding_score: float = 0.20,
) -> Tuple[float, list[str], list[str], DecisionCategory, list[GuardrailViolation]]:
    """Validate answer citations and measure grounding score against retrieved chunks.

    Returns:
        grounding_score: Computed grounding score (0.0 to 1.0).
        validated_citations: List of verified citations.
        rejected_citations: List of fabricated or missing citations.
        decision: Updated decision category.
        violations: List of guardrail violations.
    """
    violations: list[GuardrailViolation] = []

    # 1. Check for standard refusal pattern
    lowered = answer_text.lower()
    is_refusal = (
        "couldn't find this information" in lowered
        or "could not find this information" in lowered
        or "not available in the provided policy" in lowered
    )

    if is_refusal:
        return 1.0, [], [], DecisionCategory.INSUFFICIENT_EVIDENCE, []

    # 2. Validate Citations
    citations = extract_citations_from_text(answer_text)
    validated_cites, rejected_cites, cite_violations = validate_citations(
        citations, retrieved_chunks
    )
    violations.extend(cite_violations)

    # 3. Grounding Score Calculation
    context_text = " ".join(c.content for c in retrieved_chunks)
    grounding_score = calculate_grounding_score(answer_text, context_text)

    # 4. Determine Grounding Decision
    if not retrieved_chunks:
        violations.append(
            GuardrailViolation(
                violation_type=ViolationType.UNGROUNDED_CONTENT,
                message="Answer generated with zero retrieved context evidence.",
                severity="critical",
            )
        )
        decision = DecisionCategory.INSUFFICIENT_EVIDENCE
    elif rejected_cites:
        # Fabricated citations disqualify answer from fully supported evidence
        decision = DecisionCategory.INSUFFICIENT_EVIDENCE
    elif grounding_score < min_grounding_score:
        violations.append(
            GuardrailViolation(
                violation_type=ViolationType.UNGROUNDED_CONTENT,
                message=f"Answer grounding score ({grounding_score:.2f}) is below minimum threshold ({min_grounding_score:.2f}).",
                severity="warning",
                details={
                    "grounding_score": grounding_score,
                    "threshold": min_grounding_score,
                },
            )
        )
        decision = DecisionCategory.INSUFFICIENT_EVIDENCE
    else:
        decision = DecisionCategory.SUPPORTED_BY_EVIDENCE

    return grounding_score, validated_cites, rejected_cites, decision, violations
