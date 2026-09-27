"""Central RAGGuardrails manager orchestrating input, context, and output verification."""

import logging
from typing import Optional, Tuple

from mcp_rag_agent.agent.models import RetrievedChunkOutput
from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.guardrails.context_guardrails import evaluate_retrieval_context
from mcp_rag_agent.guardrails.input_guardrails import (
    check_input_prompt_injection,
    check_out_of_domain,
    sanitize_query,
)
from mcp_rag_agent.guardrails.models import (
    DecisionCategory,
    GuardrailResult,
    GuardrailViolation,
    ViolationType,
)
from mcp_rag_agent.guardrails.output_guardrails import (
    GROUNDED_REFUSAL_MESSAGE,
    evaluate_output_grounding,
    mask_sensitive_data,
)

logger = logging.getLogger("RAGGuardrails")


class RAGGuardrails:
    """Production Guardrails orchestrator enforcing the 4-tier decision taxonomy:

    A. SUPPORTED_BY_EVIDENCE: Answer supported by retrieved evidence
    B. INSUFFICIENT_EVIDENCE: Refusal standard enforced; prevents guessing
    C. OUT_OF_DOMAIN: Question outside knowledge scope
    D. SYSTEM_FAILURE: Retrieval or system failure
    """

    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or config

    def validate_input(self, query: str) -> GuardrailResult:
        """Validate user input against prompt injection and out-of-domain scope."""
        if not self.cfg.ff_guardrails:
            return GuardrailResult(is_safe=True, sanitized_query=query)

        cleaned_query = sanitize_query(query)
        safe_query_log = mask_sensitive_data(cleaned_query)
        logger.debug(f"[GUARDRAIL:INPUT] Checking query: '{safe_query_log}'")

        violations: list[GuardrailViolation] = []

        # 1. Prompt Injection Defense
        is_inj_safe, inj_violations = check_input_prompt_injection(cleaned_query)
        if not is_inj_safe:
            violations.extend(inj_violations)
            logger.warning(
                f"[GUARDRAIL:INPUT] Prompt injection detected in query: '{safe_query_log}'"
            )
            return GuardrailResult(
                is_safe=False,
                decision=DecisionCategory.OUT_OF_DOMAIN,
                violations=violations,
                sanitized_query=cleaned_query,
            )

        # 2. Out-of-Domain Scope Detection
        is_in_domain, ood_violations = check_out_of_domain(cleaned_query)
        if not is_in_domain:
            violations.extend(ood_violations)
            logger.info(
                f"[GUARDRAIL:INPUT] Query classified as out-of-domain: '{safe_query_log}'"
            )
            return GuardrailResult(
                is_safe=True,
                decision=DecisionCategory.OUT_OF_DOMAIN,
                violations=violations,
                sanitized_query=cleaned_query,
            )

        return GuardrailResult(
            is_safe=True,
            decision=DecisionCategory.SUPPORTED_BY_EVIDENCE,
            sanitized_query=cleaned_query,
        )

    def filter_context(
        self,
        chunks: list[RetrievedChunkOutput],
        preliminary_result: Optional[GuardrailResult] = None,
    ) -> Tuple[str, GuardrailResult]:
        """Apply context guardrails: empty check, confidence threshold, injection sanitization, and truncation."""
        base_result = preliminary_result or GuardrailResult()
        if not self.cfg.ff_guardrails:
            context_str = "\n\n".join(c.content for c in chunks)
            return context_str, base_result

        (
            sanitized_context,
            confidence_score,
            decision,
            violations,
            warnings,
        ) = evaluate_retrieval_context(
            chunks=chunks,
            confidence_threshold=self.cfg.guardrail_confidence_threshold,
            min_vector_similarity=self.cfg.guardrail_min_vector_similarity,
            max_context_chars=self.cfg.guardrail_max_context_chars,
        )

        all_violations = list(base_result.violations) + violations
        all_warnings = list(base_result.warnings) + warnings

        # Determine combined decision
        final_decision = decision
        if base_result.decision == DecisionCategory.OUT_OF_DOMAIN:
            final_decision = DecisionCategory.OUT_OF_DOMAIN
        elif decision == DecisionCategory.INSUFFICIENT_EVIDENCE:
            final_decision = DecisionCategory.INSUFFICIENT_EVIDENCE

        updated_result = GuardrailResult(
            is_safe=base_result.is_safe
            and not any(
                v.severity == "critical"
                for v in violations
                if v.violation_type == ViolationType.PROMPT_INJECTION_QUERY
            ),
            decision=final_decision,
            confidence_score=confidence_score,
            grounding_score=base_result.grounding_score,
            violations=all_violations,
            warnings=all_warnings,
            sanitized_query=base_result.sanitized_query,
            sanitized_context=sanitized_context,
        )

        logger.debug(
            f"[GUARDRAIL:CONTEXT] Chunks: {len(chunks)} | Decision: {final_decision.value} | "
            f"Confidence: {confidence_score:.3f} | Violations: {len(all_violations)}"
        )
        return sanitized_context, updated_result

    def validate_output(
        self,
        answer_text: str,
        chunks: list[RetrievedChunkOutput],
        context_result: Optional[GuardrailResult] = None,
    ) -> Tuple[str, GuardrailResult]:
        """Validate answer citations, source existence, and factual grounding against retrieved chunks."""
        base_result = context_result or GuardrailResult()
        if not self.cfg.ff_guardrails:
            return answer_text, base_result

        # If already determined out of domain, preserve that decision
        if base_result.decision == DecisionCategory.OUT_OF_DOMAIN:
            return answer_text, base_result

        # If no chunks were retrieved
        if not chunks:
            if base_result.decision in (
                DecisionCategory.INSUFFICIENT_EVIDENCE,
                DecisionCategory.SYSTEM_FAILURE,
            ):
                final_decision = base_result.decision
                final_answer = answer_text
                if final_decision == DecisionCategory.INSUFFICIENT_EVIDENCE:
                    lowered = answer_text.lower()
                    if (
                        "couldn't find this information" not in lowered
                        and "could not find this information" not in lowered
                    ):
                        final_answer = f"{GROUNDED_REFUSAL_MESSAGE} Please consult Company XYZ HR or your manager for guidance."
                safe_final_answer = mask_sensitive_data(final_answer)
                return safe_final_answer, base_result
            else:
                # No retrieval was executed (e.g. conversational / non-retrieval graph execution)
                safe_final_answer = mask_sensitive_data(answer_text)
                return safe_final_answer, base_result

        (
            grounding_score,
            validated_cites,
            rejected_cites,
            grounding_decision,
            out_violations,
        ) = evaluate_output_grounding(
            answer_text=answer_text,
            retrieved_chunks=chunks,
            min_grounding_score=self.cfg.guardrail_min_grounding_score,
        )

        all_violations = list(base_result.violations) + out_violations
        all_warnings = list(base_result.warnings)

        # Merge decision taxonomy
        if base_result.decision == DecisionCategory.SYSTEM_FAILURE:
            final_decision = DecisionCategory.SYSTEM_FAILURE
        elif (
            base_result.decision == DecisionCategory.INSUFFICIENT_EVIDENCE
            or grounding_decision == DecisionCategory.INSUFFICIENT_EVIDENCE
        ):
            final_decision = DecisionCategory.INSUFFICIENT_EVIDENCE
        else:
            final_decision = DecisionCategory.SUPPORTED_BY_EVIDENCE

        # If decision is INSUFFICIENT_EVIDENCE and answer attempted to guess without refusal, enforce grounded refusal
        final_answer = answer_text
        if final_decision == DecisionCategory.INSUFFICIENT_EVIDENCE:
            lowered = answer_text.lower()
            if (
                "couldn't find this information" not in lowered
                and "could not find this information" not in lowered
            ):
                logger.info(
                    "[GUARDRAIL:OUTPUT] Enforcing grounded refusal response for insufficient evidence."
                )
                final_answer = f"{GROUNDED_REFUSAL_MESSAGE} Please consult Company XYZ HR or your manager for guidance."

        # Mask sensitive data in final answer
        safe_final_answer = mask_sensitive_data(final_answer)

        final_result = GuardrailResult(
            is_safe=base_result.is_safe and len(rejected_cites) == 0,
            decision=final_decision,
            confidence_score=base_result.confidence_score,
            grounding_score=grounding_score,
            violations=all_violations,
            warnings=all_warnings,
            sanitized_query=base_result.sanitized_query,
            sanitized_context=base_result.sanitized_context,
            validated_citations=validated_cites,
            rejected_citations=rejected_cites,
        )

        logger.info(
            f"[GUARDRAIL:OUTPUT] Decision: {final_decision.value} | Grounding Score: {grounding_score:.2f} | "
            f"Validated Cites: {len(validated_cites)} | Rejected Cites: {len(rejected_cites)}"
        )
        return safe_final_answer, final_result
