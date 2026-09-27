"""Data models for Phase 8: Production Observability, telemetry, tracing, and error taxonomy."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    """Standardized error categories for end-to-end AI system diagnostics."""

    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    MCP_ERROR = "MCP_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    GUARDRAIL_BLOCK = "GUARDRAIL_BLOCK"
    TIMEOUT = "TIMEOUT"


class ErrorRecord(BaseModel):
    """Detailed record of an error or guardrail trigger occurring during execution."""

    category: ErrorCategory = Field(..., description="Standardized error category")
    message: str = Field(
        ..., description="Human-readable error description (sanitized)"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of occurrence",
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic attributes and context"
    )
    recoverable: bool = Field(
        False, description="Whether the system degraded gracefully from this error"
    )


class TokenUsage(BaseModel):
    """Token consumption and financial accounting for LLM invocations."""

    prompt_tokens: int = Field(
        0, description="Tokens used for input prompt and context"
    )
    completion_tokens: int = Field(0, description="Tokens used for generated response")
    total_tokens: int = Field(0, description="Total tokens consumed")
    estimated_cost_usd: float = Field(
        0.0, description="Estimated inference cost in USD"
    )


class TraceSpan(BaseModel):
    """Discrete operational span representing a sub-task in the execution pipeline."""

    span_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8], description="Span identifier"
    )
    parent_id: Optional[str] = Field(None, description="Parent span identifier")
    name: str = Field(
        ..., description="Name of the operation (e.g. 'retrieval', 'llm', 'mongodb')"
    )
    start_time_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Span start timestamp",
    )
    duration_ms: float = Field(0.0, description="Duration of the span in milliseconds")
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Span attributes and metadata"
    )
    status: str = Field(
        "success", description="Span status: 'success', 'error', or 'skipped'"
    )
    error: Optional[ErrorRecord] = Field(
        None, description="Error details if the span failed"
    )


class RequestTrace(BaseModel):
    """End-to-end execution trace capturing metrics from Request through Response."""

    request_id: str = Field(..., description="Unique request trace identifier")
    thread_id: str = Field(..., description="Conversation session identifier")
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    model: str = Field("unknown", description="Name of LLM or embedding model utilized")
    retrieval_query: Optional[str] = Field(
        None, description="Actual query passed to retrieval"
    )
    number_of_retrieved_chunks: int = Field(
        0, description="Count of retrieved chunks exposed to context"
    )
    retrieval_latency_ms: float = Field(
        0.0, description="Time spent in retrieval operations"
    )
    llm_latency_ms: float = Field(
        0.0, description="Time spent in LLM reasoning and generation"
    )
    total_latency_ms: float = Field(0.0, description="Total end-to-end request latency")
    token_usage: TokenUsage = Field(
        default_factory=TokenUsage, description="Aggregated token usage and cost"
    )
    errors: list[ErrorRecord] = Field(
        default_factory=list, description="List of errors or violations encountered"
    )
    spans: list[TraceSpan] = Field(
        default_factory=list, description="Sub-operational trace spans"
    )
    evaluation_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Grounding & guardrail metrics"
    )
    status: str = Field(
        "completed", description="Execution status: 'completed', 'blocked', 'failed'"
    )
