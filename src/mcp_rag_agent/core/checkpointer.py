"""Persistent conversation checkpointer for multi-turn session memory."""

import asyncio
import logging
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from mcp_rag_agent.core.config import Config, config
from mcp_rag_agent.mcp_server.tools import mask_sensitive

logger = logging.getLogger("Checkpointer")


def get_checkpointer(
    cfg: Optional[Config] = None, fallback_on_error: bool = True
) -> Optional[BaseCheckpointSaver]:
    """Factory to construct a conversation checkpointer according to configuration.

    - If FEATURE_FLAG_SESSION_MEMORY_ENABLED=false: returns None (stateless).
    - If enabled: connects to MongoDB Atlas and returns a MongoDBSaver.
    - If MongoDB connection or indexing fails: catches the exception, logs a warning
      (scrubbing credentials), and gracefully degrades to MemorySaver (or None).

    Args:
        cfg: Optional Config instance override.
        fallback_on_error: Whether to fall back to MemorySaver on database errors.

    Returns:
        BaseCheckpointSaver or None if session memory is disabled.
    """
    active_cfg = cfg or config

    # 1. Feature Flag Check
    if not active_cfg.ff_session_memory:
        logger.info(
            "[CHECKPOINTER] Session memory is disabled via FEATURE_FLAG_SESSION_MEMORY_ENABLED=false."
        )
        return None

    # 2. Database URL & Name Validation
    if not active_cfg.db_url or not active_cfg.db_name:
        logger.warning(
            "[CHECKPOINTER] Missing db_url or db_name in configuration. "
            "Gracefully degrading to in-memory checkpointer."
        )
        return MemorySaver() if fallback_on_error else None

    # 3. MongoDB Saver Initialization with Health Ping & Timeout
    try:
        safe_url = mask_sensitive(active_cfg.db_url)
        logger.debug(
            f"[CHECKPOINTER] Connecting to MongoDB for session checkpoints: {safe_url}"
        )

        client: MongoClient = MongoClient(
            active_cfg.db_url,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
        )

        # Health ping to ensure server is reachable before initializing saver indexes
        client.admin.command("ping")

        checkpointer = MongoDBSaver(
            client=client,
            db_name=active_cfg.db_name,
            checkpoint_collection_name=active_cfg.db_checkpoints_collection,
            writes_collection_name=active_cfg.db_checkpoint_writes_collection,
            ttl=active_cfg.session_memory_ttl_seconds,
        )

        logger.info(
            f"[CHECKPOINTER] Initialized MongoDBSaver on database '{active_cfg.db_name}' "
            f"collection '{active_cfg.db_checkpoints_collection}'."
        )
        return checkpointer

    except Exception as exc:
        safe_err = mask_sensitive(str(exc))
        logger.warning(
            f"[CHECKPOINTER] MongoDB connection failed: {safe_err}. "
            "Gracefully degrading to in-memory checkpointer (MemorySaver)."
        )
        if fallback_on_error:
            return MemorySaver()
        return None


async def get_checkpointer_async(
    cfg: Optional[Config] = None, fallback_on_error: bool = True
) -> Optional[BaseCheckpointSaver]:
    """Asynchronous wrapper to initialize checkpointer off the event loop thread."""
    return await asyncio.to_thread(get_checkpointer, cfg, fallback_on_error)
