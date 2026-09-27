"""Factory entry point for creating production RAG agents in Direct or MCP modes."""

import asyncio
import logging
from typing import Any, Optional

from langchain_core.tools import StructuredTool

from mcp_rag_agent.agent.models import SearchDocumentsInput, SearchDocumentsOutput
from mcp_rag_agent.agent.prompts import system_prompt
from mcp_rag_agent.agent.runner import RAGAgentRunner
from mcp_rag_agent.agent.utils.mcp_rag_agent_creator import create_mcp_rag_agent
from mcp_rag_agent.agent.utils.rag_agent_creator import create_rag_agent
from mcp_rag_agent.core.checkpointer import get_checkpointer_async
from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.core.log_setup import setup_logging
from mcp_rag_agent.mcp_server.tools import search_policy_documents_typed

setup_logging()
logger = logging.getLogger("Agent Creator")


def create_search_documents_tool() -> StructuredTool:
    """Create LangChain StructuredTool for searching policy documents with strong typed schemas."""
    logger.debug("Creating LangChain structured search_policy_documents tool...")

    async def _async_search(
        query: str, top_k: int = 3, filter_query: Optional[dict[str, Any]] = None
    ) -> str:
        """Asynchronous execution handler returning formatted context string."""
        input_data = SearchDocumentsInput(
            query=query, top_k=top_k, filter_query=filter_query
        )
        output: SearchDocumentsOutput = await search_policy_documents_typed(input_data)
        return output.to_tool_string()

    def _sync_search_stub(
        query: str, top_k: int = 3, filter_query: Optional[dict[str, Any]] = None
    ) -> str:
        """Synchronous runner that safely delegates to async coroutine without event loop crash."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run, _async_search(query, top_k, filter_query)
                )
                return future.result()
        return asyncio.run(_async_search(query, top_k, filter_query))

    return StructuredTool(
        name="search_policy_documents",
        description=(
            "This tool understands the meaning of the query, "
            "searches through stored policy documents using hybrid search, "
            "and returns relevant passages and document titles "
            "so they can be used to ground the final answer."
        ),
        func=_sync_search_stub,
        coroutine=_async_search,
        args_schema=SearchDocumentsInput,
    )


async def create_rag_agent_instance(
    cfg: Optional[Config] = None,
    prompt: Optional[str] = None,
    checkpointer: Optional[Any] = None,
) -> RAGAgentRunner:
    """Explicit async factory to create a production RAG agent with structured runner.

    Supports both Direct (StructuredTool) and MCP (stdio subprocess) modes
    based on config.ff_mcp_server with guaranteed behavioral parity and
    persistent conversation memory when enabled.

    Args:
        cfg: Optional application configuration override.
        prompt: Optional system prompt override.
        checkpointer: Optional explicit checkpointer instance.

    Returns:
        RAGAgentRunner wrapping the compiled agent.
    """
    from mcp_rag_agent.observability import configure_langsmith_environment

    active_config = cfg or config
    active_prompt = prompt or system_prompt

    active_config.validate_all()
    configure_langsmith_environment(active_config)

    # Determine checkpointer: use explicit checkpointer if passed, otherwise fetch via factory
    if checkpointer is not None:
        active_checkpointer = checkpointer
    else:
        active_checkpointer = await get_checkpointer_async(active_config)

    runbook_executor = None
    if active_config.ff_it_support:
        from mcp_rag_agent.it_support.runbooks import RunbookExecutor, create_runbook_tool
        runbook_executor = RunbookExecutor(checkpointer=active_checkpointer)

    if active_config.ff_mcp_server:
        logger.info("Initializing RAG Agent in MCP Server mode...")
        agent_graph = await create_mcp_rag_agent(
            system_prompt=active_prompt,
            config=active_config,
            checkpointer=active_checkpointer,
        )
    else:
        logger.info("Initializing RAG Agent in Direct mode...")
        tools = [create_search_documents_tool()]
        if active_config.ff_it_support:
            from mcp_rag_agent.it_support.tools import create_it_operations_tools
            tools.extend(create_it_operations_tools())
        if runbook_executor is not None:
            tools.append(create_runbook_tool(runbook_executor))

        agent_graph = await create_rag_agent(
            system_prompt=active_prompt,
            tools=tools,
            config=active_config,
            checkpointer=active_checkpointer,
        )

    return RAGAgentRunner(
        agent_graph=agent_graph,
        system_prompt=active_prompt,
        checkpointer=active_checkpointer,
        runbook_executor=runbook_executor,
    )



# -------------------------------------------------------------------
# Simple CLI test
# -------------------------------------------------------------------

if __name__ == "__main__":

    async def demo():
        runner = await create_rag_agent_instance()
        query = "In the UK, how many days of annual leave do employees receive?"
        print("=" * 60)
        print(f"Query: {query}")
        print("=" * 60)
        response = await runner.run(query)
        print("\nAnswer:\n", response.answer)
        print("\nExecution Metadata:")
        print(response.metadata.model_dump_json(indent=2))

    asyncio.run(demo())
