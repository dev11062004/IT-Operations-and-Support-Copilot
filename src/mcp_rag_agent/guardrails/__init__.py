"""RAG Safety and Grounding Guardrails package."""

from mcp_rag_agent.guardrails.context_guardrails import (
    check_conflicting_documents,
    evaluate_retrieval_context,
    sanitize_document_text,
)
from mcp_rag_agent.guardrails.input_guardrails import (
    check_input_prompt_injection,
    check_out_of_domain,
    sanitize_query,
)
from mcp_rag_agent.guardrails.manager import RAGGuardrails
from mcp_rag_agent.guardrails.models import (
    DecisionCategory,
    GuardrailResult,
    GuardrailViolation,
    ViolationType,
)
from mcp_rag_agent.guardrails.output_guardrails import (
    GROUNDED_REFUSAL_MESSAGE,
    calculate_grounding_score,
    evaluate_output_grounding,
    extract_citations_from_text,
    mask_sensitive_data,
    validate_citations,
)

__all__ = [
    "RAGGuardrails",
    "GuardrailResult",
    "GuardrailViolation",
    "DecisionCategory",
    "ViolationType",
    "GROUNDED_REFUSAL_MESSAGE",
    "sanitize_query",
    "check_input_prompt_injection",
    "check_out_of_domain",
    "sanitize_document_text",
    "check_conflicting_documents",
    "evaluate_retrieval_context",
    "mask_sensitive_data",
    "extract_citations_from_text",
    "validate_citations",
    "calculate_grounding_score",
    "evaluate_output_grounding",
]
