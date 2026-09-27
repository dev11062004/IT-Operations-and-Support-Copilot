"""Unit tests for agent creation factories and execution modes."""

import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mcp_rag_agent.agent
from mcp_rag_agent.agent.create_agent import (
    create_rag_agent_instance,
    create_search_documents_tool,
)
from mcp_rag_agent.core.config import Config, ConfigurationError


class TestAgentCreation:
    """Test suite for agent creation in Direct and MCP modes."""

    def test_search_documents_tool_metadata(self):
        """Verify the structured tool has the expected name and schema."""
        tool = create_search_documents_tool()
        assert tool.name == "search_policy_documents"
        assert "stored policy documents" in tool.description
        assert "query" in tool.args_schema.model_fields
        assert "top_k" in tool.args_schema.model_fields

    @pytest.mark.asyncio
    async def test_create_rag_agent_instance_raises_without_credentials(self):
        """Verify factory raises ConfigurationError when credentials are missing."""
        invalid_cfg = Config(db_url="", db_name="", model_api_key="")
        with pytest.raises(ConfigurationError):
            await create_rag_agent_instance(cfg=invalid_cfg)

    @pytest.mark.asyncio
    async def test_create_rag_agent_instance_direct_mode(self):
        """Verify factory in direct mode creates an agent with StructuredTool."""
        valid_cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            model_api_key="sk-test",
            ff_mcp_server=False,
        )

        with patch(
            "mcp_rag_agent.agent.utils.rag_agent_creator.create_agent"
        ) as mock_create_agent, patch(
            "mcp_rag_agent.agent.utils.rag_agent_creator.ChatOpenAI"
        ):
            mock_create_agent.return_value = MagicMock()
            agent = await create_rag_agent_instance(cfg=valid_cfg)
            assert agent is not None
            mock_create_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rag_agent_instance_mcp_mode(self):
        """Verify factory in MCP mode delegates to create_mcp_rag_agent."""
        mcp_cfg = Config(
            db_url="mongodb://localhost:27017",
            db_name="test_db",
            model_api_key="sk-test",
            ff_mcp_server=True,
        )

        with patch(
            "mcp_rag_agent.agent.create_agent.create_mcp_rag_agent",
            new_callable=AsyncMock,
        ) as mock_mcp:
            mock_mcp.return_value = MagicMock()
            agent = await create_rag_agent_instance(cfg=mcp_cfg)
            assert agent is not None
            mock_mcp.assert_awaited_once()

    def test_legacy_agent_attribute_issues_deprecation_warning(self):
        """Verify accessing mcp_rag_agent.agent.agent issues a DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="deprecated"):
            with patch(
                "mcp_rag_agent.agent.create_agent.create_rag_agent_instance",
                new_callable=AsyncMock,
            ) as mock_factory:
                mock_factory.return_value = MagicMock()
                # Access the attribute via getattr
                _ = mcp_rag_agent.agent.agent
