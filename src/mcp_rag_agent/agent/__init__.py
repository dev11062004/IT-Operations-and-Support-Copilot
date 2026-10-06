"""Agent module for production MCP RAG Agent."""

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
    """Lazy import for create_agent symbols to break circular import cycle.

    mcp_server.tools imports agent.models (fine), but agent.__init__ must not
    eagerly import create_agent (which imports mcp_server.tools) at package
    load time — that would form a circular dependency.
    """
    if name in ("create_rag_agent_instance", "create_mcp_rag_agent", "create_search_documents_tool"):
        from mcp_rag_agent.agent import create_agent as _ca
        return getattr(_ca, name)

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

