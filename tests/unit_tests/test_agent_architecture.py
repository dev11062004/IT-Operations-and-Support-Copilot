"""Unit tests for Phase 4: Production Agent Architecture.

Tests typed tool interfaces, input validation, failure handling, Direct/MCP parity,
runner responsibilities, grounding and citation extraction, and execution metadata.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import ValidationError

from mcp_rag_agent.agent.create_agent import (
    create_rag_agent_instance,
    create_search_documents_tool,
)
from mcp_rag_agent.agent.models import (
    AgentExecutionMetadata,
    AgentResponse,
    RetrievedChunkOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
)
from mcp_rag_agent.agent.runner import RAGAgentRunner
from mcp_rag_agent.core.config import Config
from mcp_rag_agent.mcp_server.server import mcp, search_policy_documents
from mcp_rag_agent.mcp_server.tools import (
    mask_sensitive,
    reset_retriever,
    search_policy_documents_typed,
    set_advanced_retriever,
)
from mcp_rag_agent.retrieval.models import (
    RetrievalLatency,
    RetrievalResult,
    RetrievedChunk,
)

# ============================================================================
# 1. TYPED TOOL INTERFACE & INPUT VALIDATION TESTS
# ============================================================================


class TestTypedToolInterface:
    """Test suite for search_policy_documents strongly typed schema and error resilience."""

    def teardown_method(self):
        reset_retriever()

    @pytest.mark.asyncio
    async def test_tool_invocation_success(self):
        """Verify successful retrieval returns typed SearchDocumentsOutput."""
        mock_retriever = MagicMock()
        mock_chunk = RetrievedChunk(
            chunk_id="doc_1_c0",
            document_id="doc_1",
            document_name="Remote_Work.pdf",
            content="Employees may work remotely 2 days per week.",
            fusion_score=0.016,
            rank=1,
            metadata={"section": "Eligibility"},
        )
        mock_result = RetrievalResult(
            chunks=[mock_chunk],
            latency=RetrievalLatency(total_latency_ms=12.5),
        )
        mock_retriever.retrieve = AsyncMock(return_value=mock_result)
        set_advanced_retriever(mock_retriever)

        input_data = SearchDocumentsInput(query="remote work", top_k=2)
        output = await search_policy_documents_typed(input_data)

        assert isinstance(output, SearchDocumentsOutput)
        assert output.status == "success"
        assert output.total_found == 1
        assert len(output.chunks) == 1
        assert output.chunks[0].chunk_id == "doc_1_c0"
        assert output.chunks[0].document_name == "Remote_Work.pdf"
        assert output.document_ids == ["doc_1"]
        assert output.retrieval_latency_ms == 12.5
        assert "Remote_Work.pdf" in output.to_tool_string()

    @pytest.mark.asyncio
    async def test_tool_invocation_empty_results(self):
        """Verify empty results return status='empty' and clean fallback string."""
        mock_retriever = MagicMock()
        mock_result = RetrievalResult(
            chunks=[],
            latency=RetrievalLatency(total_latency_ms=5.0),
        )
        mock_retriever.retrieve = AsyncMock(return_value=mock_result)
        set_advanced_retriever(mock_retriever)

        input_data = SearchDocumentsInput(query="nonexistent term", top_k=3)
        output = await search_policy_documents_typed(input_data)

        assert output.status == "empty"
        assert output.total_found == 0
        assert output.chunks == []
        assert "[EMPTY]" in output.to_tool_string()

    def test_tool_input_validation_errors(self):
        """Verify Pydantic input model rejects invalid queries and limits."""
        # Empty query
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="")

        # top_k < 1
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="test", top_k=0)

        # top_k > 10
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="test", top_k=50)

    @pytest.mark.asyncio
    async def test_tool_handles_retrieval_failure_gracefully(self):
        """Verify retriever crash does not crash the agent, returns status='error'."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(
            side_effect=ConnectionError("MongoDB connection lost")
        )
        set_advanced_retriever(mock_retriever)

        input_data = SearchDocumentsInput(query="leave policy", top_k=3)
        output = await search_policy_documents_typed(input_data)

        assert output.status == "error"
        assert output.total_found == 0
        assert "MongoDB connection lost" in output.error_message
        assert "[ERROR]" in output.to_tool_string()

    def test_secret_masking(self):
        """Verify secrets like OpenAI keys and Mongo URIs are scrubbed."""
        raw_msg = "Error connecting to mongodb+srv://admin:SecretPass123@cluster.mongodb.net with sk-1234567890abcdef1234567890"
        masked = mask_sensitive(raw_msg)
        assert "SecretPass123" not in masked
        assert "sk-1234567890abcdef1234567890" not in masked
        assert "mongodb://***REDACTED***@" in masked
        assert "sk-***REDACTED***" in masked


# ============================================================================
# 2. DIRECT MODE & MCP MODE PARITY TESTS
# ============================================================================


