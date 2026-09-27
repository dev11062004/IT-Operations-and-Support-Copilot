"""Advanced Retrieval Subsystem for MCP RAG Agent.

Provides production-grade query preprocessing, candidate over-fetching,
Reciprocal Rank Fusion (RRF), deduplication, pluggable reranking,
latency tracking, and transparent debug tracing.
"""

from mcp_rag_agent.retrieval.models import (
    CandidateItem,
    RetrievalDebugInfo,
    RetrievalLatency,
    RetrievalResult,
    RetrievedChunk,
)
from mcp_rag_agent.retrieval.pipeline import AdvancedRetriever
from mcp_rag_agent.retrieval.preprocessor import PreprocessedQuery, QueryPreprocessor
from mcp_rag_agent.retrieval.reranker import (
    BaseReranker,
    CrossEncoderReranker,
    LLMReranker,
    NoOpReranker,
    get_reranker,
)

__all__ = [
    # Pipeline
    "AdvancedRetriever",
    # Models
    "RetrievedChunk",
    "RetrievalResult",
    "RetrievalLatency",
    "RetrievalDebugInfo",
    "CandidateItem",
    # Preprocessor
    "QueryPreprocessor",
    "PreprocessedQuery",
    # Rerankers
    "BaseReranker",
    "NoOpReranker",
    "CrossEncoderReranker",
    "LLMReranker",
    "get_reranker",
]
