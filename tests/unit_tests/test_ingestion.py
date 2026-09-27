"""Unit tests for document ingestion and cross-platform path resolution."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_rag_agent.core.config import config
from mcp_rag_agent.embeddings.index_documents import index_documents_from_folder, main


class TestDocumentIngestion:
    """Test suite for document ingestion."""

    @pytest.mark.asyncio
    async def test_non_existent_folder_returns_gracefully(self):
        """Verify non-existent folder does not crash and returns early."""
        mock_mongo = MagicMock()
        mock_search = MagicMock()

        # Should log error and return without exception
        await index_documents_from_folder(
            folder_path="non/existent/path/here",
            mongo_client=mock_mongo,
            semantic_search=mock_search,
            documents_collection="documents",
            vectors_collection="vectors",
        )
        mock_mongo.insert_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_indexing_processes_text_files(self, tmp_path):
        """Verify indexing reads text files and stores in both documents and vectors collections."""
        # Create dummy policy document in temporary directory
        doc_path = tmp_path / "test_policy.txt"
        doc_path.write_text("This is a sample test policy content.", encoding="utf-8")

        mock_mongo = MagicMock()
        mock_mongo.insert_document.return_value = "doc_123"
        mock_search = MagicMock()
        mock_search.index_document = AsyncMock(return_value="vec_123")

        await index_documents_from_folder(
            folder_path=tmp_path,
            mongo_client=mock_mongo,
            semantic_search=mock_search,
            documents_collection="documents",
            vectors_collection="vectors",
        )

        mock_mongo.insert_document.assert_called_once()
        mock_search.index_document.assert_awaited_once()

    def test_default_ingested_directory_resolved_as_path(self):
        """Verify ingested doc directory resolves to valid Path object."""
        resolved = Path(config.ingested_doc_dir).resolve()
        assert isinstance(resolved, Path)
        assert resolved.name == "ingested_documents"
