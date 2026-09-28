"""Security regression tests for cross-user isolation, privilege escalation, and approval gating."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_rag_agent.agent.models import (
    GetDeviceInfoInput,
    GetUserContextInput,
    RetrievedChunkOutput,
    SearchDocumentsInput,
    UpdateTicketToolInput,
)
from mcp_rag_agent.it_support.devices.models import DeviceRecord
from mcp_rag_agent.it_support.devices.service import DeviceService
from mcp_rag_agent.it_support.tickets.models import (
    ITCategory,
    Priority,
    TicketCreate,
    TicketLifecycleStatus,
    TicketRecord,
)
from mcp_rag_agent.it_support.tickets.service import TicketService
from mcp_rag_agent.mcp_server.tools import (
    get_device_info_typed,
    get_user_context_typed,
    reset_it_services,
    search_policy_documents_typed,
    set_advanced_retriever,
    set_approval_service,
    set_audit_service,
    set_device_service,
    set_ticket_service,
    update_ticket_typed,
)
from mcp_rag_agent.retrieval.models import (
    RetrievalLatency,
    RetrievalResult,
    RetrievedChunk,
)
from mcp_rag_agent.security.approval import (
    ApprovalRequest,
    ApprovalService,
    ApprovalStatus,
    ApprovalStore,
    InvalidApprovalStateError,
    RiskPolicy,
)
from mcp_rag_agent.security.audit import AuditService, AuditStore
from mcp_rag_agent.security.authorization import AuthorizationService
from mcp_rag_agent.security.rbac import Permission, RiskLevel, Role, SecuritySubject


class MemoryTicketStore:
    """In-memory ticket store double for regression tests."""

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


class MemoryDeviceStore:
    """In-memory device store double for regression tests."""

    def __init__(self) -> None:
        self.records: dict[str, DeviceRecord] = {}

    def get(self, device_id: str) -> DeviceRecord:
        return self.records[device_id]

    def create(self, dev: DeviceRecord) -> DeviceRecord:
        self.records[dev.device_id] = dev
        return dev

    def list(self, filters=None, limit=100):
        return list(self.records.values())[:limit]

    def get_by_user(self, user_id: str) -> list[DeviceRecord]:
        return [d for d in self.records.values() if d.user_id == user_id]


@pytest.fixture(autouse=True)
def setup_security_environment():
    """Ensure clean services and memory stores for regression testing."""
    reset_it_services()
    audit_store = AuditStore(mongo_client=None)
    approval_store = ApprovalStore(mongo_client=None)
    set_audit_service(AuditService(audit_store))
    set_approval_service(ApprovalService(approval_store))
    yield
    reset_it_services()


# ---------------------------------------------------------------------------
# Regression Test 1: Cross-User Isolation (User A cannot access User B's ticket)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_user_ticket_isolation_regression():
    """User A (EMP-1001) attempting to access/update User B's (EMP-1002) ticket is DENIED."""
    ticket_store = MemoryTicketStore()
    ticket_service = TicketService(ticket_store)
    set_ticket_service(ticket_service)

    # User B creates a ticket
    t_created = ticket_service.create_ticket(
        TicketCreate(
            title="Private salary discussion ticket",
            description="Confidential HR question",
            category=ITCategory.OTHER,
            priority=Priority.MEDIUM,
            requester_id="EMP-1002",
        )
    ).ticket

    # User A (EMP-1001) attempts to update User B's ticket
    user_a = SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)
    tool_input = UpdateTicketToolInput(
        ticket_id=t_created.ticket_id,
        comment="Unauthorized snoop comment",
    )

    result = await update_ticket_typed(tool_input, subject=user_a)
    assert result.status == "error"
    assert result.error_code == "RESOURCE_ACCESS_DENIED"
    assert (
        "cannot modify tickets" in result.error_message
        or "Employees cannot modify" in result.error_message
    )


# ---------------------------------------------------------------------------
# Regression Test 2: Employee Privilege Escalation Prevention
# ---------------------------------------------------------------------------


