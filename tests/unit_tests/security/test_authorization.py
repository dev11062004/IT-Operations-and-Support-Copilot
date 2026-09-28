"""Unit tests for AuthorizationService, resource-level security, tool execution, and retrieval filtering."""

from typing import Any

import pytest

from mcp_rag_agent.agent.models import RetrievedChunkOutput
from mcp_rag_agent.it_support.tickets.models import TicketRecord
from mcp_rag_agent.security.authorization import AuthorizationService
from mcp_rag_agent.security.rbac import Permission, Role, SecuritySubject


@pytest.fixture
def auth_service() -> AuthorizationService:
    return AuthorizationService()


@pytest.fixture
def employee_subject() -> SecuritySubject:
    return SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE, department="Sales")


@pytest.fixture
def other_employee_subject() -> SecuritySubject:
    return SecuritySubject(
        user_id="EMP-1002", role=Role.EMPLOYEE, department="Marketing"
    )


@pytest.fixture
def it_support_subject() -> SecuritySubject:
    return SecuritySubject(
        user_id="SUPP-2001", role=Role.IT_SUPPORT, department="IT Support"
    )


@pytest.fixture
def security_analyst_subject() -> SecuritySubject:
    return SecuritySubject(
        user_id="SEC-3001", role=Role.SECURITY_ANALYST, department="InfoSec"
    )


@pytest.fixture
def it_admin_subject() -> SecuritySubject:
    return SecuritySubject(
        user_id="ADM-4001", role=Role.IT_ADMIN, department="IT Operations"
    )


# ---------------------------------------------------------------------------
# 1. Role-Level Permission Checks
# ---------------------------------------------------------------------------


def test_can_check_role_permissions(auth_service, employee_subject, it_support_subject):
    """Test standard role-permission checks."""
    # Employee can search knowledge but cannot view audit logs
    decision_allow = auth_service.can(employee_subject, Permission.SEARCH_KNOWLEDGE)
    assert decision_allow.allowed is True
    assert decision_allow.reason_code == "AUTHORIZED"

    decision_deny = auth_service.can(employee_subject, Permission.VIEW_AUDIT_LOGS)
    assert decision_deny.allowed is False
    assert decision_deny.reason_code == "PERMISSION_DENIED"

    # IT Support can update tickets
    decision_support = auth_service.can(it_support_subject, Permission.UPDATE_TICKET)
    assert decision_support.allowed is True


def test_can_requires_valid_subject(auth_service):
    """Subject must be non-empty and authenticated."""
    decision = auth_service.can(None, Permission.SEARCH_KNOWLEDGE)
    assert decision.allowed is False
    assert decision.reason_code == "AUTHENTICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 2. Resource-Level Authorization: Tickets
# ---------------------------------------------------------------------------


def test_ticket_resource_authorization_employee_own_ticket(
    auth_service, employee_subject
):
    """Employees are authorized to access and comment on their own tickets."""
    own_ticket = {
        "ticket_id": "TCK-100",
        "requester_id": "EMP-1001",
        "title": "VPN issue",
    }
    dec_read = auth_service.can_access_ticket(
        employee_subject, own_ticket, action="read"
    )
    assert dec_read.allowed is True

    dec_comment = auth_service.can_access_ticket(
        employee_subject, own_ticket, action="comment"
    )
    assert dec_comment.allowed is True


def test_ticket_resource_authorization_cross_user_isolation(
    auth_service, employee_subject, other_employee_subject
):
    """Cross-user isolation: User A cannot read or modify User B's private ticket."""
    other_ticket = {
        "ticket_id": "TCK-200",
        "requester_id": "EMP-1002",
        "title": "Salary discrepancy",
    }

    dec_read = auth_service.can_access_ticket(
        employee_subject, other_ticket, action="read"
    )
    assert dec_read.allowed is False
    assert dec_read.reason_code == "RESOURCE_ACCESS_DENIED"

    dec_update = auth_service.can_access_ticket(
        employee_subject, other_ticket, action="update"
    )
    assert dec_update.allowed is False
    assert dec_update.reason_code == "RESOURCE_ACCESS_DENIED"


def test_ticket_resource_authorization_it_support_access(
    auth_service, it_support_subject
):
    """IT Support personnel can access tickets across users."""
    ticket = {
        "ticket_id": "TCK-200",
        "requester_id": "EMP-1002",
        "title": "Hardware broken",
    }
    dec = auth_service.can_access_ticket(it_support_subject, ticket, action="read")
    assert dec.allowed is True


# ---------------------------------------------------------------------------
# 3. Resource-Level Authorization: User & Device Context
# ---------------------------------------------------------------------------


def test_user_context_resource_authorization(
    auth_service, employee_subject, it_support_subject
):
    """Employee can only query own profile context; IT Support can query any profile."""
    # Own profile
    dec_own = auth_service.can_access_user(employee_subject, "EMP-1001")
    assert dec_own.allowed is True

    # Other employee's profile
    dec_other = auth_service.can_access_user(employee_subject, "EMP-1002")
    assert dec_other.allowed is False
    assert dec_other.reason_code == "RESOURCE_ACCESS_DENIED"

    # Support staff querying other user
    dec_support = auth_service.can_access_user(it_support_subject, "EMP-1002")
    assert dec_support.allowed is True


