"""Observability tracer tracking spans, latencies, tokens, costs, and categorized errors."""

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Generator, Optional

from mcp_rag_agent.observability.context import (
    get_request_id,
    get_thread_id,
    get_user_id,
)
from mcp_rag_agent.observability.models import (
    ErrorCategory,
    ErrorRecord,
    RequestTrace,
    TokenUsage,
    TraceSpan,
)

logger = logging.getLogger("ObservabilityTracer")

# Rate cards per 1M tokens (USD)
RATE_CARDS: dict[str, tuple[float, float]] = {
    # model: (input_per_million, output_per_million)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
    "default": (0.15, 0.60),
}


def calculate_cost_usd(
    model_name: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Calculate inference cost in USD given model and token counts."""
    matched_key = "default"
    lowered = model_name.lower()
    for key in RATE_CARDS:
        if key in lowered:
            matched_key = key
            break
    input_rate, output_rate = RATE_CARDS[matched_key]
    cost = (prompt_tokens / 1_000_000.0) * input_rate + (
        completion_tokens / 1_000_000.0
    ) * output_rate
    return round(cost, 6)


class ObservabilityTracer:
    """End-to-end request tracer recording operational metrics, spans, and errors."""

    def __init__(
        self,
        request_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: str = "gpt-4.1",
    ):
        self.request_id = request_id or get_request_id() or "unknown_req"
        self.thread_id = thread_id or get_thread_id() or "unknown_thread"
        self.user_id = user_id or get_user_id()
        self.model = model
        self.start_time = time.perf_counter()

        self.retrieval_query: Optional[str] = None
        self.number_of_retrieved_chunks: int = 0
        self.retrieval_latency_ms: float = 0.0
        self.llm_latency_ms: float = 0.0
        self.total_latency_ms: float = 0.0

        self.token_usage = TokenUsage()
        self.errors: list[ErrorRecord] = []
        self.spans: list[TraceSpan] = []
        self.evaluation_metadata: dict[str, Any] = {}
        self.status: str = "running"

    @contextmanager
    def span(
        self, name: str, attributes: Optional[dict[str, Any]] = None
    ) -> Generator[TraceSpan, None, None]:
        """Synchronous context manager for tracing an operational step."""
        span_obj = TraceSpan(
            name=name,
            attributes=attributes or {},
        )
        t0 = time.perf_counter()
        try:
            yield span_obj
        except Exception as exc:
            span_obj.status = "error"
            span_obj.duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            span_obj.error = ErrorRecord(
                category=(
                    ErrorCategory.MODEL_ERROR
                    if "llm" in name
                    else (
                        ErrorCategory.DATABASE_ERROR
                        if "mongo" in name
                        else ErrorCategory.RETRIEVAL_ERROR
                    )
                ),
                message=str(exc),
                details={"span": name},
            )
            self.spans.append(span_obj)
            raise
        else:
            span_obj.duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            self.spans.append(span_obj)

    @asynccontextmanager
    async def async_span(
        self, name: str, attributes: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[TraceSpan, None]:
        """Asynchronous context manager for tracing an operational step."""
        span_obj = TraceSpan(
            name=name,
            attributes=attributes or {},
        )
        t0 = time.perf_counter()
        try:
            yield span_obj
        except Exception as exc:
            span_obj.status = "error"
            span_obj.duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            span_obj.error = ErrorRecord(
                category=(
                    ErrorCategory.MODEL_ERROR
                    if "llm" in name
                    else (
                        ErrorCategory.DATABASE_ERROR
                        if "mongo" in name
                        else ErrorCategory.RETRIEVAL_ERROR
                    )
                ),
                message=str(exc),
                details={"span": name},
            )
            self.spans.append(span_obj)
            raise
        else:
            span_obj.duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            self.spans.append(span_obj)

    def record_tool_call(
        self,
        tool_name: str,
        query: str,
        chunks_count: int,
        latency_ms: float,
        status: str = "success",
    ) -> None:
        """Record tool invocation telemetry."""
        self.spans.append(
            TraceSpan(
                name=f"tool:{tool_name}",
                duration_ms=round(latency_ms, 2),
                attributes={"query": query, "chunks_found": chunks_count},
                status=status,
            )
        )

    def record_retrieval(
        self,
        query: str,
        chunks_count: int,
        latency_ms: float,
        document_ids: Optional[list[str]] = None,
    ) -> None:
        """Record retrieval pipeline execution metrics."""
        self.retrieval_query = query
        self.number_of_retrieved_chunks = chunks_count
        self.retrieval_latency_ms = round(latency_ms, 2)
        self.spans.append(
            TraceSpan(
                name="retrieval:pipeline",
                duration_ms=round(latency_ms, 2),
                attributes={
                    "query": query,
                    "chunks_count": chunks_count,
                    "document_ids": document_ids or [],
                },
                status="success" if chunks_count > 0 else "empty",
            )
        )

    def record_database_op(
        self,
        operation: str,
        collection: str,
        latency_ms: float,
        status: str = "success",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record MongoDB database operation telemetry."""
        attrs = {"operation": operation, "collection": collection}
        if details:
            attrs.update(details)
        self.spans.append(
            TraceSpan(
                name=f"mongodb:{operation}",
                duration_ms=round(latency_ms, 2),
                attributes=attrs,
                status=status,
            )
        )

    def record_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> None:
        """Record LLM generation metrics, tokens, and inference cost."""
        self.model = model
        self.llm_latency_ms = round(latency_ms, 2)
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = calculate_cost_usd(model, prompt_tokens, completion_tokens)

        self.token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost_usd,
        )
        self.spans.append(
            TraceSpan(
                name=f"llm:{model}",
                duration_ms=round(latency_ms, 2),
                attributes={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": cost_usd,
                },
                status="success",
            )
        )

    def record_error(
        self,
        category: ErrorCategory,
        message: str,
        details: Optional[dict[str, Any]] = None,
        exc: Optional[Exception] = None,
        recoverable: bool = False,
    ) -> ErrorRecord:
        """Record a categorized error or guardrail trigger."""
        err_details = dict(details or {})
        if exc:
            err_details["exception_type"] = type(exc).__name__

        error_rec = ErrorRecord(
            category=category,
            message=message,
            details=err_details,
            recoverable=recoverable,
        )
        self.errors.append(error_rec)
        logger.warning(
            f"[{category.value}] req:{self.request_id} th:{self.thread_id} - {message} "
            f"(recoverable={recoverable})"
        )
        return error_rec

    def record_evaluation_metadata(self, metadata: dict[str, Any]) -> None:
        """Record guardrail decisions and factual grounding scores."""
        self.evaluation_metadata.update(metadata)

    def finish(self, status: Optional[str] = None) -> RequestTrace:
        """Finish the trace and generate immutable RequestTrace snapshot."""
        self.total_latency_ms = round(
            (time.perf_counter() - self.start_time) * 1000.0, 2
        )
        if status:
            self.status = status
        elif self.errors and any(not e.recoverable for e in self.errors):
            self.status = "failed"
        elif any(e.category == ErrorCategory.GUARDRAIL_BLOCK for e in self.errors):
            self.status = "blocked"
        else:
            self.status = "completed"

        return RequestTrace(
            request_id=self.request_id,
            thread_id=self.thread_id,
            user_id=self.user_id,
            model=self.model,
            retrieval_query=self.retrieval_query,
            number_of_retrieved_chunks=self.number_of_retrieved_chunks,
            retrieval_latency_ms=self.retrieval_latency_ms,
            llm_latency_ms=self.llm_latency_ms,
            total_latency_ms=self.total_latency_ms,
            token_usage=self.token_usage,
            errors=self.errors,
            spans=self.spans,
            evaluation_metadata=self.evaluation_metadata,
            status=self.status,
        )
