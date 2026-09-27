"""Init file for agent prompts."""

from mcp_rag_agent.agent.prompts.it_support_prompt import it_support_system_prompt
from mcp_rag_agent.agent.prompts.system_prompt import system_prompt

__all__ = ["system_prompt", "it_support_system_prompt"]
