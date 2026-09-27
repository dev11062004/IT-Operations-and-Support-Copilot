"""Unit tests for MCP server tools and lazy retriever initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_rag_agent.core.config import Config, ConfigurationError
from mcp_rag_agent.mcp_server.tools import (
    get_hybrid_search,
    reset_retriever,
    search_documents,
    set_hybrid_search,
)


class TestToolsAndRetriever:
    """Test suite for tools.py lazy initialization and execution."""

    def teardown_method(self):
        """Clean up retriever singleton after each test."""
        reset_retriever()

    def test_get_hybrid_search_raises_on_unconfigured_credentials(self):
        """Verify get_hybrid_search raises ConfigurationError if required config is missing."""
        invalid_config = Config(db_url="", db_name="", model_api_key="")
        with pytest.raises(ConfigurationError):
            get_hybrid_search(invalid_config)

    def test_set_hybrid_search_mock(self):
        """Verify set_hybrid_search allows injecting a mock searcher."""
        mock_searcher = MagicMock()
        set_hybrid_search(mock_searcher)
        assert get_hybrid_search() is mock_searcher

    @pytest.mark.asyncio
    async def test_search_documents_invokes_searcher(self):
        """Verify search_documents invokes the underlying hybrid search engine."""
        mock_searcher = MagicMock()
        mock_results = [{"content": "Policy document", "rrf_score": 0.05}]
        mock_searcher.search = AsyncMock(return_value=mock_results)
        set_hybrid_search(mock_searcher)

        results = await search_documents("annual leave", top_k=2)
        assert results == mock_results
        mock_searcher.search.assert_awaited_once()
