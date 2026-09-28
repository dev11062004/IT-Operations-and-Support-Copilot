"""MongoDB persistence adapter for tickets; no connection ownership lives here."""

from datetime import datetime, timezone
from typing import Any

from mcp_rag_agent.it_support.tickets.models import (
    TicketComment,
    TicketLifecycleStatus,
    TicketRecord,
)
from mcp_rag_agent.mongodb import MongoDBClient


class TicketNotFoundError(KeyError):
    pass


class TicketStore:
    def __init__(
        self, mongo_client: MongoDBClient, collection_name: str = "it_tickets"
    ) -> None:
        self._mongo_client = mongo_client
        self._collection_name = collection_name

    @property
    def _collection(self) -> Any:
        return self._mongo_client.get_collection(self._collection_name)

    @staticmethod
    def _to_record(document: dict[str, Any] | None) -> TicketRecord:
        if document is None:
            raise TicketNotFoundError("Ticket not found")
        document.pop("_id", None)
        return TicketRecord.model_validate(document)

    def create(self, ticket: TicketRecord) -> TicketRecord:
        self._collection.insert_one(ticket.model_dump(mode="json"))
        return ticket

    def get(self, ticket_id: str) -> TicketRecord:
        return self._to_record(self._collection.find_one({"ticket_id": ticket_id}))

    def list(
        self, filters: dict[str, Any] | None = None, limit: int = 100
    ) -> list[TicketRecord]:
        return [
            self._to_record(item)
            for item in self._collection.find(filters or {}).limit(limit)
        ]

    def list_tickets(
        self, filters: dict[str, Any] | None = None, limit: int = 100
    ) -> list[TicketRecord]:
        return self.list(filters, limit)

    def find_unresolved_duplicate(self, ticket: TicketRecord) -> TicketRecord | None:
        query: dict[str, Any] = {
            "requester_id": ticket.requester_id,
            "status": {
                "$in": [
                    TicketLifecycleStatus.NEW.value,
                    TicketLifecycleStatus.OPEN.value,
                    TicketLifecycleStatus.IN_PROGRESS.value,
                    TicketLifecycleStatus.WAITING_FOR_USER.value,
                    TicketLifecycleStatus.ESCALATED.value,
                ]
            },
            "category": ticket.category.value,
            "title": ticket.title,
        }
        for key in ("product", "platform", "error_code"):
            value = getattr(ticket, key)
            if value:
                query[key] = value
        found = self._collection.find_one(query)
        return self._to_record(found) if found else None

    def update_fields(self, ticket_id: str, fields: dict[str, Any]) -> TicketRecord:
        payload = {**fields, "updated_at": datetime.now(timezone.utc).isoformat()}
        result = self._collection.update_one(
            {"ticket_id": ticket_id}, {"$set": payload}
        )
        if not result.matched_count:
            raise TicketNotFoundError(ticket_id)
        return self.get(ticket_id)

    def update(self, ticket_id: str, fields: dict[str, Any]) -> TicketRecord:
        return self.update_fields(ticket_id, fields)

    def update_status(
        self, ticket_id: str, status: TicketLifecycleStatus
    ) -> TicketRecord:
        return self.update_fields(ticket_id, {"status": status.value})

    def assign_team(self, ticket_id: str, team: str | None) -> TicketRecord:
        return self.update_fields(ticket_id, {"assigned_team": team})

    def add_comment(self, ticket_id: str, comment: TicketComment) -> TicketRecord:
        result = self._collection.update_one(
            {"ticket_id": ticket_id},
            {
                "$push": {"comments": comment.model_dump(mode="json")},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )
        if not result.matched_count:
            raise TicketNotFoundError(ticket_id)
        return self.get(ticket_id)
