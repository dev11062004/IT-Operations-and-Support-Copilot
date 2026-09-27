"""Application service for conversational chat execution with Zero-CoT guarantees."""

import logging
from typing import Any, Optional

from mcp_rag_agent.agent.create_agent import create_rag_agent_instance
from mcp_rag_agent.agent.models import AgentResponse
from mcp_rag_agent.agent.runner import RAGAgentRunner
from mcp_rag_agent.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatResponseMetadata,
    SourceDocument,
)
from mcp_rag_agent.core.config import Config, config

logger = logging.getLogger("ChatService")


class ChatService:
    """Application service orchestrating RAGAgentRunner and enforcing Zero-CoT API contracts."""

    def __init__(
        self,
        runner: Optional[RAGAgentRunner] = None,
        cfg: Optional[Config] = None,
        conversation_service: Optional[Any] = None,
    ):
        self._runner = runner
        self._config = cfg or config
        self._conversation_service = conversation_service

    async def get_runner(self) -> RAGAgentRunner:
        """Lazily initialize or return the shared RAGAgentRunner."""
        if self._runner is None:
            logger.info("Initializing RAGAgentRunner for ChatService...")
            self._runner = await create_rag_agent_instance(cfg=self._config)
        return self._runner

    def set_runner(self, runner: RAGAgentRunner) -> None:
        """Inject or override the RAGAgentRunner (useful for unit testing)."""
        self._runner = runner

    async def execute_chat(
        self,
        request: ChatRequest,
        request_id: Optional[str] = None,
    ) -> ChatResponse:
        """Execute chat request through the agent runner and map to Zero-CoT response.

        Args:
            request: Validated ChatRequest payload.
            request_id: Optional correlation ID (from middleware or client).

        Returns:
            ChatResponse containing grounded answer, citations, sources, and operational metadata.
        """
        runner = await self.get_runner()

        response: AgentResponse = await runner.run(
            query=request.message,
            thread_id=request.thread_id,
            request_id=request_id,
            user_id=request.user_id,
        )

        metadata = ChatResponseMetadata(
            retrieval_latency_ms=response.metadata.retrieval_latency_ms,
            total_latency_ms=response.metadata.total_latency_ms,
            model_latency_ms=response.metadata.model_latency_ms,
            model_name=response.metadata.model_name,
            decision=response.decision.value,
            token_usage=(
                response.metadata.token_usage.model_dump()
                if response.metadata.token_usage
                else None
            ),
        )

        # Transform retrieved chunks into structured sources for citation inspection
        sources: list[SourceDocument] = []
        raw_chunks = getattr(response.metadata, "retrieved_chunks", []) or []
        for chk in raw_chunks:
            sources.append(
                SourceDocument(
                    document_name=getattr(chk, "document_name", ""),
                    document_id=getattr(chk, "document_id", None),
                    chunk_id=getattr(chk, "chunk_id", None),
                    content=getattr(chk, "content", ""),
                    fusion_score=getattr(chk, "fusion_score", None),
                    rank=getattr(chk, "rank", None),
                    metadata=getattr(chk, "metadata", {}) or {},
                )
            )

        # Fallback: If no raw chunks but citations exist, create source records for each citation
        if not sources and response.metadata.citations:
            for idx, cite in enumerate(response.metadata.citations, start=1):
                sources.append(
                    SourceDocument(
                        document_name=cite,
                        rank=idx,
                    )
                )

        # Record thread in conversation service if available
        if self._conversation_service is not None and response.metadata.thread_id:
            tid = response.metadata.thread_id
            if tid not in getattr(self._conversation_service, "_threads", {}):
                from datetime import datetime, timezone

                now_iso = datetime.now(timezone.utc).isoformat()
                title_snip = (
                    (request.message[:45] + "...")
                    if len(request.message) > 45
                    else request.message
                )
                self._conversation_service._threads[tid] = {
                    "thread_id": tid,
                    "user_id": request.user_id,
                    "created_at": now_iso,
                    "status": "active",
                    "metadata": {"title": title_snip},
                }

        # Enforce Zero-CoT: Return only final answer, citations, sources, thread_id, request_id, and metadata.
        # Do not expose internal graph state, message turns, or tool arguments.
        return ChatResponse(
            answer=response.answer,
            citations=response.metadata.citations,
            sources=sources,
            thread_id=response.metadata.thread_id,
            request_id=response.metadata.request_id,
            metadata=metadata,
        )
