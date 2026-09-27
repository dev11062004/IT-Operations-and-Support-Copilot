"""Advanced hybrid retrieval pipeline combining vector search, keyword search, RRF, and reranking."""

import asyncio
import logging
import time
from typing import Any, Optional

from mcp_rag_agent.core.config import config
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator
from mcp_rag_agent.mongodb.client import MongoDBClient
from mcp_rag_agent.retrieval.models import (
    RetrievalDebugInfo,
    RetrievalLatency,
    RetrievalResult,
    RetrievedChunk,
)
from mcp_rag_agent.retrieval.preprocessor import QueryPreprocessor
from mcp_rag_agent.retrieval.reranker import BaseReranker, get_reranker

logger = logging.getLogger("AdvancedRetriever")


class AdvancedRetriever:
    """Production-grade hybrid retriever featuring over-fetching, RRF fusion, deduplication, and latency tracking."""

    def __init__(
        self,
        mongo_client: MongoDBClient,
        embedding_generator: EmbeddingGenerator,
        preprocessor: Optional[QueryPreprocessor] = None,
        reranker: Optional[BaseReranker] = None,
        default_collection: Optional[str] = None,
        default_vector_index: Optional[str] = None,
        default_text_index: str = "text_index",
        vector_field: str = "embedding",
        text_field: str = "content",
        oversample_factor: Optional[int] = None,
        rrf_k: Optional[int] = None,
    ):
        """Initialize AdvancedRetriever.

        Args:
            mongo_client: Connected MongoDBClient instance.
            embedding_generator: EmbeddingGenerator instance for query embeddings.
            preprocessor: QueryPreprocessor instance.
            reranker: BaseReranker instance.
            default_collection: Target vector/chunk collection name.
            default_vector_index: Vector search index name.
            default_text_index: Full-text search index name.
            vector_field: Embedding field name.
            text_field: Text content field name.
            oversample_factor: Multiplier for candidate over-fetching (default: from config).
            rrf_k: RRF constant dampener (default: from config).
        """
        self.mongo_client = mongo_client
        self.embedding_generator = embedding_generator
        self.preprocessor = preprocessor or QueryPreprocessor()
        self.reranker = reranker or get_reranker(config.retrieval_reranker_type)
        self.default_collection = default_collection or config.db_vector_collection
        self.default_vector_index = default_vector_index or config.db_vector_index_name
        self.default_text_index = default_text_index
        self.vector_field = vector_field
        self.text_field = text_field
        self.oversample_factor = oversample_factor or config.retrieval_oversample_factor
        self.rrf_k = rrf_k or config.retrieval_rrf_k

    @staticmethod
    def _extract_chunk_identity(doc: dict[str, Any]) -> tuple[str, str, str]:
        """Extract chunk_id, document_id, and document_name reliably from raw MongoDB document.

        Returns:
            Tuple of (chunk_id, document_id, document_name).
        """
        meta = doc.get("metadata") or {}

        # 1. chunk_id
        chunk_id = (
            doc.get("chunk_id") or meta.get("chunk_id") or str(doc.get("_id", ""))
        )

        # 2. document_id
        document_id = (
            doc.get("document_id")
            or meta.get("document_id")
            or meta.get("doc_id")
            or chunk_id.split("_c")[0]
        )

        # 3. document_name
        document_name = (
            meta.get("filename")
            or meta.get("document_name")
            or meta.get("title")
            or doc.get("name")
            or "Unknown Document"
        )

        return str(chunk_id), str(document_id), str(document_name)

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        semantic_weight: Optional[float] = None,
        filter_query: Optional[dict[str, Any]] = None,
        debug: bool = False,
        collection_name: Optional[str] = None,
    ) -> RetrievalResult:
        """Execute hybrid search pipeline with candidate over-fetching, RRF fusion, and deduplication.

        Args:
            query: Raw user query text.
            top_k: Number of final chunks to return (default: config.retrieval_top_k).
            semantic_weight: Weight for vector vs keyword search (0.0 to 1.0).
            filter_query: Optional MongoDB filter dictionary.
            debug: If True, attaches detailed execution debug trace.
            collection_name: Target MongoDB collection override.

        Returns:
            RetrievalResult containing ranked chunks, latency metrics, and optional debug trace.
        """
        start_total = time.perf_counter()
        target_top_k = top_k or config.retrieval_top_k
        weight_vec = (
            semantic_weight if semantic_weight is not None else config.semantic_weight
        )
        weight_kw = 1.0 - weight_vec
        col_name = collection_name or self.default_collection
        fetch_limit = target_top_k * self.oversample_factor

        # ---------------------------------------------------------
        # 1. Query Preprocessing & Normalization
        # ---------------------------------------------------------
        t0 = time.perf_counter()
        preprocessed = self.preprocessor.preprocess(query)
        prep_ms = (time.perf_counter() - t0) * 1000.0

        if not preprocessed.normalized_query:
            logger.warning("Empty query received in retriever.")
            return RetrievalResult(
                chunks=[],
                latency=RetrievalLatency(
                    query_preprocessing_ms=prep_ms, total_latency_ms=prep_ms
                ),
            )

        # ---------------------------------------------------------
        # 2. Parallel Candidate Retrieval (Vector & Keyword)
        # ---------------------------------------------------------
        async def fetch_vector_candidates() -> tuple[list[dict[str, Any]], float]:
            t_vec_start = time.perf_counter()
            query_vector = await self.embedding_generator.generate(
                preprocessed.semantic_query
            )
            candidates = self.mongo_client.vector_search(
                collection_name=col_name,
                index_name=self.default_vector_index,
                vector_field=self.vector_field,
                query_vector=query_vector,
                limit=fetch_limit,
                filter_query=filter_query,
            )
            vec_ms = (time.perf_counter() - t_vec_start) * 1000.0
            return candidates, vec_ms

        def fetch_keyword_candidates() -> tuple[list[dict[str, Any]], float]:
            t_kw_start = time.perf_counter()
            candidates = self.mongo_client.text_search(
                collection_name=col_name,
                index_name=self.default_text_index,
                query_text=preprocessed.keyword_query,
                limit=fetch_limit,
                filter_query=filter_query,
            )
            kw_ms = (time.perf_counter() - t_kw_start) * 1000.0
            return candidates, kw_ms

        # Run vector search asynchronously while running keyword search
        (raw_vec_candidates, vec_ms), (raw_kw_candidates, kw_ms) = await asyncio.gather(
            fetch_vector_candidates(),
            asyncio.to_thread(fetch_keyword_candidates),
        )

        # ---------------------------------------------------------
        # 3. Reciprocal Rank Fusion & Deduplication
        # ---------------------------------------------------------
        t_fusion_start = time.perf_counter()
        fused_pool: dict[str, dict[str, Any]] = {}

        # Process vector candidates
        for rank, doc in enumerate(raw_vec_candidates, start=1):
            chunk_id, doc_id, doc_name = self._extract_chunk_identity(doc)
            rrf_contrib = weight_vec / (self.rrf_k + rank)
            raw_v_score = doc.get("score")

            fused_pool[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "document_name": doc_name,
                "content": doc.get(self.text_field, ""),
                "vector_score": float(raw_v_score) if raw_v_score is not None else None,
                "keyword_score": None,
                "vector_rank": rank,
                "keyword_rank": None,
                "fusion_score": rrf_contrib,
                "metadata": doc.get("metadata") or {},
                "raw_doc": doc,
            }

        # Process keyword candidates (merge / deduplicate)
        for rank, doc in enumerate(raw_kw_candidates, start=1):
            chunk_id, doc_id, doc_name = self._extract_chunk_identity(doc)
            rrf_contrib = weight_kw / (self.rrf_k + rank)
            raw_kw_score = doc.get("text_score")

            if chunk_id in fused_pool:
                fused_pool[chunk_id]["fusion_score"] += rrf_contrib
                fused_pool[chunk_id]["keyword_rank"] = rank
                fused_pool[chunk_id]["keyword_score"] = (
                    float(raw_kw_score) if raw_kw_score is not None else None
                )
            else:
                fused_pool[chunk_id] = {
                    "chunk_id": chunk_id,
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "content": doc.get(self.text_field, ""),
                    "vector_score": None,
                    "keyword_score": (
                        float(raw_kw_score) if raw_kw_score is not None else None
                    ),
                    "vector_rank": None,
                    "keyword_rank": rank,
                    "fusion_score": rrf_contrib,
                    "metadata": doc.get("metadata") or {},
                    "raw_doc": doc,
                }

        # Sort candidate pool descending by fusion_score
        sorted_fused = sorted(
            fused_pool.values(),
            key=lambda x: x["fusion_score"],
            reverse=True,
        )

        # Convert to RetrievedChunk candidate list
        candidate_chunks: list[RetrievedChunk] = []
        for idx, item in enumerate(sorted_fused, start=1):
            candidate_chunks.append(
                RetrievedChunk(
                    chunk_id=item["chunk_id"],
                    document_id=item["document_id"],
                    document_name=item["document_name"],
                    content=item["content"],
                    vector_score=item["vector_score"],
                    keyword_score=item["keyword_score"],
                    fusion_score=round(item["fusion_score"], 6),
                    rank=idx,
                    metadata=item["metadata"],
                )
            )

        fusion_ms = (time.perf_counter() - t_fusion_start) * 1000.0

        # ---------------------------------------------------------
        # 4. Optional Reranking
        # ---------------------------------------------------------
        t_rerank_start = time.perf_counter()
        final_chunks = await self.reranker.rerank(
            query=preprocessed.normalized_query,
            candidates=candidate_chunks,
            top_k=target_top_k,
        )
        rerank_ms = (time.perf_counter() - t_rerank_start) * 1000.0

        total_ms = (time.perf_counter() - start_total) * 1000.0

        latency = RetrievalLatency(
            query_preprocessing_ms=round(prep_ms, 2),
            vector_search_ms=round(vec_ms, 2),
            keyword_search_ms=round(kw_ms, 2),
            fusion_ms=round(fusion_ms, 2),
            rerank_ms=round(rerank_ms, 2),
            total_latency_ms=round(total_ms, 2),
        )

        # ---------------------------------------------------------
        # 5. Debug Inspection Trace (No Chain of Thought)
        # ---------------------------------------------------------
        debug_info = None
        if debug or config.retrieval_debug_mode:
            debug_info = RetrievalDebugInfo(
                original_query=query,
                normalized_query=preprocessed.normalized_query,
                vector_candidates=[
                    {
                        "rank": r,
                        "chunk_id": self._extract_chunk_identity(d)[0],
                        "score": d.get("score"),
                        "content_preview": (d.get(self.text_field) or "")[:80],
                    }
                    for r, d in enumerate(raw_vec_candidates, start=1)
                ],
                keyword_candidates=[
                    {
                        "rank": r,
                        "chunk_id": self._extract_chunk_identity(d)[0],
                        "score": d.get("text_score"),
                        "content_preview": (d.get(self.text_field) or "")[:80],
                    }
                    for r, d in enumerate(raw_kw_candidates, start=1)
                ],
                fusion_candidates=[
                    {
                        "rank": c.rank,
                        "chunk_id": c.chunk_id,
                        "fusion_score": c.fusion_score,
                        "vector_score": c.vector_score,
                        "keyword_score": c.keyword_score,
                    }
                    for c in candidate_chunks
                ],
                final_chunks=[c.to_dict() for c in final_chunks],
            )

        logger.info(
            f"[RETRIEVE] Query: '{preprocessed.normalized_query}' -> "
            f"{len(final_chunks)} chunks (Total: {total_ms:.1f}ms, "
            f"Vec: {vec_ms:.1f}ms, KW: {kw_ms:.1f}ms, RRF: {fusion_ms:.1f}ms, Rerank: {rerank_ms:.1f}ms)"
        )

        return RetrievalResult(
            chunks=final_chunks,
            latency=latency,
            debug=debug_info,
        )
