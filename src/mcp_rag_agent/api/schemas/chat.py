"""Pydantic schemas for /api/v1/chat endpoint."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for conversational chat endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The user's question or instruction regarding Company XYZ policies.",
        examples=["In the UK, how many days of annual leave do employees receive?"],
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional conversation thread identifier to resume previous dialogue. Auto-generated if omitted.",
        examples=["th_12345678"],
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user identifier for session tracking.",
        examples=["user_emp_42"],
    )


class ChatResponseMetadata(BaseModel):
    """Operational latency and grounding metadata (Zero-CoT safe)."""

    retrieval_latency_ms: float = Field(
        ..., description="Time spent retrieving document candidates in milliseconds."
    )
    total_latency_ms: float = Field(
        ..., description="Total end-to-end processing latency in milliseconds."
    )
    model_latency_ms: Optional[float] = Field(
        default=None, description="Time spent in LLM reasoning in milliseconds."
    )
    model_name: Optional[str] = Field(
        default="gpt-4.1", description="Name of the generative model utilized."
    )
    decision: Optional[str] = Field(
        default="supported_by_evidence",
        description="4-tier grounding decision taxonomy.",
    )
    token_usage: Optional[dict[str, Any]] = Field(
        default=None,
        description="Aggregated token counts and estimated inference cost.",
    )


class SourceDocument(BaseModel):
    """Detailed source document and chunk information for citation inspection."""

    document_name: str = Field(..., description="Document filename or title.")
    document_id: Optional[str] = Field(default=None, description="Document identifier.")
    chunk_id: Optional[str] = Field(
        default=None, description="Unique chunk identifier."
    )
    content: Optional[str] = Field(default=None, description="Text passage excerpt.")
    fusion_score: Optional[float] = Field(
        default=None, description="Retrieval fusion score."
    )
    rank: Optional[int] = Field(default=None, description="Retrieval rank.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata dictionary."
    )


class ChatResponse(BaseModel):
    """Response model for conversational chat endpoint."""

    answer: str = Field(..., description="Grounded, policy-compliant answer text.")
    citations: list[str] = Field(
        default_factory=list,
        description="List of verified policy documents cited in the answer.",
    )
    sources: list[SourceDocument] = Field(
        default_factory=list,
        description="Detailed source documents and passages supporting the answer.",
    )
    thread_id: str = Field(..., description="Active conversation session identifier.")
    request_id: str = Field(..., description="Unique request trace identifier.")
    metadata: ChatResponseMetadata = Field(
        ..., description="Operational execution metadata."
    )
