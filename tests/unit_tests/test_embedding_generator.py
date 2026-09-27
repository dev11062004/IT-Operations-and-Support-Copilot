"""Unit tests for EmbeddingGenerator consistency and validation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_rag_agent.core.config import ConfigurationError, config
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator


class TestEmbeddingGenerator:
    """Test suite for EmbeddingGenerator."""

    def test_dimensions_defaults_to_config_dimension(self):
        """Verify dimensions defaults to config.embedding_dimension (256) when not specified."""
        generator = EmbeddingGenerator(api_key="sk-test")
        assert generator.dimensions == config.embedding_dimension
        assert generator.dimensions == 256

    def test_explicit_dimensions_overrides_default(self):
        """Verify passing explicit dimensions overrides the config default."""
        generator = EmbeddingGenerator(api_key="sk-test", dimensions=1536)
        assert generator.dimensions == 1536

    @pytest.mark.asyncio
    async def test_generate_raises_when_api_key_missing(self):
        """Verify generate raises ConfigurationError when API key is missing."""
        generator = EmbeddingGenerator(api_key="")
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            await generator.generate("test text")

    @pytest.mark.asyncio
    async def test_generate_batch_empty_list(self):
        """Verify generate_batch returns empty list for empty inputs without calling API."""
        generator = EmbeddingGenerator(api_key="sk-test")
        result = await generator.generate_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_calls_openai_with_correct_parameters(self):
        """Verify generate calls OpenAI embeddings.create with correct model and dimensions."""
        generator = EmbeddingGenerator(
            api_key="sk-test", model="text-embedding-3-small", dimensions=256
        )

        mock_response = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1] * 256
        mock_response.data = [mock_item]

        generator._client = MagicMock()
        generator._client.embeddings.create = AsyncMock(return_value=mock_response)

        embedding = await generator.generate("hello world")

        generator._client.embeddings.create.assert_awaited_once_with(
            model="text-embedding-3-small", input="hello world", dimensions=256
        )
        assert len(embedding) == 256
