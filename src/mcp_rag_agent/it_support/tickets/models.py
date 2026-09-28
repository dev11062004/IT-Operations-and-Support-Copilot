"""Persisted ticket contracts and deterministic lifecycle definitions."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mcp_rag_agent.it_support.models import ITCategory, Priority


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketLifecycleStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


ALLOWED_TRANSITIONS: dict[TicketLifecycleStatus, set[TicketLifecycleStatus]] = {
    TicketLifecycleStatus.NEW: {TicketLifecycleStatus.OPEN},
    TicketLifecycleStatus.OPEN: {
        TicketLifecycleStatus.IN_PROGRESS,
        TicketLifecycleStatus.ESCALATED,
    },
    TicketLifecycleStatus.IN_PROGRESS: {
        TicketLifecycleStatus.WAITING_FOR_USER,
        TicketLifecycleStatus.RESOLVED,
        TicketLifecycleStatus.ESCALATED,
    },
    TicketLifecycleStatus.WAITING_FOR_USER: {TicketLifecycleStatus.IN_PROGRESS},
    TicketLifecycleStatus.RESOLVED: {TicketLifecycleStatus.CLOSED},
    TicketLifecycleStatus.CLOSED: set(),
    TicketLifecycleStatus.ESCALATED: set(),
}


class TicketComment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    comment_id: str = Field(default_factory=lambda: f"comment_{uuid4().hex}")
    author_id: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    created_at: datetime = Field(default_factory=_utc_now)


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    category: ITCategory
    priority: Priority = Priority.MEDIUM
    requester_id: str = Field(min_length=1, max_length=200)
    assigned_team: str | None = Field(default=None, max_length=200)
    conversation_id: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=200)
    platform: str | None = Field(default=None, max_length=100)
    error_code: str | None = Field(default=None, max_length=100)


class TicketRecord(TicketCreate):
    ticket_id: str = Field(default_factory=lambda: f"TKT-{uuid4().hex[:10].upper()}")
    status: TicketLifecycleStatus = TicketLifecycleStatus.NEW
    comments: list[TicketComment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class TicketPatch(BaseModel):
    """Only fields permitted by the ticket API; status uses a validated transition."""

    model_config = ConfigDict(str_strip_whitespace=True)
    status: TicketLifecycleStatus | None = None
    assigned_team: str | None = Field(default=None, max_length=200)
    priority: Priority | None = None


class TicketOperationResult(BaseModel):
    ticket: TicketRecord
    created: bool
    duplicate: bool = False
