"""Agent module for production MCP RAG Agent."""

from mcp_rag_agent.agent.create_agent import (
    create_mcp_rag_agent,
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

__all__ = [
    "create_rag_agent_instance",
    "create_mcp_rag_agent",
    "create_search_documents_tool",
    "RAGAgentRunner",
    "AgentResponse",
    "AgentExecutionMetadata",
    "SearchDocumentsInput",
    "SearchDocumentsOutput",
    "RetrievedChunkOutput",
]


def __getattr__(name: str):
    """Provide lazy backwards compatibility for legacy 'agent' attribute."""
    if name == "agent":
        import asyncio
        import warnings

        warnings.warn(
            "Accessing 'agent' directly from mcp_rag_agent.agent is deprecated. "
            "Use 'await create_rag_agent_instance()' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from mcp_rag_agent.agent.create_agent import create_rag_agent_instance

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(
                    asyncio.run, create_rag_agent_instance()
                ).result()
        return asyncio.run(create_rag_agent_instance())
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
