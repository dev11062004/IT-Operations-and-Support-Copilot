import logging
from typing import Any, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from mcp_rag_agent.core.config import Config
from mcp_rag_agent.core.log_setup import setup_logging

setup_logging()
logger = logging.getLogger("Agent Creator")


async def create_rag_agent(
    system_prompt: str,
    tools: List[BaseTool],
    config: Config,
    checkpointer: Optional[Any] = None,
):
    """Returns a LangGraph compiled graph that:
    - Uses ChatOpenAI as the LLM
    - Can call LangChain tools (e.g. `search_policy_documents`)
    - Attaches persistent conversation checkpointer if provided
    """
    logger.info("Creating Direct RAG agent graph...")

    # System message
    system_prompt_template = SystemMessage(content=system_prompt)

    # LLM
    model = ChatOpenAI(
        api_key=config.model_api_key,
        model=config.text_model,
        **config.text_generation_kwargs,
    )

    # Prebuilt agent with checkpointer
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt_template,
        checkpointer=checkpointer,
        debug=config.debug,
    )

    return agent
