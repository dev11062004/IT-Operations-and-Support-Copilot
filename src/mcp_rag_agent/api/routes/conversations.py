"""Conversation session management endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, status

from mcp_rag_agent.api.dependencies import get_conversation_service
from mcp_rag_agent.api.schemas.conversation import (
    ConversationHistoryResponse,
    ConversationThreadResponse,
    CreateConversationRequest,
    DeleteConversationResponse,
)
from mcp_rag_agent.api.services.conversation_service import ConversationService

logger = logging.getLogger("ConversationRoutes")

router = APIRouter(tags=["Conversations"])


@router.post(
    "/conversations",
    response_model=ConversationThreadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversation Thread",
    description="Initializes a new isolated conversation session with persistent memory tracking.",
)
async def create_conversation(
    payload: CreateConversationRequest = CreateConversationRequest(),
    conv_service: ConversationService = Depends(get_conversation_service),
) -> ConversationThreadResponse:
    """Delegates thread creation to ConversationService."""
    return await conv_service.create_thread(payload)


@router.get(
    "/conversations",
    response_model=list[ConversationThreadResponse],
    status_code=status.HTTP_200_OK,
    summary="List Conversation Threads",
    description="Retrieves a list of active conversation threads for the session sidebar.",
)
async def list_conversations(
    conv_service: ConversationService = Depends(get_conversation_service),
) -> list[ConversationThreadResponse]:
    """Retrieves all tracked conversation threads."""
    return await conv_service.list_threads()


@router.get(
    "/conversations/{thread_id}",
    response_model=ConversationHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation History",
    description="Fetches clean, user-facing dialogue turns for a thread. Omits tool executions and chain-of-thought.",
)
async def get_conversation_history(
    thread_id: str = Path(..., description="Unique thread identifier"),
    conv_service: ConversationService = Depends(get_conversation_service),
) -> ConversationHistoryResponse:
    """Retrieves conversation history or raises 404 if not found."""
    try:
        return await conv_service.get_history(thread_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation thread '{thread_id}' not found.",
        )


@router.delete(
    "/conversations/{thread_id}",
    response_model=DeleteConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Conversation Thread",
    description="Purges conversation history and checkpoints for the specified thread.",
)
async def delete_conversation(
    thread_id: str = Path(..., description="Unique thread identifier to delete"),
    conv_service: ConversationService = Depends(get_conversation_service),
) -> DeleteConversationResponse:
    """Purges conversation checkpoints or raises 404 if not found."""
    try:
        return await conv_service.delete_thread(thread_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation thread '{thread_id}' not found.",
        )
