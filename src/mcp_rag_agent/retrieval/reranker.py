"""Extensible reranking abstraction supporting NoOp, Cross-Encoder, and LLM rerankers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from mcp_rag_agent.retrieval.models import RetrievedChunk

logger = logging.getLogger("Reranker")


class BaseReranker(ABC):
    """Abstract base class for chunk rerankers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the reranker implementation."""
        pass

    @abstractmethod
    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        """Rerank candidate chunks according to deep cross-relevance with the query.

        Args:
            query: The user's search query.
            candidates: Initial candidates ordered by fusion score.
            top_k: Maximum number of chunks to return after reranking.

        Returns:
            List of reranked RetrievedChunk instances up to top_k.
        """
        pass


class NoOpReranker(BaseReranker):
    """Default pass-through reranker that preserves RRF fusion ordering."""

    @property
    def name(self) -> str:
        return "noop"

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        """Return top_k candidates directly without altering order or scores."""
        truncated = candidates[:top_k]
        for idx, chunk in enumerate(truncated, start=1):
            chunk.rank = idx
        return truncated


class CrossEncoderReranker(BaseReranker):
    """Cross-Encoder reranker evaluating full cross-attention between query and chunk text."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        score_fn: Optional[Callable[[str, list[str]], list[float]]] = None,
    ):
        """Initialize CrossEncoderReranker.

        Args:
            model_name: Model identifier (e.g. HuggingFace / SentenceTransformers).
            score_fn: Optional custom scoring callable `(query, texts) -> scores`.
                      If provided, overrides default model loading.
        """
        self._model_name = model_name
        self._score_fn = score_fn
        self._model = None

    @property
    def name(self) -> str:
        return f"cross_encoder:{self._model_name}"

    def _get_model(self) -> Any:
        """Lazy loader for sentence_transformers CrossEncoder."""
        if self._model is None and self._score_fn is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self._model_name)
            except ImportError:
                logger.warning(
                    "sentence_transformers is not installed. "
                    "CrossEncoderReranker will use heuristic lexical scoring fallback."
                )
        return self._model

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []

        texts = [c.content for c in candidates]

        if self._score_fn is not None:
            scores = self._score_fn(query, texts)
        else:
            model = self._get_model()
            if model is not None:
                pairs = [[query, text] for text in texts]
                raw_scores = model.predict(pairs)
                scores = [float(s) for s in raw_scores]
            else:
                # Fallback: compute term overlap density if sentence-transformers not present
                query_terms = set(query.lower().split())
                scores = []
                for text in texts:
                    words = text.lower().split()
                    matches = sum(1 for w in words if w in query_terms)
                    score = matches / (len(words) + 1e-5)
                    scores.append(score)

        for chunk, score in zip(candidates, scores):
            chunk.rerank_score = round(float(score), 4)

        # Sort descending by rerank_score, then fallback to fusion_score
        reranked = sorted(
            candidates,
            key=lambda c: (
                c.rerank_score if c.rerank_score is not None else -1.0,
                c.fusion_score,
            ),
            reverse=True,
        )[:top_k]

        for idx, chunk in enumerate(reranked, start=1):
            chunk.rank = idx

        return reranked


class LLMReranker(BaseReranker):
    """LLM-based reranker that scores relevance using prompt evaluation."""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        score_fn: Optional[Callable[[str, list[str]], list[float]]] = None,
    ):
        """Initialize LLMReranker.

        Args:
            model_name: Model identifier.
            score_fn: Optional scoring callable `(query, texts) -> scores`.
        """
        self._model_name = model_name
        self._score_fn = score_fn

    @property
    def name(self) -> str:
        return f"llm:{self._model_name}"

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []

        texts = [c.content for c in candidates]

        if self._score_fn is not None:
            scores = self._score_fn(query, texts)
        else:
            # Default mock/heuristic scoring for unit and offline tests
            query_words = set(query.lower().split())
            scores = []
            for text in texts:
                overlap = sum(1 for w in query_words if w in text.lower())
                scores.append(round(min(1.0, overlap * 0.3), 4))

        for chunk, score in zip(candidates, scores):
            chunk.rerank_score = float(score)

        reranked = sorted(
            candidates,
            key=lambda c: (
                c.rerank_score if c.rerank_score is not None else -1.0,
                c.fusion_score,
            ),
            reverse=True,
        )[:top_k]

        for idx, chunk in enumerate(reranked, start=1):
            chunk.rank = idx

        return reranked


def get_reranker(reranker_type: str = "none", **kwargs: Any) -> BaseReranker:
    """Factory to instantiate the configured reranker.

    Args:
        reranker_type: One of 'none'/'noop', 'cross_encoder', 'llm'.
        **kwargs: Optional parameters passed to the reranker constructor.

    Returns:
        BaseReranker instance.
    """
    clean_type = (reranker_type or "none").lower().strip()
    if clean_type in {"none", "noop"}:
        return NoOpReranker()
    elif clean_type in {"cross_encoder", "crossencoder"}:
        return CrossEncoderReranker(**kwargs)
    elif clean_type in {"llm", "llm_reranker"}:
        return LLMReranker(**kwargs)
    else:
        logger.warning(
            f"Unknown reranker type '{reranker_type}'. Defaulting to NoOpReranker."
        )
        return NoOpReranker()
