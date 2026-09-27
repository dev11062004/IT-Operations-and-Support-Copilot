import logging
import os
from typing import Any, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.prompts import load_mcp_prompt
from langchain_openai import ChatOpenAI

from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.core.log_setup import setup_logging

setup_logging()
logger = logging.getLogger("Agent Creator")


def get_mcp_connections(cfg: Config) -> dict:
    """Build MCP connection configuration dictionary supporting stdio or network SSE transports."""
    mcp_transport = getattr(
        cfg, "mcp_transport", os.environ.get("MCP_TRANSPORT", "stdio")
    ).lower()
    if mcp_transport == "sse":
        url = getattr(cfg, "mcp_url", None) or os.environ.get(
            "MCP_SERVER_URL", f"http://{cfg.mcp_host}:{cfg.mcp_port}/sse"
        )
        return {
            cfg.mcp_name: {
                "url": url,
                "transport": "sse",
            }
        }
    return {
        cfg.mcp_name: {
            "command": "python",
            "args": ["-m", "mcp_rag_agent.mcp_server.server"],
            "transport": "stdio",
        }
    }


async def _load_mcp_tools_and_prompt(
    cfg: Optional[Config] = None,
) -> tuple[List[BaseTool], str]:
    """
    - Connects to your MCP server via MultiServerMCPClient
    - Loads all MCP tools as LangChain tools (including `search_documents`)
    - Loads the `grounded_qa_prompt` MCP prompt and turns it into a system prompt
    """
    active_config = cfg or config
    server_name = active_config.mcp_name
    connections = get_mcp_connections(active_config)

    logger.info(f"Connecting to MCP server '{server_name}'...")
    client = MultiServerMCPClient(connections)

    # 1) Load all tools from this MCP server
    # Each tool call will internally open a short-lived MCP session.
    tools: List[BaseTool] = await client.get_tools(server_name=server_name)

    # 2) Load the grounded QA prompt once (it's static text from your server)
    async with client.session(server_name) as session:
        prompt_messages = await load_mcp_prompt(
            session,
            name="grounded_qa_prompt",  # <- name from your @mcp.prompt()
        )

    # `prompt_messages` is a list of HumanMessage/AIMessage – flatten to a single string
    grounded_prompt = " ".join(msg.content for msg in prompt_messages)

    return tools, grounded_prompt


# -------------------------------------------------------------------
# Build the LangGraph ReAct agent wired to MCP
# -------------------------------------------------------------------


async def create_mcp_rag_agent(
    system_prompt: str,
    config: Config,
    checkpointer: Optional[Any] = None,
):
    """
    Returns a LangGraph compiled graph that:
    - Uses ChatOpenAI as the LLM
    - Can call MCP tools (e.g. `search_documents`)
    - Is guided by the `grounded_qa_prompt` from the MCP server
    - Persists conversation checkpoints when checkpointer is provided
    """
    logger.info("Creating MCP RAG agent...")
    config.validate_all()
    # Tools
    tools, grounded_prompt = await _load_mcp_tools_and_prompt(config)

    # System message
    full_system_prompt = system_prompt + "\n" + grounded_prompt
    system_prompt_template = SystemMessage(content=full_system_prompt)

    # LLM
    model = ChatOpenAI(
        api_key=config.model_api_key,
        model=config.text_model,
        **config.text_generation_kwargs,
    )

    # Prebuilt agent
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt_template,
        checkpointer=checkpointer,
    )

    return agent