def test_device_context_resource_authorization(
    auth_service, employee_subject, it_support_subject
):
    """Employee can only inspect assigned device; IT Support can inspect any device."""
    own_device = {"device_id": "DEV-01", "user_id": "EMP-1001", "model": "MacBook Pro"}
    other_device = {"device_id": "DEV-02", "user_id": "EMP-1002", "model": "Dell XPS"}

    dec_own = auth_service.can_access_device(employee_subject, own_device)
    assert dec_own.allowed is True

    dec_other = auth_service.can_access_device(employee_subject, other_device)
    assert dec_other.allowed is False
    assert dec_other.reason_code == "RESOURCE_ACCESS_DENIED"

    dec_support = auth_service.can_access_device(it_support_subject, other_device)
    assert dec_support.allowed is True


# ---------------------------------------------------------------------------
# 4. Tool Execution Authorization
# ---------------------------------------------------------------------------


def test_can_execute_tool_search_policy(auth_service, employee_subject):
    """All authenticated enterprise roles can search knowledge."""
    dec = auth_service.can_execute_tool(
        employee_subject, "search_policy_documents", {"query": "wifi setup"}
    )
    assert dec.allowed is True


def test_can_execute_tool_get_user_context(
    auth_service, employee_subject, it_support_subject
):
    """Tool get_user_context enforces resource-level constraints."""
    dec_self = auth_service.can_execute_tool(
        employee_subject, "get_user_context", {"user_id": "EMP-1001"}
    )
    assert dec_self.allowed is True

    dec_foreign = auth_service.can_execute_tool(
        employee_subject, "get_user_context", {"user_id": "EMP-9999"}
    )
    assert dec_foreign.allowed is False
    assert dec_foreign.reason_code == "RESOURCE_ACCESS_DENIED"

    dec_supp = auth_service.can_execute_tool(
        it_support_subject, "get_user_context", {"user_id": "EMP-9999"}
    )
    assert dec_supp.allowed is True


def test_can_execute_tool_create_ticket(auth_service, employee_subject):
    """Employees can create tickets for themselves, but cannot spoof other requesters."""
    dec_own = auth_service.can_execute_tool(
        employee_subject,
        "create_ticket",
        {"requester_id": "EMP-1001", "title": "VPN help"},
    )
    assert dec_own.allowed is True

    dec_spoof = auth_service.can_execute_tool(
        employee_subject,
        "create_ticket",
        {"requester_id": "EMP-1002", "title": "Spoofed ticket"},
    )
    assert dec_spoof.allowed is False
    assert dec_spoof.reason_code == "RESOURCE_ACCESS_DENIED"


def test_can_execute_tool_unknown_tool(auth_service, employee_subject):
    """Execution of unmapped or arbitrary tools is strictly denied."""
    dec = auth_service.can_execute_tool(employee_subject, "execute_shell_command", {})
    assert dec.allowed is False
    assert dec.reason_code == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# 5. Pre-Retrieval Document Access-Level Filtering
# ---------------------------------------------------------------------------


def test_retrieval_document_access_filtering(
    auth_service,
    employee_subject,
    it_support_subject,
    security_analyst_subject,
    it_admin_subject,
):
    """Verify document chunks are filtered BEFORE synthesis based on role and metadata.access_level."""
    chunks = [
        RetrievedChunkOutput(
            chunk_id="chunk-1",
            document_id="doc-pub",
            document_name="Public Welcome Guide",
            content="Welcome to the company.",
            fusion_score=0.95,
            rank=1,
            metadata={"access_level": "public"},
        ),
        RetrievedChunkOutput(
            chunk_id="chunk-2",
            document_id="doc-int",
            document_name="Standard Employee Handbook",
            content="Standard office hours and holidays.",
            fusion_score=0.90,
            rank=2,
            metadata={"access_level": "internal"},
        ),
        RetrievedChunkOutput(
            chunk_id="chunk-3",
            document_id="doc-conf",
            document_name="IT Escalation Internal Runbook",
            content="Internal routing keys and escalation matrix.",
            fusion_score=0.88,
            rank=3,
            metadata={"access_level": "confidential"},
        ),
        RetrievedChunkOutput(
            chunk_id="chunk-4",
            document_id="doc-sec",
            document_name="SOC Incident Response Playbook",
            content="Handling active breach indicators.",
            fusion_score=0.85,
            rank=4,
            metadata={"access_level": "security_ops"},
        ),
        RetrievedChunkOutput(
            chunk_id="chunk-5",
            document_id="doc-adm",
            document_name="Infrastructure Root Keys Guide",
            content="Root administration rotation instructions.",
            fusion_score=0.80,
            rank=5,
            metadata={"access_level": "admin_only"},
        ),
    ]

    # 1. Employee: only sees 'public' and 'internal'
    emp_filtered = auth_service.filter_documents_for_subject(employee_subject, chunks)
    emp_ids = [c.chunk_id for c in emp_filtered]
    assert emp_ids == ["chunk-1", "chunk-2"]

    # 2. IT Support: sees 'public', 'internal', 'confidential'
    supp_filtered = auth_service.filter_documents_for_subject(
        it_support_subject, chunks
    )
    supp_ids = [c.chunk_id for c in supp_filtered]
    assert supp_ids == ["chunk-1", "chunk-2", "chunk-3"]

    # 3. Security Analyst: sees 'public', 'internal', 'confidential', 'security_ops'
    sec_filtered = auth_service.filter_documents_for_subject(
        security_analyst_subject, chunks
    )
    sec_ids = [c.chunk_id for c in sec_filtered]
    assert sec_ids == ["chunk-1", "chunk-2", "chunk-3", "chunk-4"]

    # 4. IT Admin: sees all
    adm_filtered = auth_service.filter_documents_for_subject(it_admin_subject, chunks)
    assert len(adm_filtered) == 5
