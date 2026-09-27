"""Data models for advanced hybrid retrieval, ranking, and observability."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """Represents a final retrieved chunk with ranking provenance and metadata."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document identifier")
    document_name: str = Field(..., description="Source document filename or title")
    content: str = Field(..., description="Text content of the retrieved chunk")
    vector_score: Optional[float] = Field(
        None, description="Raw cosine vector similarity score"
    )
    keyword_score: Optional[float] = Field(
        None, description="Raw keyword/BM25/text relevance score"
    )
    fusion_score: float = Field(
        ..., description="Combined Reciprocal Rank Fusion (RRF) score"
    )
    rerank_score: Optional[float] = Field(
        None, description="Score assigned by optional reranker"
    )
    rank: int = Field(..., description="Final 1-indexed rank position in output")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Preserved chunk metadata"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert chunk into standard dictionary representation."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "content": self.content,
            "vector_score": self.vector_score,
            "keyword_score": self.keyword_score,
            "fusion_score": self.fusion_score,
            "rerank_score": self.rerank_score,
            "rank": self.rank,
            "metadata": self.metadata,
        }


class CandidateItem(BaseModel):
    """Intermediate candidate document from vector or keyword search."""

    doc_id: str = Field(
        ..., description="Unique identifier of candidate (chunk_id or _id)"
    )
    content: str = Field(..., description="Text content")
    score: float = Field(..., description="Search score from single modality")
    rank: int = Field(..., description="1-indexed rank in single modality search")
    source: str = Field(
        ..., description="Search modality source ('vector' or 'keyword')"
    )
    document: dict[str, Any] = Field(
        default_factory=dict, description="Raw document dictionary"
    )


class RetrievalLatency(BaseModel):
    """Detailed timing metrics across retrieval stages in milliseconds."""

    query_preprocessing_ms: float = Field(
        0.0, description="Query sanitization & normalization latency"
    )
    vector_search_ms: float = Field(0.0, description="Vector similarity search latency")
    keyword_search_ms: float = Field(
        0.0, description="Full-text keyword search latency"
    )
    fusion_ms: float = Field(0.0, description="RRF fusion and deduplication latency")
    rerank_ms: float = Field(0.0, description="Reranking model latency")
    total_latency_ms: float = Field(
        0.0, description="Total end-to-end retrieval latency"
    )


class RetrievalDebugInfo(BaseModel):
    """Transparent inspection trace for retrieval debugging (no chain-of-thought)."""

    original_query: str = Field(..., description="Raw user query")
    normalized_query: str = Field(..., description="Sanitized and normalized query")
    vector_candidates: list[dict[str, Any]] = Field(
        default_factory=list, description="Raw candidates from vector search"
    )
    keyword_candidates: list[dict[str, Any]] = Field(
        default_factory=list, description="Raw candidates from keyword search"
    )
    fusion_candidates: list[dict[str, Any]] = Field(
        default_factory=list, description="Fused and deduplicated candidate ranking"
    )
    final_chunks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Final ranked chunks after truncation/reranking",
    )


class RetrievalResult(BaseModel):
    """Full retrieval response containing ranked chunks, latency metrics, and optional debug trace."""

    chunks: list[RetrievedChunk] = Field(
        default_factory=list, description="Ranked retrieved chunks"
    )
    latency: RetrievalLatency = Field(
        default_factory=RetrievalLatency, description="Latency breakdown"
    )
    debug: Optional[RetrievalDebugInfo] = Field(
        None, description="Optional debug trace if debug mode enabled"
    )