def test_employee_attempting_admin_operations_denied():
    """Employee attempting admin-only operations is strictly DENIED."""
    auth_service = AuthorizationService()
    employee = SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)

    # 1. Manage tickets
    dec_tickets = auth_service.can(employee, Permission.MANAGE_TICKETS)
    assert dec_tickets.allowed is False
    assert dec_tickets.reason_code == "PERMISSION_DENIED"

    # 2. Manage incidents
    dec_incidents = auth_service.can(employee, Permission.MANAGE_INCIDENTS)
    assert dec_incidents.allowed is False
    assert dec_incidents.reason_code == "PERMISSION_DENIED"

    # 3. Approve high risk actions
    dec_approve = auth_service.can(employee, Permission.APPROVE_HIGH_RISK_ACTION)
    assert dec_approve.allowed is False
    assert dec_approve.reason_code == "PERMISSION_DENIED"

    # 4. View audit logs
    dec_audit = auth_service.can(employee, Permission.VIEW_AUDIT_LOGS)
    assert dec_audit.allowed is False
    assert dec_audit.reason_code == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# Regression Test 3: Unapproved High-Risk Action Execution is Blocked
# ---------------------------------------------------------------------------


def test_unapproved_high_risk_action_blocked():
    """An AI-proposed high-risk action with no prior human approval is strictly BLOCKED from execution."""
    approval_store = ApprovalStore(mongo_client=None)
    approval_svc = ApprovalService(approval_store)
    admin = SecuritySubject(user_id="ADM-9001", role=Role.IT_ADMIN)

    # 1. AI requests credential reset for compromised user
    req = approval_svc.request_approval(
        user_id="AI-AGENT",
        action="credential_reset",
        reason="Detected anomalous brute-force logins",
        request_id="req-sec-99",
        resource="user:EMP-1001",
        risk_level=RiskLevel.HIGH,
    )

    # 2. Attempting to execute immediately without human approval MUST fail
    with pytest.raises(InvalidApprovalStateError, match="expected 'approved'"):
        approval_svc.execute_approved_action(req.approval_id, executor=admin)

    # 3. Attempting to execute after rejection MUST fail
    approval_svc.reject(
        req.approval_id, approver=admin, reason="False positive confirmed"
    )
    with pytest.raises(InvalidApprovalStateError, match="expected 'approved'"):
        approval_svc.execute_approved_action(req.approval_id, executor=admin)


# ---------------------------------------------------------------------------
# Regression Test 4: Cross-User Device Access Blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_user_device_access_blocked():
    """Employee querying device assigned to another employee is DENIED."""
    dev_store = MemoryDeviceStore()
    dev_store.create(
        DeviceRecord(
            device_id="DEV-SECRET-01",
            user_id="EMP-1002",
            model="Executive Laptop",
            status="active",
        )
    )
    set_device_service(DeviceService(dev_store))

    user_a = SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)
    tool_input = GetDeviceInfoInput(device_id="DEV-SECRET-01")

    res = await get_device_info_typed(tool_input, subject=user_a)
    assert res.status == "error"
    assert res.error_code == "RESOURCE_ACCESS_DENIED"


# ---------------------------------------------------------------------------
# Regression Test 5: Confidential Security Playbook Filtered Before LLM Context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_confidential_security_docs_filtered_for_employee():
    """Confidential security ops docs are stripped BEFORE the LLM sees retrieval results."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=RetrievalResult(
            query="incident protocol",
            chunks=[
                RetrievedChunk(
                    chunk_id="chunk-pub",
                    document_id="doc-pub",
                    document_name="General FAQ",
                    content="Contact IT helpdesk for assistance.",
                    fusion_score=0.92,
                    rank=1,
                    metadata={"access_level": "public"},
                ),
                RetrievedChunk(
                    chunk_id="chunk-sec-ops",
                    document_id="doc-sec-ops",
                    document_name="SOC Secret Playbook",
                    content="Classified vulnerability remediation keys.",
                    fusion_score=0.91,
                    rank=2,
                    metadata={"access_level": "security_ops"},
                ),
            ],
            latency=RetrievalLatency(total_latency_ms=15.0),
        )
    )
    set_advanced_retriever(mock_retriever)

    employee = SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)
    tool_input = SearchDocumentsInput(query="incident protocol", top_k=2)

    res = await search_policy_documents_typed(tool_input, subject=employee)
    assert res.status == "success"
    assert len(res.chunks) == 1
    assert res.chunks[0].chunk_id == "chunk-pub"
    assert "chunk-sec-ops" not in [c.chunk_id for c in res.chunks]
    assert res.document_ids == ["doc-pub"]
