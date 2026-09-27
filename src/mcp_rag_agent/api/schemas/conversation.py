"""Pydantic schemas for /api/v1/conversations endpoints."""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    """Request model for creating a new isolated conversation thread."""

    user_id: Optional[str] = Field(
        default=None, description="Optional user identifier associated with the thread."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional arbitrary metadata (e.g. channel, client_version).",
    )


class ConversationThreadResponse(BaseModel):
    """Response model representing an active conversation thread."""

    thread_id: str = Field(..., description="Unique conversation session identifier.")
    user_id: Optional[str] = Field(
        default=None, description="User identifier if provided."
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC creation timestamp.",
    )
    status: str = Field(
        "active", description="Thread status: 'active', 'archived', 'deleted'."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Thread metadata."
    )


class ChatMessageItem(BaseModel):
    """Clean representation of a dialogue turn (Zero-CoT safe)."""

    role: str = Field(..., description="Speaker role: 'user' or 'assistant'.")
    content: str = Field(..., description="Text content of the message.")
    timestamp: Optional[str] = Field(
        default=None, description="Timestamp of the message if available."
    )


class ConversationHistoryResponse(BaseModel):
    """Response model containing conversation dialogue history."""

    thread_id: str = Field(..., description="Conversation thread identifier.")
    messages: list[ChatMessageItem] = Field(
        default_factory=list, description="List of dialogue turns."
    )
    total_messages: int = Field(0, description="Total number of dialogue turns.")


class DeleteConversationResponse(BaseModel):
    """Response model for conversation deletion."""

    thread_id: str = Field(..., description="Deleted conversation thread identifier.")
    deleted: bool = Field(
        True, description="Whether the thread was successfully purged."
    )
    message: str = Field(
        "Conversation thread deleted successfully.", description="Status message."
    )
