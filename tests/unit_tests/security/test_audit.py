"""Unit tests for MongoDB-backed structured audit logging and secret redaction."""

from datetime import datetime, timedelta, timezone

import pytest

from mcp_rag_agent.agent.models import GetUserContextInput
from mcp_rag_agent.mcp_server.tools import (
    get_user_context_typed,
    reset_it_services,
    set_audit_service,
    set_user_service,
)
from mcp_rag_agent.security.audit import (
    AuditEvent,
    AuditService,
    AuditStore,
    _sanitize_details,
)
from mcp_rag_agent.security.rbac import RiskLevel, Role, SecuritySubject


@pytest.fixture
def audit_service() -> AuditService:
    store = AuditStore(mongo_client=None)
    return AuditService(store=store)


def test_audit_event_model():
    """Verify AuditEvent structure and default properties."""
    event = AuditEvent(
        request_id="req-999",
        user_id="EMP-1001",
        role=Role.EMPLOYEE,
        action="search_policy_documents",
        resource_type="knowledge",
    )
    assert event.event_id.startswith("AUD-")
    assert event.timestamp is not None
    assert event.authorization_result == "AUTHORIZED"
    assert event.risk_level == RiskLevel.LOW


def test_audit_log_event_and_query(audit_service):
    """Test creating and querying audit events."""
    event = audit_service.log_event(
        user_id="EMP-1001",
        role=Role.EMPLOYEE,
        action="create_ticket",
        request_id="req-001",
        resource_type="ticket",
        resource_id="TCK-100",
        authorization_result="AUTHORIZED",
        risk_level=RiskLevel.MEDIUM,
        thread_id="th-session-1",
    )
    assert event.action == "create_ticket"
    assert event.resource_id == "TCK-100"

    # Query by user_id
    results = audit_service.query_events(user_id="EMP-1001")
    assert len(results) == 1
    assert results[0].request_id == "req-001"

    # Query by thread_id
    th_results = audit_service.query_events(thread_id="th-session-1")
    assert len(th_results) == 1

    # Query with non-matching filter
    empty_results = audit_service.query_events(user_id="EMP-9999")
    assert len(empty_results) == 0


def test_audit_details_secret_sanitization():
    """Test recursive redaction of sensitive credentials, API keys, passwords, and URIs."""
    raw_details = {
        "user_id": "EMP-1001",
        "password": "SuperSecretPassword123!",
        "api_key": "sk-proj-abcdef1234567890abcdef123456",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "nested": {
            "password_hash": "$2b$12$e8Yx9XJ9e...",
            "database_url": "mongodb://admin:secretPass@localhost:27017/admin",
            "safe_field": "public info",
        },
        "credentials_list": [
            {"secret": "hidden_key_123"},
            "Contact user at dev.support@corp.com",
        ],
    }

    sanitized = _sanitize_details(raw_details)

    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["token"] == "***REDACTED***"
    assert sanitized["nested"]["password_hash"] == "***REDACTED***"
    assert "secretPass" not in sanitized["nested"]["database_url"]
    assert (
        sanitized["nested"]["database_url"]
        == "mongodb://***REDACTED***@localhost:27017/admin"
    )
    assert sanitized["nested"]["safe_field"] == "public info"
    assert sanitized["credentials_list"][0]["secret"] == "***REDACTED***"
    assert "@REDACTED.COM" in sanitized["credentials_list"][1]


@pytest.mark.asyncio
async def test_tool_authorization_denial_emits_audit_log(audit_service):
    """Verify tool authorization rejection creates a DENIED audit record."""
    reset_it_services()
    set_audit_service(audit_service)

    # Employee attempting to access another user's context
    caller = SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)
    tool_input = GetUserContextInput(user_id="EMP-9999")

    out = await get_user_context_typed(tool_input, subject=caller)
    assert out.status == "error"
    assert out.error_code == "RESOURCE_ACCESS_DENIED"

    # Verify audit event was recorded
    audit_logs = audit_service.query_events(
        user_id="EMP-1001", action="get_user_context"
    )
    assert len(audit_logs) >= 1
    latest = audit_logs[0]
    assert latest.authorization_result == "DENIED"
    assert latest.resource_id == "EMP-9999"
    assert latest.details["reason"] == "RESOURCE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_tool_authorization_success_emits_audit_log(audit_service):
    """Verify authorized tool execution creates an AUTHORIZED audit record."""
    reset_it_services()
    set_audit_service(audit_service)

    from mcp_rag_agent.it_support.users.models import UserContextRecord
    from mcp_rag_agent.it_support.users.service import UserService

    class _MemUserStore:
        def __init__(self):
            self.records = {}

        def get(self, user_id):
            return self.records[user_id]

        def create(self, user):
            self.records[user.user_id] = user
            return user

    store = _MemUserStore()
    store.create(
        UserContextRecord(
            user_id="EMP-1001",
            name="Alice Smith",
            email="alice@company.com",
            role="Sales Representative",
            department="Sales",
        )
    )
    set_user_service(UserService(store))

    caller = SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)
    tool_input = GetUserContextInput(user_id="EMP-1001")

    out = await get_user_context_typed(tool_input, subject=caller)
    assert out.status == "success"
    assert out.user is not None

    # Verify audit event
    audit_logs = audit_service.query_events(
        user_id="EMP-1001", action="get_user_context"
    )
    assert len(audit_logs) >= 1
    latest = audit_logs[0]
    assert latest.authorization_result == "AUTHORIZED"
    assert latest.status == "success"
