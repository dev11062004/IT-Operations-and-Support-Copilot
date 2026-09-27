"""Application service for managing conversation threads and session state."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage

from mcp_rag_agent.agent.runner import RAGAgentRunner
from mcp_rag_agent.api.schemas.conversation import (
    ChatMessageItem,
    ConversationHistoryResponse,
    ConversationThreadResponse,
    CreateConversationRequest,
    DeleteConversationResponse,
)
from mcp_rag_agent.core.config import Config, config

logger = logging.getLogger("ConversationService")


class ConversationService:
    """Orchestrates conversation thread lifecycles and dialogue history."""

    def __init__(
        self,
        runner: Optional[RAGAgentRunner] = None,
        checkpointer: Optional[Any] = None,
        cfg: Optional[Config] = None,
    ) -> None:
        self.runner = runner
        self.checkpointer = checkpointer or (runner.checkpointer if runner else None)
        self.config = cfg or config
        # Local registry of created threads and metadata
        self._threads: dict[str, dict[str, Any]] = {}

    def set_runner(self, runner: RAGAgentRunner) -> None:
        """Dynamically attach or update the agent runner."""
        self.runner = runner
        if not self.checkpointer and runner.checkpointer:
            self.checkpointer = runner.checkpointer

    async def create_thread(
        self, request: CreateConversationRequest
    ) -> ConversationThreadResponse:
        """Create a new isolated conversation thread with tracked metadata."""
        thread_id = f"thread_{uuid.uuid4().hex[:16]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        record = {
            "thread_id": thread_id,
            "user_id": request.user_id,
            "created_at": now_iso,
            "status": "active",
            "metadata": request.metadata,
        }
        self._threads[thread_id] = record
        logger.info(
            f"[CONVERSATION] Created thread: {thread_id} for user: {request.user_id}"
        )

        return ConversationThreadResponse(
            thread_id=thread_id,
            user_id=request.user_id,
            created_at=now_iso,
            status="active",
            metadata=request.metadata,
        )

    async def list_threads(self) -> list[ConversationThreadResponse]:
        """List all active conversation threads ordered by creation time descending."""
        results: list[ConversationThreadResponse] = []
        for record in reversed(list(self._threads.values())):
            results.append(
                ConversationThreadResponse(
                    thread_id=record["thread_id"],
                    user_id=record.get("user_id"),
                    created_at=record.get("created_at"),
                    status=record.get("status", "active"),
                    metadata=record.get("metadata", {}),
                )
            )
        return results

    async def get_history(self, thread_id: str) -> ConversationHistoryResponse:
        """Retrieve clean dialogue history for a thread, enforcing Zero-CoT output."""
        raw_messages: list[Any] = []

        # 1. Inspect agent graph state if runner is available
        if (
            self.runner
            and hasattr(self.runner, "agent_graph")
            and hasattr(self.runner.agent_graph, "aget_state")
        ):
            try:
                state = await self.runner.agent_graph.aget_state(
                    {"configurable": {"thread_id": thread_id}}
                )
                raw_messages = (
                    state.values.get("messages", [])
                    if state and hasattr(state, "values")
                    else []
                )
            except Exception as e:
                logger.warning(
                    f"[CONVERSATION] Could not fetch graph state for thread {thread_id}: {e}"
                )

        # 2. Fallback to checkpointer directly if state was empty
        if not raw_messages and self.checkpointer:
            try:
                if hasattr(self.checkpointer, "aget_tuple"):
                    tup = await self.checkpointer.aget_tuple(
                        {"configurable": {"thread_id": thread_id}}
                    )
                elif hasattr(self.checkpointer, "get_tuple"):
                    tup = await asyncio.to_thread(
                        self.checkpointer.get_tuple,
                        {"configurable": {"thread_id": thread_id}},
                    )
                else:
                    tup = None

                if (
                    tup
                    and hasattr(tup, "checkpoint")
                    and isinstance(tup.checkpoint, dict)
                ):
                    raw_messages = tup.checkpoint.get("channel_values", {}).get(
                        "messages", []
                    )
            except Exception as e:
                logger.warning(
                    f"[CONVERSATION] Could not fetch checkpointer tuple for thread {thread_id}: {e}"
                )

        # If not known in memory and has no messages in checkpointer, thread does not exist
        if not raw_messages and thread_id not in self._threads:
            logger.warning(f"[CONVERSATION] Thread not found: {thread_id}")
            raise KeyError(f"Conversation thread '{thread_id}' not found.")

        # 3. Filter dialogue turns (Zero-CoT safe: only HumanMessage and AIMessage; omit ToolMessages)
        dialogue: list[ChatMessageItem] = []
        for msg in raw_messages:
            if isinstance(msg, HumanMessage):
                dialogue.append(ChatMessageItem(role="user", content=str(msg.content)))
            elif isinstance(msg, AIMessage):
                # Omit empty tool-calling assistant messages or intermediate calls
                content_str = str(msg.content or "").strip()
                if content_str:
                    dialogue.append(
                        ChatMessageItem(role="assistant", content=content_str)
                    )

        return ConversationHistoryResponse(
            thread_id=thread_id,
            messages=dialogue,
            total_messages=len(dialogue),
        )

    async def delete_thread(self, thread_id: str) -> DeleteConversationResponse:
        """Purge thread state from checkpointer and active registry."""
        thread_exists = thread_id in self._threads

        # Check checkpointer presence
        cp = self.checkpointer or (self.runner.checkpointer if self.runner else None)
        if not thread_exists and cp:
            try:
                if hasattr(cp, "aget_tuple"):
                    tup = await cp.aget_tuple(
                        {"configurable": {"thread_id": thread_id}}
                    )
                elif hasattr(cp, "get_tuple"):
                    tup = await asyncio.to_thread(
                        cp.get_tuple, {"configurable": {"thread_id": thread_id}}
                    )
                else:
                    tup = None
                if tup is not None:
                    thread_exists = True
            except Exception:
                pass

        if not thread_exists:
            raise KeyError(f"Conversation thread '{thread_id}' not found.")

        # Remove from local registry
        self._threads.pop(thread_id, None)

        # Purge from checkpointer
        if cp:
            try:
                if hasattr(cp, "adelete_thread"):
                    await cp.adelete_thread(thread_id)
                elif hasattr(cp, "delete_thread"):
                    await asyncio.to_thread(cp.delete_thread, thread_id)
                logger.info(
                    f"[CONVERSATION] Purged checkpoints for thread: {thread_id}"
                )
            except Exception as e:
                logger.warning(
                    f"[CONVERSATION] Error purging checkpointer for {thread_id}: {e}"
                )

        return DeleteConversationResponse(
            thread_id=thread_id,
            deleted=True,
            message=f"Conversation thread '{thread_id}' deleted successfully.",
        )
