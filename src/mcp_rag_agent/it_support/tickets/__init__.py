"""Ticket persistence and lifecycle domain."""

from .models import (
    TicketComment,
    TicketCreate,
    TicketLifecycleStatus,
    TicketOperationResult,
    TicketPatch,
    TicketRecord,
)
from .service import InvalidTicketTransitionError, TicketService
from .store import TicketNotFoundError, TicketStore

__all__ = [
    "TicketComment",
    "TicketCreate",
    "TicketLifecycleStatus",
    "TicketOperationResult",
    "TicketPatch",
    "TicketRecord",
    "TicketStore",
    "TicketNotFoundError",
    "TicketService",
    "InvalidTicketTransitionError",
]
