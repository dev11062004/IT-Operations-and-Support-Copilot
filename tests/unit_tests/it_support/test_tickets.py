"""Ticket store and lifecycle tests with mocked MongoDB."""

from unittest.mock import MagicMock

import pytest

from mcp_rag_agent.it_support.models import ITCategory
from mcp_rag_agent.it_support.tickets.models import (
    TicketCreate,
    TicketLifecycleStatus,
    TicketRecord,
)
from mcp_rag_agent.it_support.tickets.service import (
    InvalidTicketTransitionError,
    TicketService,
)
from mcp_rag_agent.it_support.tickets.store import TicketStore


def _request() -> TicketCreate:
    return TicketCreate(
        title="VPN unavailable",
        description="Cannot connect",
        category=ITCategory.VPN,
        requester_id="user-1",
        product="corporate VPN",
        platform="Windows",
    )


class MemoryTicketStore:
    def __init__(self) -> None:
        self.records: dict[str, TicketRecord] = {}

    def find_unresolved_duplicate(self, ticket: TicketRecord):
        return next(
            (
                item
                for item in self.records.values()
                if item.requester_id == ticket.requester_id
                and item.category == ticket.category
                and item.status is not TicketLifecycleStatus.CLOSED
            ),
            None,
        )

    def create(self, ticket: TicketRecord) -> TicketRecord:
        self.records[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> TicketRecord:
        return self.records[ticket_id]

    def update_fields(self, ticket_id: str, fields: dict) -> TicketRecord:
        payload = self.records[ticket_id].model_dump()
        payload.update(fields)
        self.records[ticket_id] = TicketRecord.model_validate(payload)
        return self.records[ticket_id]

    def list(self, filters=None):
        return list(self.records.values())


def test_create_and_duplicate_detection() -> None:
    service = TicketService(MemoryTicketStore())
    first = service.create_ticket(_request())
    duplicate = service.create_ticket(_request())
    assert first.created is True
    assert duplicate.created is False
    assert duplicate.duplicate is True
    assert duplicate.ticket.ticket_id == first.ticket.ticket_id


def test_lifecycle_allows_only_deterministic_transitions() -> None:
    service = TicketService(MemoryTicketStore())
    ticket = service.create_ticket(_request()).ticket
    for target in (
        TicketLifecycleStatus.OPEN,
        TicketLifecycleStatus.IN_PROGRESS,
        TicketLifecycleStatus.WAITING_FOR_USER,
        TicketLifecycleStatus.IN_PROGRESS,
        TicketLifecycleStatus.RESOLVED,
        TicketLifecycleStatus.CLOSED,
    ):
        ticket = service.transition_status(ticket.ticket_id, target)
    assert ticket.status is TicketLifecycleStatus.CLOSED


def test_invalid_lifecycle_transition_is_rejected() -> None:
    service = TicketService(MemoryTicketStore())
    ticket = service.create_ticket(_request()).ticket
    with pytest.raises(InvalidTicketTransitionError):
        service.transition_status(ticket.ticket_id, TicketLifecycleStatus.CLOSED)


def test_escalation_is_allowed_only_from_open_or_in_progress() -> None:
    service = TicketService(MemoryTicketStore())
    ticket = service.create_ticket(_request()).ticket
    ticket = service.transition_status(ticket.ticket_id, TicketLifecycleStatus.OPEN)
    assert (
        service.transition_status(
            ticket.ticket_id, TicketLifecycleStatus.ESCALATED
        ).status
        is TicketLifecycleStatus.ESCALATED
    )


def test_ticket_store_crud_uses_shared_mongodb_client() -> None:
    client = MagicMock()
    collection = client.get_collection.return_value
    record = TicketRecord(**_request().model_dump())
    collection.find_one.return_value = record.model_dump(mode="json")
    collection.update_one.return_value.matched_count = 1
    store = TicketStore(client)
    assert store.create(record).ticket_id == record.ticket_id
    assert store.get(record.ticket_id).ticket_id == record.ticket_id
    assert (
        store.update_fields(record.ticket_id, {"assigned_team": "network"}).ticket_id
        == record.ticket_id
    )


def test_mongodb_failure_is_not_silenced() -> None:
    client = MagicMock()
    client.get_collection.return_value.insert_one.side_effect = RuntimeError(
        "Mongo unavailable"
    )
    with pytest.raises(RuntimeError, match="Mongo unavailable"):
        TicketStore(client).create(TicketRecord(**_request().model_dump()))


def test_ticket_comments_and_service_methods() -> None:
    service = TicketService(MemoryTicketStore())
    created = service.create_ticket(_request()).ticket

    # Assign team
    assigned = service.assign_team(created.ticket_id, "DevOps")
    assert assigned.assigned_team == "DevOps"

    # Update fields
    updated = service.update_fields(created.ticket_id, {"priority": "critical"})
    assert updated.priority.value == "critical"

    # List tickets
    all_tickets = service.list_tickets()
    assert len(all_tickets) == 1
    assert all_tickets[0].ticket_id == created.ticket_id

    # Add comment via TicketStore with mock
    from mcp_rag_agent.it_support.tickets.models import TicketComment

    client = MagicMock()
    coll = client.get_collection.return_value
    coll.update_one.return_value.matched_count = 1
    record = TicketRecord(**_request().model_dump())
    coll.find_one.return_value = record.model_dump(mode="json")
    store = TicketStore(client)
    comment = TicketComment(author_id="admin-1", body="Investigating issue.")
    res = store.add_comment(record.ticket_id, comment)
    assert res.ticket_id == record.ticket_id


def test_ticket_store_queries_and_not_found_handling() -> None:
    from mcp_rag_agent.it_support.tickets.models import TicketComment
    from mcp_rag_agent.it_support.tickets.store import TicketNotFoundError

    client = MagicMock()
    coll = client.get_collection.return_value
    store = TicketStore(client)

    # find_unresolved_duplicate
    record = TicketRecord(**_request().model_dump())
    coll.find_one.return_value = record.model_dump(mode="json")
    found = store.find_unresolved_duplicate(record)
    assert found is not None
    assert found.ticket_id == record.ticket_id

    # list
    coll.find.return_value.limit.return_value = [record.model_dump(mode="json")]
    listed = store.list({"category": "vpn"})
    assert len(listed) == 1
    assert listed[0].ticket_id == record.ticket_id

    # Not found on get
    coll.find_one.return_value = None
    with pytest.raises(TicketNotFoundError):
        store.get("TKT-NONEXISTENT")

    # Not found on update_fields
    coll.update_one.return_value.matched_count = 0
    with pytest.raises(TicketNotFoundError):
        store.update_fields("TKT-NONEXISTENT", {"assigned_team": "team-a"})

    # Not found on add_comment
    with pytest.raises(TicketNotFoundError):
        store.add_comment(
            "TKT-NONEXISTENT", TicketComment(author_id="user-1", body="test")
        )
