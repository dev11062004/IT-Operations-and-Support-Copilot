"""Production Agent Runner coordinating explicit responsibilities, citation validation, and execution metadata."""

import logging
import re
import time
import uuid
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from mcp_rag_agent.agent.models import (
    AgentExecutionMetadata,
    AgentResponse,
    RetrievedChunkOutput,
)
from mcp_rag_agent.core.config import config
from mcp_rag_agent.guardrails.manager import RAGGuardrails
from mcp_rag_agent.guardrails.models import (
    DecisionCategory,
    GuardrailResult,
    GuardrailViolation,
    ViolationType,
)
from mcp_rag_agent.mcp_server.tools import mask_sensitive
from mcp_rag_agent.observability import (
    ErrorCategory,
    ObservabilityTracer,
    get_langchain_run_config,
    set_request_context,
)

logger = logging.getLogger("RAGAgentRunner")


class RAGAgentRunner:
    """Production orchestrator encapsulating the 7 agentic responsibilities.

    1. Query understanding
    2. Tool selection
    3. Retrieval execution
    4. Context synthesis
    5. Grounded answer generation
    6. Citation generation and provenance validation
    7. Out-of-scope detection and graceful fallback
    """

    _OUT_OF_SCOPE_PHRASES = [
        "couldn't find this information",
        "could not find this information",
        "not available in the provided policy",
        "outside the scope",
        "only answer questions about company xyz",
    ]

    _CITATION_LINE_RE = re.compile(r"^\s*(?:\d+[\.\)]|\-|\*)\s*(.+)$", re.MULTILINE)

    def __init__(
        self,
        agent_graph: Any,
        system_prompt: Optional[str] = None,
        checkpointer: Optional[Any] = None,
        guardrails: Optional[RAGGuardrails] = None,
        runbook_executor: Optional[Any] = None,
    ):
        """Initialize runner.

        Args:
            agent_graph: Compiled LangGraph agent runnable.
            system_prompt: System prompt applied to the model.
            checkpointer: Optional conversation checkpointer for session persistence.
            guardrails: Optional RAGGuardrails instance for safety and grounding checks.
            runbook_executor: Optional RunbookExecutor instance for stateful troubleshooting workflows.
        """
        self.agent_graph = agent_graph
        self.system_prompt = system_prompt
        self.checkpointer = checkpointer
        self.guardrails = guardrails or RAGGuardrails()
        self.runbook_executor = runbook_executor

    def _extract_retrieval_info(self, messages: list[Any]) -> tuple[list[str], float]:
        """Extract retrieved document IDs and tool execution latency from message trace."""
        doc_ids: set[str] = set()
        retrieval_latency = 0.0

        for msg in messages:
            content = getattr(msg, "content", "")
            # Check ToolMessage or tool output content
            if isinstance(msg, ToolMessage) or getattr(msg, "name", None) in {
                "search_policy_documents",
                "search_documents",
            }:
                # Search for doc IDs like ID: doc_...
                found_ids = re.findall(r"ID:\s*([a-zA-Z0-9_\-]+)", str(content))
                for fid in found_ids:
                    doc_ids.add(fid)
                # Look for chunk IDs
                found_chunks = re.findall(r"Chunk:\s*([a-zA-Z0-9_\-]+)", str(content))
                for cid in found_chunks:
                    doc_ids.add(cid.split("_c")[0])

        return sorted(list(doc_ids)), retrieval_latency

    def _extract_retrieved_chunks(
        self, messages: list[Any]
    ) -> list[RetrievedChunkOutput]:
        """Extract retrieved chunks and document metadata from message trace."""
        chunks: list[RetrievedChunkOutput] = []
        pattern = re.compile(
            r"--- Document #\d+:\s*([^\(\n]+?)\s*\(ID:\s*([^,\)]+),\s*Chunk:\s*([^\)]+)\)\s*---\s*\n"
            r"(?:<retrieved_policy_chunk[^>]*>\s*)?"
            r"(.*?)"
            r"(?:\s*</retrieved_policy_chunk>|\s*(?=\n--- Document #)|\Z)",
            re.DOTALL,
        )
        for msg in messages:
            content = str(getattr(msg, "content", ""))
            if isinstance(msg, ToolMessage) or getattr(msg, "name", None) in {
                "search_policy_documents",
                "search_documents",
            }:
                matches = pattern.findall(content)
                for idx, match in enumerate(matches, start=1):
                    doc_name, doc_id, chunk_id, text = match
                    chunks.append(
                        RetrievedChunkOutput(
                            chunk_id=chunk_id.strip(),
                            document_id=doc_id.strip(),
                            document_name=doc_name.strip(),
                            content=text.strip(),
                            fusion_score=0.016,
                            rank=idx,
                        )
                    )
        return chunks

    def _extract_citations(self, answer_text: str) -> list[str]:
        """Extract cited document names from answer References section."""
        citations: list[str] = []
        if "Reference:" in answer_text or "References:" in answer_text:
            ref_part = answer_text.split("Reference:")[-1]
            if "References:" in answer_text:
                ref_part = answer_text.split("References:")[-1]
            lines = self._CITATION_LINE_RE.findall(ref_part)
            for line in lines:
                clean_cite = line.strip().rstrip(".").strip()
                if clean_cite and len(clean_cite) < 120:
                    citations.append(clean_cite)
        return citations

    def _is_out_of_scope_response(self, answer_text: str) -> bool:
        """Determine whether response indicates query was out of scope or ungrounded."""
        lowered = answer_text.lower()
        return any(phrase in lowered for phrase in self._OUT_OF_SCOPE_PHRASES)

    async def run(
        self,
        query: str,
        thread_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AgentResponse:
        """Execute full agent workflow with timing, provenance, and grounding guarantees.

        Args:
            query: User's question or instruction.
            thread_id: Conversation session identifier (auto-generates unique ID if None).
            request_id: Unique trace identifier.
            user_id: Optional user identifier.

        Returns:
            AgentResponse containing answer text, execution metadata, and message trace.
        """
        start_total = time.perf_counter()
        req_id = request_id or str(uuid.uuid4())
        th_id = thread_id or f"thread_{uuid.uuid4().hex[:12]}"
        tracer = ObservabilityTracer(
            request_id=req_id,
            thread_id=th_id,
            user_id=user_id,
            model=config.text_model,
        )

        with set_request_context(
            request_id=req_id, thread_id=th_id, user_id=user_id, tracer=tracer
        ):
            safe_query = mask_sensitive(query.strip())
            logger.info(
                f"[AGENT:RUN] Request: {req_id} | Thread: {th_id} | User: {user_id} | Query: '{safe_query}'"
            )

            # 1. Query Understanding & Input Validation
            if not query or not query.strip():
                logger.warning("[AGENT:RUN] Empty query received.")
                tracer.record_error(
                    category=ErrorCategory.VALIDATION_ERROR,
                    message="Empty query received",
                    recoverable=False,
                )
                trace_summary = tracer.finish(status="blocked")
                elapsed = (time.perf_counter() - start_total) * 1000.0
                meta = AgentExecutionMetadata(
                    request_id=req_id,
                    thread_id=th_id,
                    user_id=user_id,
                    model_name=config.text_model,
                    total_latency_ms=round(elapsed, 2),
                    token_usage=tracer.token_usage,
                    errors=tracer.errors,
                    trace=trace_summary.model_dump(),
                    guardrail_result=GuardrailResult(
                        is_safe=True,
                        decision=DecisionCategory.INSUFFICIENT_EVIDENCE,
                        sanitized_query="",
                    ),
                )
                return AgentResponse(
                    answer="Please provide a valid question regarding Company XYZ policies.",
                    metadata=meta,
                    decision=DecisionCategory.INSUFFICIENT_EVIDENCE,
                    is_out_of_scope=True,
                    messages=[],
                )

            # 2. Input Guardrails: Prompt injection & Out-of-domain detection
            input_guardrail = self.guardrails.validate_input(query)
            if not input_guardrail.is_safe:
                tracer.record_error(
                    category=ErrorCategory.GUARDRAIL_BLOCK,
                    message="Direct prompt injection or security policy violation blocked",
                    details={
                        "violations": [
                            v.model_dump() for v in input_guardrail.violations
                        ]
                    },
                    recoverable=False,
                )
                trace_summary = tracer.finish(status="blocked")
                elapsed = (time.perf_counter() - start_total) * 1000.0
                meta = AgentExecutionMetadata(
                    request_id=req_id,
                    thread_id=th_id,
                    user_id=user_id,
                    model_name=config.text_model,
                    total_latency_ms=round(elapsed, 2),
                    token_usage=tracer.token_usage,
                    errors=tracer.errors,
                    trace=trace_summary.model_dump(),
                    guardrail_result=input_guardrail,
                )
                return AgentResponse(
                    answer="Your request could not be processed due to safety policy violations.",
                    metadata=meta,
                    decision=DecisionCategory.OUT_OF_DOMAIN,
                    is_out_of_scope=True,
                    messages=[],
                )

            if input_guardrail.decision == DecisionCategory.OUT_OF_DOMAIN:
                tracer.record_error(
                    category=ErrorCategory.GUARDRAIL_BLOCK,
                    message="Query identified as outside Company XYZ knowledge domain",
                    details={
                        "violations": [
                            v.model_dump() for v in input_guardrail.violations
                        ]
                    },
                    recoverable=True,
                )
                trace_summary = tracer.finish(status="blocked")
                elapsed = (time.perf_counter() - start_total) * 1000.0
                meta = AgentExecutionMetadata(
                    request_id=req_id,
                    thread_id=th_id,
                    user_id=user_id,
                    model_name=config.text_model,
                    total_latency_ms=round(elapsed, 2),
                    token_usage=tracer.token_usage,
                    errors=tracer.errors,
                    trace=trace_summary.model_dump(),
                    guardrail_result=input_guardrail,
                )
                return AgentResponse(
                    answer="I am dedicated solely to answering questions about Company XYZ internal policies. This question is outside my knowledge scope.",
                    metadata=meta,
                    decision=DecisionCategory.OUT_OF_DOMAIN,
                    is_out_of_scope=True,
                    messages=[],
                )

            # 3. Invoke LangGraph Agent Graph (Orchestrating Tool Selection & Retrieval)
            run_config = get_langchain_run_config(
                request_id=req_id,
                thread_id=th_id,
                user_id=user_id,
                cfg=config,
            )

            t_model_start = time.perf_counter()
            try:
                async with tracer.async_span(
                    "llm:agent_graph", {"model": config.text_model}
                ):
                    result = await self.agent_graph.ainvoke(
                        {"messages": [HumanMessage(content=query)]},
                        config=run_config,
                    )
            except Exception as e:
                elapsed = (time.perf_counter() - start_total) * 1000.0
                safe_err = mask_sensitive(str(e))
                logger.error(
                    f"[AGENT:RUN] Agent graph execution failed: {safe_err}",
                    exc_info=True,
                )

                is_timeout = isinstance(e, TimeoutError) or (
                    "timeout" in str(e).lower()
                )
                err_category = (
                    ErrorCategory.TIMEOUT if is_timeout else ErrorCategory.MODEL_ERROR
                )
                tracer.record_error(
                    category=err_category,
                    message=f"Agent graph execution failed: {safe_err}",
                    exc=e,
                    recoverable=False,
                )
                trace_summary = tracer.finish(status="failed")

                sys_fail_result = GuardrailResult(
                    is_safe=False,
                    decision=DecisionCategory.SYSTEM_FAILURE,
                    violations=[
                        GuardrailViolation(
                            violation_type=ViolationType.SYSTEM_ERROR,
                            message=f"Agent graph execution failed: {safe_err}",
                            severity="critical",
                        )
                    ],
                )
                meta = AgentExecutionMetadata(
                    request_id=req_id,
                    thread_id=th_id,
                    user_id=user_id,
                    model_name=config.text_model,
                    total_latency_ms=round(elapsed, 2),
                    token_usage=tracer.token_usage,
                    errors=tracer.errors,
                    trace=trace_summary.model_dump(),
                    guardrail_result=sys_fail_result,
                )
                return AgentResponse(
                    answer=f"I encountered an error retrieving policy information: {safe_err}",
                    metadata=meta,
                    decision=DecisionCategory.SYSTEM_FAILURE,
                    is_out_of_scope=False,
                    messages=[],
                )

            model_latency_ms = (time.perf_counter() - t_model_start) * 1000.0
            total_latency_ms = (time.perf_counter() - start_total) * 1000.0

            messages = result.get("messages", []) if isinstance(result, dict) else []
            final_message = (
                messages[-1]
                if (isinstance(messages, list) and messages)
                else AIMessage(content="")
            )
            answer_text = str(getattr(final_message, "content", ""))

            # Extract token usage from messages
            prompt_tokens = 0
            completion_tokens = 0
            for msg in messages:
                if hasattr(msg, "usage_metadata") and isinstance(
                    msg.usage_metadata, dict
                ):
                    prompt_tokens += msg.usage_metadata.get("input_tokens", 0)
                    completion_tokens += msg.usage_metadata.get("output_tokens", 0)
                elif hasattr(msg, "response_metadata") and isinstance(
                    msg.response_metadata, dict
                ):
                    tu = msg.response_metadata.get("token_usage", {})
                    if isinstance(tu, dict):
                        prompt_tokens += tu.get("prompt_tokens", 0)
                        completion_tokens += tu.get("completion_tokens", 0)

            tracer.record_llm_call(
                model=config.text_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=model_latency_ms,
            )

            # 4, 5, 6, 7. Synthesis, Provenance, and Guardrail Grounding Evaluation
            retrieved_doc_ids, ret_latency = self._extract_retrieval_info(messages)
            retrieved_chunks = self._extract_retrieved_chunks(messages)
            citations = self._extract_citations(answer_text)

            tracer.record_retrieval(
                query=query,
                chunks_count=len(retrieved_chunks),
                latency_ms=ret_latency,
                document_ids=retrieved_doc_ids,
            )

            # Inspect tool messages for low confidence, empty, or error signals
            has_tool_error = False
            has_low_confidence = False
            has_empty_tool = False
            for msg in messages:
                if isinstance(msg, ToolMessage) or getattr(msg, "name", None) in {
                    "search_policy_documents",
                    "search_documents",
                }:
                    c_str = str(getattr(msg, "content", ""))
                    if "[ERROR]" in c_str:
                        has_tool_error = True
                        tracer.record_error(
                            category=ErrorCategory.RETRIEVAL_ERROR,
                            message=f"Tool execution returned error: {mask_sensitive(c_str[:120])}",
                            recoverable=False,
                        )
                    if "[LOW_CONFIDENCE]" in c_str:
                        has_low_confidence = True
                        tracer.record_error(
                            category=ErrorCategory.GUARDRAIL_BLOCK,
                            message="Retrieval fell below relevance confidence threshold",
                            recoverable=True,
                        )
                    if "[EMPTY]" in c_str:
                        has_empty_tool = True
                        tracer.record_error(
                            category=ErrorCategory.RETRIEVAL_ERROR,
                            message="Retrieval returned no policy documents",
                            recoverable=True,
                        )

            prelim_decision = DecisionCategory.SUPPORTED_BY_EVIDENCE
            prelim_violations = list(input_guardrail.violations)

            if has_tool_error:
                prelim_decision = DecisionCategory.SYSTEM_FAILURE
                prelim_violations.append(
                    GuardrailViolation(
                        violation_type=ViolationType.SYSTEM_ERROR,
                        message="Tool execution returned error",
                        severity="critical",
                    )
                )
            elif has_low_confidence:
                prelim_decision = DecisionCategory.INSUFFICIENT_EVIDENCE
                prelim_violations.append(
                    GuardrailViolation(
                        violation_type=ViolationType.LOW_CONFIDENCE,
                        message="Retrieval fell below relevance confidence threshold",
                        severity="warning",
                    )
                )
            elif has_empty_tool:
                prelim_decision = DecisionCategory.INSUFFICIENT_EVIDENCE
                prelim_violations.append(
                    GuardrailViolation(
                        violation_type=ViolationType.EMPTY_RETRIEVAL,
                        message="Retrieval returned no policy documents",
                        severity="warning",
                    )
                )

            context_result = GuardrailResult(
                is_safe=input_guardrail.is_safe,
                decision=prelim_decision,
                violations=prelim_violations,
                sanitized_query=input_guardrail.sanitized_query,
            )

            # Output guardrails validation
            safe_answer, guardrail_result = self.guardrails.validate_output(
                answer_text=answer_text,
                chunks=retrieved_chunks,
                context_result=context_result,
            )

            if not guardrail_result.is_safe:
                tracer.record_error(
                    category=ErrorCategory.GUARDRAIL_BLOCK,
                    message="Output failed safety policy",
                    recoverable=False,
                )
            elif guardrail_result.rejected_citations:
                tracer.record_error(
                    category=ErrorCategory.GUARDRAIL_BLOCK,
                    message=f"Fabricated citations rejected: {guardrail_result.rejected_citations}",
                    recoverable=True,
                )
            elif guardrail_result.decision == DecisionCategory.INSUFFICIENT_EVIDENCE:
                tracer.record_error(
                    category=ErrorCategory.GUARDRAIL_BLOCK,
                    message="Output lacked sufficient grounding evidence",
                    recoverable=True,
                )

            tracer.record_evaluation_metadata(
                {
                    "decision": guardrail_result.decision.value,
                    "confidence_score": guardrail_result.confidence_score,
                    "grounding_score": guardrail_result.grounding_score,
                    "citations": citations,
                    "validated_citations": guardrail_result.validated_citations,
                    "rejected_citations": guardrail_result.rejected_citations,
                }
            )

            is_out_of_scope = guardrail_result.decision in (
                DecisionCategory.OUT_OF_DOMAIN,
                DecisionCategory.INSUFFICIENT_EVIDENCE,
            ) or self._is_out_of_scope_response(safe_answer)

            trace_summary = tracer.finish()

            metadata = AgentExecutionMetadata(
                request_id=req_id,
                thread_id=th_id,
                user_id=user_id,
                model_name=config.text_model,
                retrieval_latency_ms=round(ret_latency, 2),
                model_latency_ms=round(model_latency_ms, 2),
                total_latency_ms=round(total_latency_ms, 2),
                token_usage=tracer.token_usage,
                errors=tracer.errors,
                retrieved_document_ids=retrieved_doc_ids,
                retrieved_chunks=retrieved_chunks,
                citations=citations,
                guardrail_result=guardrail_result,
                trace=trace_summary.model_dump(),
            )

            logger.info(
                f"[AGENT:DONE] Request: {req_id} | Total: {total_latency_ms:.1f}ms | "
                f"Tokens: {tracer.token_usage.total_tokens} | Cost: ${tracer.token_usage.estimated_cost_usd:.5f} | "
                f"Decision: {guardrail_result.decision.value} | Retrieved Docs: {len(retrieved_doc_ids)} | "
                f"Citations: {len(citations)} | OOS: {is_out_of_scope}"
            )

            return AgentResponse(
                answer=safe_answer,
                metadata=metadata,
                decision=guardrail_result.decision,
                is_out_of_scope=is_out_of_scope,
                messages=messages,
            )

    async def ainvoke(
        self, input_data: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """LangGraph-compatible entry point preserving message dict interface with enriched metadata.

        Args:
            input_data: Dictionary containing 'messages' list.
            **kwargs: Extra arguments forwarded to graph (supports config, configurable, thread_id, user_id).

        Returns:
            Dictionary with 'messages' plus structured execution metadata.
        """
        messages_input = input_data.get("messages", [])
        last_user_query = ""
        for msg in reversed(messages_input):
            if isinstance(msg, dict) and msg.get("role") == "user":
                last_user_query = msg.get("content", "")
                break
            elif isinstance(msg, HumanMessage):
                last_user_query = str(msg.content)
                break

        # Extract thread_id from input_data, kwargs, or nested configurable dicts
        thread_id = (
            input_data.get("thread_id")
            or kwargs.get("thread_id")
            or kwargs.get("config", {}).get("configurable", {}).get("thread_id")
            or input_data.get("config", {}).get("configurable", {}).get("thread_id")
        )
        user_id = (
            input_data.get("user_id")
            or kwargs.get("user_id")
            or kwargs.get("config", {}).get("configurable", {}).get("user_id")
            or input_data.get("config", {}).get("configurable", {}).get("user_id")
        )
        request_id = input_data.get("request_id") or kwargs.get("request_id")

        response = await self.run(
            query=last_user_query,
            thread_id=thread_id,
            request_id=request_id,
            user_id=user_id,
        )

        # Merge result into LangGraph return format
        return {
            "messages": response.messages,
            "request_id": response.metadata.request_id,
            "thread_id": response.metadata.thread_id,
            "user_id": response.metadata.user_id,
            "model_name": response.metadata.model_name,
            "retrieval_latency_ms": response.metadata.retrieval_latency_ms,
            "model_latency_ms": response.metadata.model_latency_ms,
            "total_latency_ms": response.metadata.total_latency_ms,
            "token_usage": (
                response.metadata.token_usage.model_dump()
                if response.metadata.token_usage
                else None
            ),
            "errors": [e.model_dump() for e in response.metadata.errors],
            "trace": response.metadata.trace,
            "retrieved_document_ids": response.metadata.retrieved_document_ids,
            "citations": response.metadata.citations,
            "decision": response.decision.value,
            "guardrail_result": (
                response.metadata.guardrail_result.model_dump()
                if response.metadata.guardrail_result
                else None
            ),
            "is_out_of_scope": response.is_out_of_scope,
        }
