"""Ticket use cases, including duplicate detection and lifecycle enforcement."""

from mcp_rag_agent.it_support.tickets.models import ALLOWED_TRANSITIONS, TicketComment, TicketCreate, TicketLifecycleStatus, TicketOperationResult, TicketRecord
from mcp_rag_agent.it_support.tickets.store import TicketStore


class InvalidTicketTransitionError(ValueError):
    pass


class TicketService:
    def __init__(self, store: TicketStore) -> None:
        self._store = store

    def create_ticket(self, request: TicketCreate) -> TicketOperationResult:
        candidate = TicketRecord(**request.model_dump())
        duplicate = self._store.find_unresolved_duplicate(candidate)
        if duplicate:
            return TicketOperationResult(ticket=duplicate, created=False, duplicate=True)
        return TicketOperationResult(ticket=self._store.create(candidate), created=True)

    def get_ticket(self, ticket_id: str) -> TicketRecord:
        return self._store.get(ticket_id)

    def list_tickets(self, filters: dict | None = None) -> list[TicketRecord]:
        return self._store.list(filters)

    def transition_status(self, ticket_id: str, target: TicketLifecycleStatus) -> TicketRecord:
        current = self._store.get(ticket_id)
        if target not in ALLOWED_TRANSITIONS[current.status]:
            raise InvalidTicketTransitionError(f"Cannot transition ticket from {current.status.value} to {target.value}.")
        return self._store.update_fields(ticket_id, {"status": target.value})

    def assign_team(self, ticket_id: str, team: str | None) -> TicketRecord:
        return self._store.update_fields(ticket_id, {"assigned_team": team})

    def update_fields(self, ticket_id: str, fields: dict) -> TicketRecord:
        """Update non-lifecycle fields after the API schema has restricted them."""
        return self._store.update_fields(ticket_id, fields)

    def add_comment(self, ticket_id: str, comment: TicketComment) -> TicketRecord:
        return self._store.add_comment(ticket_id, comment)
