"""Comprehensive unit tests for advanced retrieval, RRF ranking, deduplication, and reranking."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_rag_agent.retrieval.models import RetrievedChunk
from mcp_rag_agent.retrieval.pipeline import AdvancedRetriever
from mcp_rag_agent.retrieval.preprocessor import QueryPreprocessor
from mcp_rag_agent.retrieval.reranker import (
    CrossEncoderReranker,
    LLMReranker,
    NoOpReranker,
    get_reranker,
)

# ============================================================================
# 1. QUERY PREPROCESSING & NORMALIZATION TESTS
# ============================================================================


class TestQueryPreprocessor:
    """Test suite for QueryPreprocessor."""

    def test_normalize_unicode_nfkc_and_whitespace(self):
        preprocessor = QueryPreprocessor()
        raw = "  Ｈｅｌｌｏ   Ｗｏｒｌｄ  \n\t  "
        normalized = preprocessor.normalize(raw)
        assert normalized == "Hello World"

    def test_normalize_strips_control_characters(self):
        preprocessor = QueryPreprocessor()
        raw = "Query\x00with\x07hidden\x1fcontrols"
        normalized = preprocessor.normalize(raw)
        assert normalized == "Querywithhiddencontrols"

    def test_normalize_translates_smart_quotes(self):
        preprocessor = QueryPreprocessor()
        raw = "“Remote Work” and ‘Sick Leave’"
        normalized = preprocessor.normalize(raw)
        assert normalized == "\"Remote Work\" and 'Sick Leave'"

    def test_build_keyword_query_fixes_unbalanced_quotes(self):
        preprocessor = QueryPreprocessor()
        raw_unbalanced = 'What is "remote work policy'
        kw_query = preprocessor.build_keyword_query(raw_unbalanced)
        assert '"' not in kw_query
        assert "What is remote work policy" == kw_query

    def test_build_keyword_query_handles_leading_hyphen(self):
        preprocessor = QueryPreprocessor()
        # In MongoDB $text search, -term means NOT term
        raw = "-confidential agreement -internal"
        kw_query = preprocessor.build_keyword_query(raw)
        assert kw_query == "confidential agreement internal"

    def test_preprocess_returns_all_variants(self):
        preprocessor = QueryPreprocessor()
        res = preprocessor.preprocess("  “Annual Leave” Guidelines  ")
        assert res.raw_query == "  “Annual Leave” Guidelines  "
        assert res.normalized_query == '"Annual Leave" Guidelines'
        assert res.semantic_query == '"Annual Leave" Guidelines'
        assert res.keyword_query == '"Annual Leave" Guidelines'
        assert "annual" in res.tokens
        assert "leave" in res.tokens


# ============================================================================
# 2. RRF RANKING & DEDUPLICATION TESTS
# ============================================================================


class TestRRFRankingAndDeduplication:
    """Test suite for Reciprocal Rank Fusion, candidate merging, and deduplication."""

    @pytest.mark.asyncio
    async def test_rrf_scoring_and_deduplication_exact_math(self):
        """Verify RRF formula: weight / (rrf_k + rank) and duplicate merging."""
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate = AsyncMock(return_value=[0.1] * 256)

        # Document A is #1 in Vector, #2 in Keyword
        # Document B is #2 in Vector, not in Keyword
        # Document C is #1 in Keyword, not in Vector
        mock_mongo.vector_search.return_value = [
            {
                "_id": "id_A",
                "chunk_id": "chunk_A",
                "document_id": "doc_1",
                "content": "Content A",
                "score": 0.95,
                "metadata": {"filename": "Policy_A.docx"},
            },
            {
                "_id": "id_B",
                "chunk_id": "chunk_B",
                "document_id": "doc_2",
                "content": "Content B",
                "score": 0.85,
                "metadata": {"filename": "Policy_B.docx"},
            },
        ]

        mock_mongo.text_search.return_value = [
            {
                "_id": "id_C",
                "chunk_id": "chunk_C",
                "document_id": "doc_3",
                "content": "Content C",
                "text_score": 12.0,
                "metadata": {"filename": "Policy_C.docx"},
            },
            {
                "_id": "id_A",
                "chunk_id": "chunk_A",
                "document_id": "doc_1",
                "content": "Content A",
                "text_score": 8.0,
                "metadata": {"filename": "Policy_A.docx"},
            },
        ]

        # rrf_k = 60, semantic_weight = 0.7, keyword_weight = 0.3
        retriever = AdvancedRetriever(
            mongo_client=mock_mongo,
            embedding_generator=mock_emb,
            rrf_k=60,
        )

        result = await retriever.retrieve("test query", top_k=3, semantic_weight=0.7)
        chunks = result.chunks

        # Deduplication check: 3 unique chunks (A, B, C), chunk_A must not be duplicated
        chunk_ids = [c.chunk_id for c in chunks]
        assert len(chunk_ids) == 3
        assert len(set(chunk_ids)) == 3
        assert "chunk_A" in chunk_ids
        assert "chunk_B" in chunk_ids
        assert "chunk_C" in chunk_ids

        # Math verification:
        # Score A = 0.7 / (60 + 1) + 0.3 / (60 + 2) = 0.7/61 + 0.3/62 = 0.0114754 + 0.0048387 = 0.016314
        # Score B = 0.7 / (60 + 2) = 0.7/62 = 0.011290
        # Score C = 0.3 / (60 + 1) = 0.3/61 = 0.004918
        # Therefore, Rank 1: A, Rank 2: B, Rank 3: C
        assert chunks[0].chunk_id == "chunk_A"
        assert chunks[0].rank == 1
        assert chunks[0].vector_score == 0.95
        assert chunks[0].keyword_score == 8.0
        assert chunks[0].document_name == "Policy_A.docx"
        assert chunks[0].fusion_score == pytest.approx(0.016314, abs=1e-5)

        assert chunks[1].chunk_id == "chunk_B"
        assert chunks[1].rank == 2
        assert chunks[1].vector_score == 0.85
        assert chunks[1].keyword_score is None

        assert chunks[2].chunk_id == "chunk_C"
        assert chunks[2].rank == 3
        assert chunks[2].vector_score is None
        assert chunks[2].keyword_score == 12.0

    @pytest.mark.asyncio
    async def test_pure_keyword_weight_ranks_keyword_first(self):
        """Verify semantic_weight=0.0 turns retrieval into pure keyword ranking."""
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate = AsyncMock(return_value=[0.1] * 256)

        mock_mongo.vector_search.return_value = [
            {"_id": "v1", "chunk_id": "v1", "content": "Vector Match", "score": 0.99}
        ]
        mock_mongo.text_search.return_value = [
            {
                "_id": "k1",
                "chunk_id": "k1",
                "content": "Keyword Match",
                "text_score": 10.0,
            }
        ]

        retriever = AdvancedRetriever(
            mongo_client=mock_mongo, embedding_generator=mock_emb, rrf_k=60
        )
        result = await retriever.retrieve("test", top_k=2, semantic_weight=0.0)

        # With semantic_weight=0.0, vector search contribution is 0
        assert result.chunks[0].chunk_id == "k1"
        assert result.chunks[0].fusion_score > result.chunks[1].fusion_score


# ============================================================================
# 3. CANDIDATE OVER-FETCHING & METADATA FILTERING TESTS
# ============================================================================


class TestOverfetchingAndFiltering:
    """Test suite for candidate oversampling and metadata filters."""

    @pytest.mark.asyncio
    async def test_candidate_overfetching_multiplier(self):
        """Verify retriever requests top_k * oversample_factor candidates."""
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate = AsyncMock(return_value=[0.1] * 256)
        mock_mongo.vector_search.return_value = []
        mock_mongo.text_search.return_value = []

        retriever = AdvancedRetriever(
            mongo_client=mock_mongo,
            embedding_generator=mock_emb,
            oversample_factor=4,
        )

        await retriever.retrieve("query", top_k=5)

        # top_k=5, factor=4 -> limit=20
        mock_mongo.vector_search.assert_called_once()
        _, vec_kwargs = mock_mongo.vector_search.call_args
        assert vec_kwargs["limit"] == 20

        mock_mongo.text_search.assert_called_once()
        _, kw_kwargs = mock_mongo.text_search.call_args
        assert kw_kwargs["limit"] == 20

    @pytest.mark.asyncio
    async def test_metadata_filtering_passed_to_searches(self):
        """Verify filter_query is forwarded to both vector and text searches."""
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate = AsyncMock(return_value=[0.1] * 256)
        mock_mongo.vector_search.return_value = []
        mock_mongo.text_search.return_value = []

        retriever = AdvancedRetriever(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )
        filter_dict = {"metadata.file_type": "docx", "metadata.department": "HR"}

        await retriever.retrieve("leave", top_k=3, filter_query=filter_dict)

        _, vec_kwargs = mock_mongo.vector_search.call_args
        assert vec_kwargs["filter_query"] == filter_dict

        _, kw_kwargs = mock_mongo.text_search.call_args
        assert kw_kwargs["filter_query"] == filter_dict


# ============================================================================
# 4. RERANKER ABSTRACTION TESTS
# ============================================================================


class TestRerankerAbstraction:
    """Test suite for NoOp, Cross-Encoder, and LLM rerankers."""

    def test_factory_returns_expected_instances(self):
        assert isinstance(get_reranker("none"), NoOpReranker)
        assert isinstance(get_reranker("noop"), NoOpReranker)
        assert isinstance(get_reranker("cross_encoder"), CrossEncoderReranker)
        assert isinstance(get_reranker("llm"), LLMReranker)
        assert isinstance(get_reranker("unknown_type"), NoOpReranker)

    @pytest.mark.asyncio
    async def test_cross_encoder_reranks_and_updates_scores(self):
        """Verify cross encoder alters chunk ordering based on scoring."""
        chunk1 = RetrievedChunk(
            chunk_id="c1",
            document_id="d1",
            document_name="doc1",
            content="General company info",
            fusion_score=0.05,
            rank=1,
            metadata={},
        )
        chunk2 = RetrievedChunk(
            chunk_id="c2",
            document_id="d2",
            document_name="doc2",
            content="Explicit remote work policy rules",
            fusion_score=0.03,
            rank=2,
            metadata={},
        )

        # Custom score function scoring c2 higher than c1
        custom_scorer = lambda q, texts: [0.10, 0.95]
        reranker = CrossEncoderReranker(score_fn=custom_scorer)

        reranked = await reranker.rerank("remote work", [chunk1, chunk2], top_k=2)

        assert len(reranked) == 2
        # c2 should now be rank 1 due to higher cross-encoder score
        assert reranked[0].chunk_id == "c2"
        assert reranked[0].rank == 1
        assert reranked[0].rerank_score == 0.95

        assert reranked[1].chunk_id == "c1"
        assert reranked[1].rank == 2
        assert reranked[1].rerank_score == 0.10


# ============================================================================
# 5. DEBUG MODE & OBSERVABILITY TESTS
# ============================================================================


class TestRetrievalDebugAndObservability:
    """Test suite for debug inspection mode and latency tracking."""

    @pytest.mark.asyncio
    async def test_debug_mode_exposes_trace_without_chain_of_thought(self):
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate = AsyncMock(return_value=[0.1] * 256)

        mock_mongo.vector_search.return_value = [
            {
                "_id": "v1",
                "chunk_id": "c1",
                "content": "Vector Candidate",
                "score": 0.90,
            }
        ]
        mock_mongo.text_search.return_value = [
            {
                "_id": "k1",
                "chunk_id": "c2",
                "content": "Keyword Candidate",
                "text_score": 14.5,
            }
        ]

        retriever = AdvancedRetriever(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )
        result = await retriever.retrieve("remote policy", top_k=2, debug=True)

        assert result.debug is not None
        debug = result.debug
        assert debug.original_query == "remote policy"
        assert debug.normalized_query == "remote policy"
        assert len(debug.vector_candidates) == 1
        assert len(debug.keyword_candidates) == 1
        assert len(debug.fusion_candidates) == 2
        assert len(debug.final_chunks) == 2

        # Verify NO chain-of-thought field is present
        debug_dict = debug.model_dump()
        assert "chain_of_thought" not in debug_dict
        assert "reasoning" not in debug_dict
        assert "thought" not in debug_dict

    @pytest.mark.asyncio
    async def test_latency_metrics_tracked(self):
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate = AsyncMock(return_value=[0.1] * 256)
        mock_mongo.vector_search.return_value = []
        mock_mongo.text_search.return_value = []

        retriever = AdvancedRetriever(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )
        result = await retriever.retrieve("test query")

        lat = result.latency
        assert lat.total_latency_ms >= 0.0
        assert lat.query_preprocessing_ms >= 0.0
        assert lat.vector_search_ms >= 0.0
        assert lat.keyword_search_ms >= 0.0
        assert lat.fusion_ms >= 0.0
        assert lat.rerank_ms >= 0.0


# ============================================================================
# 6. RETRIEVED CHUNK SCHEMA COMPLIANCE TEST
# ============================================================================


class TestRetrievedChunkSchemaCompliance:
    """Verify all 9 mandatory fields are exposed on every chunk."""

    @pytest.mark.asyncio
    async def test_all_nine_fields_present_in_chunk_to_dict(self):
        mock_mongo = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate = AsyncMock(return_value=[0.1] * 256)

        mock_mongo.vector_search.return_value = [
            {
                "_id": "id_10",
                "chunk_id": "doc_10_c0",
                "document_id": "doc_10",
                "content": "Sample policy content",
                "score": 0.88,
                "metadata": {
                    "filename": "leave.pdf",
                    "file_type": "pdf",
                    "section": "Sick Leave",
                    "page_number": 2,
                },
            }
        ]
        mock_mongo.text_search.return_value = []

        retriever = AdvancedRetriever(
            mongo_client=mock_mongo, embedding_generator=mock_emb
        )
        result = await retriever.retrieve("leave", top_k=1)

        assert len(result.chunks) == 1
        chunk_dict = result.chunks[0].to_dict()

        # All 9 required fields
        required_fields = [
            "chunk_id",
            "document_id",
            "document_name",
            "content",
            "vector_score",
            "keyword_score",
            "fusion_score",
            "rank",
            "metadata",
        ]

        for field in required_fields:
            assert field in chunk_dict, f"Missing required field: {field}"

        assert chunk_dict["chunk_id"] == "doc_10_c0"
        assert chunk_dict["document_id"] == "doc_10"
        assert chunk_dict["document_name"] == "leave.pdf"
        assert chunk_dict["rank"] == 1
        assert chunk_dict["metadata"]["section"] == "Sick Leave"
        assert chunk_dict["metadata"]["page_number"] == 2
