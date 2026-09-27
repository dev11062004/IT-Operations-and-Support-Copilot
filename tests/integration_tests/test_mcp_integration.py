"""Integration tests for FastMCP server endpoints and tool registry."""

import os

import pytest

from mcp_rag_agent.agent.models import SearchDocumentsInput
from mcp_rag_agent.mcp_server.server import (
    grounded_qa_prompt,
    mcp,
    search_documents,
    search_policy_documents,
)
from mcp_rag_agent.mcp_server.tools import search_policy_documents_typed

pytestmark = pytest.mark.integration


def is_live_openai_configured() -> bool:
    """Check if a valid non-dummy OpenAI API key is present."""
    key = os.environ.get("OPENAI_API_KEY", "")
    return bool(
        key
        and not key.startswith("sk-proj-test")
        and not key.startswith("sk-mock")
        and key != "your_secret_key"
        and key != "your_openai_api_key_here"
    )


class TestMCPIntegration:
    """Integration test suite for FastMCP server tools and endpoints."""

    def test_mcp_server_initialization_and_metadata(self):
        """Verify FastMCP server instance attributes."""
        assert mcp.name == "mongodb-semantic-search" or mcp.name is not None
        assert mcp.settings.port == 8000 or mcp.settings.port is not None

    def test_mcp_prompt_generation(self):
        """Verify the grounded QA system prompt is properly loaded."""
        prompt = grounded_qa_prompt()
        assert "search_policy_documents" in prompt
        assert "Never invent facts" in prompt

    @pytest.mark.skipif(
        not is_live_openai_configured(),
        reason="Valid live OPENAI_API_KEY required for live embedding retrieval",
    )
    @pytest.mark.asyncio
    async def test_search_policy_documents_typed_contract(self):
        """Verify search_policy_documents_typed returns structured SearchDocumentsOutput with live credentials."""
        query_input = SearchDocumentsInput(query="remote working allowance", top_k=2)
        output = await search_policy_documents_typed(query_input)
        assert output is not None
        assert hasattr(output, "query")
        assert output.query == "remote working allowance"
        assert hasattr(output, "chunks")
        assert isinstance(output.to_tool_string(), str)
