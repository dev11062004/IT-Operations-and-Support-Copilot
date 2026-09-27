"""Data models and abstractions for RAG Safety and Grounding Guardrails."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DecisionCategory(str, Enum):
    """The 4-tier grounding decision taxonomy required for production verification."""

    SUPPORTED_BY_EVIDENCE = (
        "supported_by_evidence"  # A. Answer supported by retrieved evidence
    )
    INSUFFICIENT_EVIDENCE = (
        "insufficient_evidence"  # B. Insufficient evidence (refusal standard enforced)
    )
    OUT_OF_DOMAIN = (
        "out_of_domain"  # C. Question outside knowledge scope / policy domain
    )
    SYSTEM_FAILURE = "system_failure"  # D. Retrieval or database system failure


class ViolationType(str, Enum):
    """Specific guardrail violation categories."""

    PROMPT_INJECTION_QUERY = "prompt_injection_query"
    PROMPT_INJECTION_DOCUMENT = "prompt_injection_document"
    OUT_OF_DOMAIN = "out_of_domain"
    EMPTY_RETRIEVAL = "empty_retrieval"
    LOW_CONFIDENCE = "low_confidence"
    CONTEXT_LIMIT_EXCEEDED = "context_limit_exceeded"
    CONFLICTING_DOCUMENTS = "conflicting_documents"
    FABRICATED_CITATION = "fabricated_citation"
    NON_EXISTENT_SOURCE = "non_existent_source"
    UNGROUNDED_CONTENT = "ungrounded_content"
    SYSTEM_ERROR = "system_error"


class GuardrailViolation(BaseModel):
    """Details regarding a specific guardrail rule trigger."""

    violation_type: ViolationType = Field(
        ..., description="Classification of the rule violation"
    )
    message: str = Field(..., description="Human-readable description of the violation")
    severity: str = Field(
        "warning", description="Severity level: 'warning' or 'critical'"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic contextual metadata"
    )


class GuardrailResult(BaseModel):
    """Complete diagnostic result returned by RAG safety guardrails."""

    is_safe: bool = Field(
        True, description="True if no critical safety or grounding violations occurred"
    )
    decision: DecisionCategory = Field(
        DecisionCategory.SUPPORTED_BY_EVIDENCE,
        description="Final decision taxonomy classification",
    )
    confidence_score: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Retrieval confidence score based on similarity/fusion rankings",
    )
    grounding_score: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Measured lexical & semantic grounding score (overlap of facts with retrieved context)",
    )
    violations: list[GuardrailViolation] = Field(
        default_factory=list, description="List of detected rule violations"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Advisory warnings (e.g. conflicting documents, context truncation)",
    )
    sanitized_query: str = Field(
        "", description="Cleaned, injection-neutralized user query"
    )
    sanitized_context: str = Field(
        "", description="Sanitized, sandboxed context safe for LLM ingestion"
    )
    validated_citations: list[str] = Field(
        default_factory=list,
        description="Citations verified to exist in the retrieved document corpus",
    )
    rejected_citations: list[str] = Field(
        default_factory=list,
        description="Citations rejected because they were fabricated or missing from retrieved context",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional evaluation or timing metadata"
    )
