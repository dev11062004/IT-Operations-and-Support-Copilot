"""Unit tests for Phase 13-F Admin Operations API and RBAC route protection."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_rag_agent.api import create_app
from mcp_rag_agent.api.dependencies import get_admin_service
from mcp_rag_agent.api.services.admin_service import AdminAPIService
from mcp_rag_agent.core.config import Config
from mcp_rag_agent.it_support.incidents.models import IncidentCreate, IncidentRecord
from mcp_rag_agent.it_support.incidents.service import IncidentService
from mcp_rag_agent.it_support.models import IncidentStatus, ITCategory, Priority
from mcp_rag_agent.it_support.tickets.models import TicketLifecycleStatus, TicketRecord
from mcp_rag_agent.it_support.tickets.service import TicketService
from mcp_rag_agent.security.audit import AuditEvent, AuditService, AuditStore
from mcp_rag_agent.security.rbac import RiskLevel, Role


class MemoryTicketStore:
    def __init__(self) -> None:
        self.records: dict[str, TicketRecord] = {}

    def create(self, ticket: TicketRecord) -> TicketRecord:
        self.records[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> TicketRecord:
        if ticket_id not in self.records:
            raise KeyError(ticket_id)
        return self.records[ticket_id]

    def list(self, filters: dict | None = None, limit: int = 100) -> list[TicketRecord]:
        results = list(self.records.values())
        if filters:
            if "status" in filters:
                results = [r for r in results if r.status.value == filters["status"]]
            if "priority" in filters:
                results = [
                    r for r in results if r.priority.value == filters["priority"]
                ]
            if "category" in filters:
                results = [
                    r for r in results if r.category.value == filters["category"]
                ]
        return results[:limit]

    def list_tickets(
        self, filters: dict | None = None, limit: int = 100
    ) -> list[TicketRecord]:
        return self.list(filters, limit)

    def find_unresolved_duplicate(self, ticket: TicketRecord) -> TicketRecord | None:
        return None

    def update_fields(self, ticket_id: str, fields: dict) -> TicketRecord:
        if ticket_id not in self.records:
            raise KeyError(ticket_id)
        payload = self.records[ticket_id].model_dump()
        payload.update(fields)
        self.records[ticket_id] = TicketRecord.model_validate(payload)
        return self.records[ticket_id]


class MemoryIncidentStore:
    def __init__(self) -> None:
        self.records: dict[str, IncidentRecord] = {}

    def create(self, incident: IncidentRecord) -> IncidentRecord:
        self.records[incident.incident_id] = incident
        return incident

    def get(self, incident_id: str) -> IncidentRecord:
        if incident_id not in self.records:
            raise KeyError(incident_id)
        return self.records[incident_id]

    def list_active(self, limit: int = 100) -> list[IncidentRecord]:
        return [
            r
            for r in self.records.values()
            if r.status
            in (
                IncidentStatus.INVESTIGATING,
                IncidentStatus.IDENTIFIED,
                IncidentStatus.MONITORING,
            )
        ][:limit]

    def list_all(self, limit: int = 100) -> list[IncidentRecord]:
        return list(self.records.values())[:limit]


@pytest.fixture
def test_setup():
    app = create_app(
        cfg=Config(ff_it_support=True), runner=MagicMock(checkpointer=None)
    )
    t_store = MemoryTicketStore()
    i_store = MemoryIncidentStore()
    a_store = AuditStore(mongo_client=None)

    t_service = TicketService(t_store)
    i_service = IncidentService(i_store)
    a_service = AuditService(a_store)

    # Seed ticket
    sample_ticket = TicketRecord(
        ticket_id="TKT-TEST-001",
        title="Cannot connect to VPN",
        description="Gateway timeout on vpn.corp.xyz",
        category=ITCategory.VPN,
        priority=Priority.HIGH,
        status=TicketLifecycleStatus.OPEN,
        requester_id="EMP-1001",
        assigned_team="Network Support",
    )
    t_store.create(sample_ticket)

    # Seed incident
    sample_incident = IncidentRecord(
        incident_id="INC-TEST-001",
        title="Global VPN Gateway Degraded",
        description="Packet loss on primary VPN gateway",
        service="VPN",
        severity=Priority.CRITICAL,
        status=IncidentStatus.INVESTIGATING,
        affected_users=150,
        workaround="Connect to secondary gateway vpn-backup.corp.xyz",
    )
    i_store.create(sample_incident)

    # Seed audit event
    sample_audit = AuditEvent(
        event_id="AUD-001",
        request_id="req-001",
        user_id="EMP-1001",
        role=Role.EMPLOYEE,
        action="search_policy_documents",
        resource_type="knowledge_document",
        resource_id="1 - Remote Working.txt",
        authorization_result="AUTHORIZED",
        risk_level=RiskLevel.LOW,
        status="success",
    )
    a_store.insert(sample_audit)

    admin_service = AdminAPIService(
        ticket_service=t_service,
        incident_service=i_service,
        audit_service=a_service,
    )
    app.dependency_overrides[get_admin_service] = lambda: admin_service
    client = TestClient(app)

    return client, t_store, i_store, a_store


def test_admin_tickets_rbac_protection(test_setup):
    """Verify employee cannot access admin tickets endpoint, but IT admin can."""
    client, _, _, _ = test_setup

    # 1. Employee access denied (403 Forbidden)
    res_emp = client.get(
        "/api/v1/admin/tickets",
        headers={"X-User-Role": "employee", "X-User-ID": "EMP-1001"},
    )
    assert res_emp.status_code == 403
    assert "PERMISSION_DENIED" in str(res_emp.json())

    # 2. IT Admin access granted (200 OK)
    res_admin = client.get(
        "/api/v1/admin/tickets",
        headers={"X-User-Role": "it_admin", "X-User-ID": "ADM-001"},
    )
    assert res_admin.status_code == 200
    tickets = res_admin.json()
    assert len(tickets) == 1
    assert tickets[0]["ticket_id"] == "TKT-TEST-001"


def test_admin_ticket_detail_endpoint(test_setup):
    """Verify admin ticket details endpoint for existing and nonexistent tickets."""
    client, _, _, _ = test_setup

    # Valid ticket
    res = client.get(
        "/api/v1/admin/tickets/TKT-TEST-001",
        headers={"X-User-Role": "it_admin", "X-User-ID": "ADM-001"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ticket_id"] == "TKT-TEST-001"
    assert data["category"] == "vpn"

    # Nonexistent ticket
    res_404 = client.get(
        "/api/v1/admin/tickets/TKT-NONEXISTENT",
        headers={"X-User-Role": "it_admin", "X-User-ID": "ADM-001"},
    )
    assert res_404.status_code == 404


def test_admin_incidents_rbac_and_data(test_setup):
    """Verify incidents endpoint security and returned records."""
    client, _, _, _ = test_setup

    # Employee forbidden
    res_emp = client.get(
        "/api/v1/admin/incidents",
        headers={"X-User-Role": "employee", "X-User-ID": "EMP-1001"},
    )
    assert res_emp.status_code == 403

    # System Admin allowed
    res_sys = client.get(
        "/api/v1/admin/incidents",
        headers={"X-User-Role": "system_admin", "X-User-ID": "SYS-001"},
    )
    assert res_sys.status_code == 200
    incidents = res_sys.json()
    assert len(incidents) == 1
    assert incidents[0]["incident_id"] == "INC-TEST-001"
    assert incidents[0]["severity"] == "critical"


def test_admin_metrics_endpoint(test_setup):
    """Verify operational KPIs aggregation endpoint."""
    client, _, _, _ = test_setup

    res = client.get(
        "/api/v1/admin/metrics",
        headers={"X-User-Role": "it_admin", "X-User-ID": "ADM-001"},
    )
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["open_tickets"] == 1
    assert metrics["critical_incidents"] == 1
    assert metrics["active_incidents"] == 1
    assert "VPN" in metrics["tickets_by_category"]
    assert "HIGH" in metrics["tickets_by_priority"]


def test_admin_evaluation_endpoint(test_setup):
    """Verify evaluation benchmark summary endpoint."""
    client, _, _, _ = test_setup

    res = client.get(
        "/api/v1/admin/evaluation",
        headers={"X-User-Role": "it_admin", "X-User-ID": "ADM-001"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["benchmark_name"] == "IT Operations & Support Benchmark"
    assert data["total_cases"] >= 100
    assert "intent_accuracy" in data
    assert "runbook_completion_rate" in data
    assert "rag_metrics" in data


def test_admin_audit_logs_rbac(test_setup):
    """Verify audit log viewing requires appropriate permission."""
    client, _, _, _ = test_setup

    # Employee forbidden
    res_emp = client.get(
        "/api/v1/admin/audit",
        headers={"X-User-Role": "employee", "X-User-ID": "EMP-1001"},
    )
    assert res_emp.status_code == 403

    # Security Analyst allowed
    res_sec = client.get(
        "/api/v1/admin/audit",
        headers={"X-User-Role": "security_analyst", "X-User-ID": "SEC-001"},
    )
    assert res_sec.status_code == 200
    logs = res_sec.json()
    assert len(logs) == 1
    assert logs[0]["event_id"] == "AUD-001"
    assert logs[0]["authorization_result"] == "AUTHORIZED"
