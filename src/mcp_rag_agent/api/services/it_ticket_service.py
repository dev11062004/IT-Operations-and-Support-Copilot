"""API-facing ticket service that keeps routes free of persistence logic."""

from mcp_rag_agent.it_support.tickets.models import TicketCreate, TicketOperationResult, TicketPatch, TicketRecord
from mcp_rag_agent.it_support.tickets.service import TicketService


class ITTicketAPIService:
    def __init__(self, ticket_service: TicketService) -> None:
        self._ticket_service = ticket_service

    def create(self, request: TicketCreate) -> TicketOperationResult:
        return self._ticket_service.create_ticket(request)

    def get(self, ticket_id: str) -> TicketRecord:
        return self._ticket_service.get_ticket(ticket_id)

    def patch(self, ticket_id: str, request: TicketPatch) -> TicketRecord:
        ticket = self.get(ticket_id)
        if request.status is not None:
            ticket = self._ticket_service.transition_status(ticket_id, request.status)
        if request.assigned_team is not None:
            ticket = self._ticket_service.assign_team(ticket_id, request.assigned_team)
        if request.priority is not None:
            ticket = self._ticket_service.update_fields(ticket_id, {"priority": request.priority.value})
        return ticket
