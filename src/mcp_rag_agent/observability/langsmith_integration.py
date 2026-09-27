"""LangSmith tracing configuration and metadata injection."""

import logging
import os
from typing import Any, Optional

from mcp_rag_agent.core.config import Config, config

logger = logging.getLogger("LangSmithIntegration")


def is_langsmith_enabled(cfg: Optional[Config] = None) -> bool:
    """Check if LangSmith tracing is actively enabled with a valid API key."""
    active_config = cfg or config
    return bool(active_config.langsmith_tracing and active_config.langsmith_api_key)


def configure_langsmith_environment(cfg: Optional[Config] = None) -> bool:
    """Set standard LangChain/LangSmith environment variables if enabled.

    Returns:
        bool: True if LangSmith is enabled and environment variables configured.
    """
    active_config = cfg or config
    if not is_langsmith_enabled(active_config):
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = active_config.langsmith_endpoint
    os.environ["LANGCHAIN_API_KEY"] = active_config.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = active_config.langsmith_project

    if active_config.langsmith_hide_inputs:
        os.environ["LANGCHAIN_HIDE_INPUTS"] = "true"
    if active_config.langsmith_hide_outputs:
        os.environ["LANGCHAIN_HIDE_OUTPUTS"] = "true"

    logger.info(
        f"[LANGSMITH] Tracing enabled for project '{active_config.langsmith_project}' "
        f"at endpoint '{active_config.langsmith_endpoint}'"
    )
    return True


def get_langchain_run_config(
    request_id: str,
    thread_id: str,
    user_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    cfg: Optional[Config] = None,
) -> dict[str, Any]:
    """Build LangChain execution config containing metadata, thread ID, and run tags.

    Args:
        request_id: Active request correlation ID.
        thread_id: Active session thread ID.
        user_id: Optional user identifier.
        tags: Optional extra tags to append to the trace.
        cfg: Optional application configuration.

    Returns:
        dict: Config dictionary compatible with LangGraph/LangChain runnable.ainvoke().
    """
    active_config = cfg or config

    # Base configurable parameters for LangGraph checkpointers
    configurable: dict[str, Any] = {"thread_id": thread_id}
    if user_id:
        configurable["user_id"] = user_id

    run_tags = ["production", "mcp-rag-agent"]
    if tags:
        run_tags.extend(tags)

    metadata: dict[str, Any] = {
        "request_id": request_id,
        "thread_id": thread_id,
        "app_name": active_config.app_name,
        "app_version": active_config.app_version,
    }
    if user_id:
        metadata["user_id"] = user_id

    run_config: dict[str, Any] = {
        "configurable": configurable,
        "metadata": metadata,
        "tags": run_tags,
        "run_name": f"rag_agent_{request_id[:8]}",
    }

    return run_config
