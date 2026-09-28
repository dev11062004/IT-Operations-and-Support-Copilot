"""HTTP contract tests for the IT ticket routes without a live MongoDB connection."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from mcp_rag_agent.api import create_app
from mcp_rag_agent.api.dependencies import get_it_ticket_service
from mcp_rag_agent.api.services.it_ticket_service import ITTicketAPIService
from mcp_rag_agent.core.config import Config
from mcp_rag_agent.it_support.models import ITCategory
from mcp_rag_agent.it_support.tickets.models import TicketLifecycleStatus, TicketRecord
from mcp_rag_agent.it_support.tickets.service import TicketService
from mcp_rag_agent.it_support.tickets.store import TicketNotFoundError


class MemoryTicketStore:
    def __init__(self) -> None:
        self.records: dict[str, TicketRecord] = {}

    def find_unresolved_duplicate(self, ticket: TicketRecord) -> TicketRecord | None:
        return next(
            (
                item
                for item in self.records.values()
                if item.requester_id == ticket.requester_id
                and item.category == ticket.category
                and item.title == ticket.title
                and item.status is not TicketLifecycleStatus.CLOSED
            ),
            None,
        )

    def create(self, ticket: TicketRecord) -> TicketRecord:
        self.records[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> TicketRecord:
        if ticket_id not in self.records:
            raise TicketNotFoundError(ticket_id)
        return self.records[ticket_id]

    def update_fields(self, ticket_id: str, fields: dict) -> TicketRecord:
        if ticket_id not in self.records:
            raise TicketNotFoundError(ticket_id)
        payload = self.records[ticket_id].model_dump()
        payload.update(fields)
        self.records[ticket_id] = TicketRecord.model_validate(payload)
        return self.records[ticket_id]

    def list(self, filters: dict | None = None) -> list[TicketRecord]:
        return list(self.records.values())


def _build_test_client(ff_enabled: bool = True):
    app = create_app(
        cfg=Config(ff_it_support=ff_enabled), runner=MagicMock(checkpointer=None)
    )
    store = MemoryTicketStore()
    service = ITTicketAPIService(TicketService(store))
    app.dependency_overrides[get_it_ticket_service] = lambda: service
    return TestClient(app), store


def test_ticket_routes_lifecycle_and_validation() -> None:
    client, _ = _build_test_client(ff_enabled=True)
    with client:
        payload = {
            "title": "VPN Outage",
            "description": "Cannot connect to VPN",
            "category": "vpn",
            "requester_id": "user-1",
        }
        created = client.post("/api/v1/it/tickets", json=payload)
        assert created.status_code == 201
        data = created.json()
        assert data["created"] is True
        assert data["duplicate"] is False
        ticket_id = data["ticket"]["ticket_id"]
        assert data["ticket"]["status"] == "new"

        # Duplicate submission returns 200 with duplicate=True and existing ticket
        duplicate = client.post("/api/v1/it/tickets", json=payload)
        assert duplicate.status_code == 200
        dup_data = duplicate.json()
        assert dup_data["created"] is False
        assert dup_data["duplicate"] is True
        assert dup_data["ticket"]["ticket_id"] == ticket_id

        # Retrieve ticket by ID
        get_res = client.get(f"/api/v1/it/tickets/{ticket_id}")
        assert get_res.status_code == 200
        assert get_res.json()["ticket_id"] == ticket_id

        # Valid PATCH: transition from new to open and set assigned team
        patch_res = client.patch(
            f"/api/v1/it/tickets/{ticket_id}",
            json={"status": "open", "assigned_team": "network-ops", "priority": "high"},
        )
        assert patch_res.status_code == 200
        patched_data = patch_res.json()
        assert patched_data["status"] == "open"
        assert patched_data["assigned_team"] == "network-ops"
        assert patched_data["priority"] == "high"

        # Invalid PATCH transition: open -> closed directly is rejected by lifecycle
        invalid_patch = client.patch(
            f"/api/v1/it/tickets/{ticket_id}", json={"status": "closed"}
        )
        assert invalid_patch.status_code == 422
        assert "Cannot transition ticket" in invalid_patch.json()["message"]

        # Non-existent ticket returns 404
        get_nonexistent = client.get("/api/v1/it/tickets/TKT-NONEXISTENT")
        assert get_nonexistent.status_code == 404
        assert "not found" in get_nonexistent.json()["message"]
        patch_nonexistent = client.patch(
            "/api/v1/it/tickets/TKT-NONEXISTENT", json={"status": "open"}
        )
        assert patch_nonexistent.status_code == 404
        assert "not found" in patch_nonexistent.json()["message"]

        # Schema validation error on missing required fields returns 422
        assert (
            client.post("/api/v1/it/tickets", json={"title": "missing"}).status_code
            == 422
        )


def test_ticket_routes_disabled_when_feature_flag_off() -> None:
    client, _ = _build_test_client(ff_enabled=False)
    with client:
        payload = {
            "title": "VPN",
            "description": "Cannot connect",
            "category": "vpn",
            "requester_id": "user-1",
        }
        post_res = client.post("/api/v1/it/tickets", json=payload)
        assert post_res.status_code == 404
        assert "IT support capability is disabled" in post_res.json()["message"]
        assert client.get("/api/v1/it/tickets/TKT-123").status_code == 404
        assert (
            client.patch(
                "/api/v1/it/tickets/TKT-123", json={"status": "open"}
            ).status_code
            == 404
        )