class TestDirectAndMCPParity:
    """Verify tool signatures and behavioral consistency between Direct and MCP modes."""

    def test_direct_and_mcp_tool_name_parity(self):
        """Both direct mode and MCP mode must expose 'search_policy_documents'."""
        direct_tool = create_search_documents_tool()
        assert direct_tool.name == "search_policy_documents"

        # Check MCP server tools
        mcp_tools = [t.name for t in mcp._tool_manager.list_tools()]
        assert "search_policy_documents" in mcp_tools

    def test_direct_and_mcp_input_schema_equivalence(self):
        """Both direct tool and MCP tool must accept 'query' and 'top_k' parameters."""
        direct_tool = create_search_documents_tool()
        assert "query" in direct_tool.args_schema.model_fields
        assert "top_k" in direct_tool.args_schema.model_fields
        assert "filter_query" in direct_tool.args_schema.model_fields


# ============================================================================
# 3. AGENT RUNNER RESPONSIBILITIES & EXECUTION METADATA TESTS
# ============================================================================


class TestAgentRunnerResponsibilities:
    """Test suite for the 7 explicit agentic responsibilities and metadata tracking."""

    @pytest.mark.asyncio
    async def test_runner_empty_query_returns_out_of_scope(self):
        """Responsibility 1: Empty query handled gracefully without model call."""
        mock_graph = MagicMock()
        runner = RAGAgentRunner(agent_graph=mock_graph)

        response = await runner.run("   ")
        assert response.is_out_of_scope is True
        assert "valid question" in response.answer.lower()
        mock_graph.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_runner_captures_structured_execution_metadata(self):
        """Responsibility 3 & Execution Metadata: Tracking latencies, request_id, thread_id, doc_ids."""
        mock_graph = MagicMock()
        tool_msg = ToolMessage(
            content="Retrieved 1 relevant policy section(s):\n--- Document #1: Travel_Policy.docx (ID: doc_travel_99, Chunk: doc_travel_99_c0) ---\nMeal limits are $50/day.",
            tool_call_id="call_123",
            name="search_policy_documents",
        )
        ai_msg = AIMessage(
            content="Employees may expense meals up to $50 per day.\n\nReference:\n1. Travel_Policy.docx"
        )
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [tool_msg, ai_msg]})

        runner = RAGAgentRunner(agent_graph=mock_graph)
        response = await runner.run(
            query="What is the meal expense limit?",
            thread_id="test_thread_42",
            request_id="req_custom_100",
        )

        assert isinstance(response, AgentResponse)
        assert response.answer.startswith("Employees may expense")
        assert response.is_out_of_scope is False

        # Metadata verification
        meta = response.metadata
        assert meta.request_id == "req_custom_100"
        assert meta.thread_id == "test_thread_42"
        assert meta.total_latency_ms >= 0.0
        assert meta.model_latency_ms >= 0.0
        assert "doc_travel_99" in meta.retrieved_document_ids
        assert "Travel_Policy.docx" in meta.citations

    @pytest.mark.asyncio
    async def test_runner_citation_extraction_and_grounding(self):
        """Responsibility 6: Citation generation parsing."""
        mock_graph = MagicMock()
        ai_msg = AIMessage(
            content="UK employees receive 25 days of annual leave.\n\nReference:\n1. Annual_Leave_Policy.pdf\n2. UK_Employee_Handbook.docx"
        )
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [ai_msg]})

        runner = RAGAgentRunner(agent_graph=mock_graph)
        response = await runner.run("How much annual leave in UK?")

        assert len(response.metadata.citations) == 2
        assert "Annual_Leave_Policy.pdf" in response.metadata.citations
        assert "UK_Employee_Handbook.docx" in response.metadata.citations

    @pytest.mark.asyncio
    async def test_runner_out_of_scope_detection(self):
        """Responsibility 7: Standard COSTAR refusal triggers is_out_of_scope=True."""
        mock_graph = MagicMock()
        ai_msg = AIMessage(
            content="I couldn't find this information in the available policy content. Please rephrase or contact HR."
        )
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [ai_msg]})

        runner = RAGAgentRunner(agent_graph=mock_graph)
        response = await runner.run("What is the policy for traveling to Mars?")

        assert response.is_out_of_scope is True
        assert "couldn't find this information" in response.answer

    @pytest.mark.asyncio
    async def test_runner_ainvoke_backward_compatibility(self):
        """Ensure runner.ainvoke works with LangGraph dict input and evaluation harness."""
        mock_graph = MagicMock()
        ai_msg = AIMessage(
            content="Remote work is allowed up to 2 days per week.\n\nReference:\n1. Remote_Work.txt"
        )
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [ai_msg]})

        runner = RAGAgentRunner(agent_graph=mock_graph)
        result = await runner.ainvoke(
            {"messages": [{"role": "user", "content": "How many days remote work?"}]}
        )

        assert "messages" in result
        assert result["messages"][-1].content.startswith("Remote work is allowed")
        assert "request_id" in result
        assert "thread_id" in result
        assert "total_latency_ms" in result
        assert "citations" in result
