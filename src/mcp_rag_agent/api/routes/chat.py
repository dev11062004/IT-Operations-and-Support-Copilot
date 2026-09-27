"""Conversational RAG chat endpoint."""

import logging

from fastapi import APIRouter, Depends, Request, status

from mcp_rag_agent.api.dependencies import get_chat_service
from mcp_rag_agent.api.schemas.chat import ChatRequest, ChatResponse
from mcp_rag_agent.api.services.chat_service import ChatService

logger = logging.getLogger("ChatRoutes")

router = APIRouter(tags=["Conversational RAG"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Conversational RAG Query",
    description=(
        "Processes a natural language query through the RAG agent pipeline. "
        "Returns grounded answers with citations and latency metadata. "
        "Zero Chain-of-Thought guarantee: internal reasoning and tool calls are never exposed."
    ),
)
async def chat_endpoint(
    payload: ChatRequest,
    request: Request,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Delegates query execution to ChatService."""
    req_id = getattr(request.state, "request_id", None)
    return await chat_service.execute_chat(request=payload, request_id=req_id)
