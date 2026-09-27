"""Offline checks for Phase 13-A IT support contracts."""

import pytest
from pydantic import ValidationError

from mcp_rag_agent.it_support.models import (
    Device,
    Incident,
    ITCategory,
    ITIssue,
    IncidentStatus,
    Priority,
    SupportUser,
    Ticket,
    TicketStatus,
)


def test_issue_accepts_typed_optional_context() -> None:
    issue = ITIssue(title="VPN fails", description="VPN-ERR-742 on Windows", category=ITCategory.VPN, priority=Priority.HIGH, user_id="u-1", device_id="d-1", product="corporate VPN", platform="Windows", error_code="VPN-ERR-742")
    assert issue.status is TicketStatus.OPEN
    assert issue.error_code == "VPN-ERR-742"


@pytest.mark.parametrize("payload", [{"title": "", "description": "test"}, {"title": "test", "description": ""}, {"title": "test", "description": "test", "category": "not-a-category"}])
def test_issue_rejects_invalid_values(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ITIssue(**payload)


def test_ticket_has_foundational_fields_and_typed_status() -> None:
    ticket = Ticket(title="GitHub access", description="Need repository access", category=ITCategory.ACCESS, requester_id="u-1", assigned_team="identity", conversation_id="c-1")
    assert ticket.status is TicketStatus.OPEN
    assert ticket.ticket_id.startswith("TKT-")


def test_incident_has_typed_status_and_severity() -> None:
    incident = Incident(title="VPN outage", description="Remote workers cannot connect", service="corporate VPN", severity=Priority.CRITICAL, affected_users=42)
    assert incident.status is IncidentStatus.INVESTIGATING
    assert incident.affected_users == 42


def test_incident_rejects_invalid_enum_and_negative_affected_users() -> None:
    with pytest.raises(ValidationError):
        Incident(title="outage", description="details", service="VPN", severity="emergency")
    with pytest.raises(ValidationError):
        Incident(title="outage", description="details", service="VPN", severity=Priority.HIGH, affected_users=-1)


def test_required_fields_are_enforced() -> None:
    with pytest.raises(ValidationError):
        Ticket(title="missing required fields", description="details")
    with pytest.raises(ValidationError):
        SupportUser(user_id="u-1")
    with pytest.raises(ValidationError):
        Device(device_id="d-1")


def test_optional_user_and_device_fields_default_cleanly() -> None:
    user = SupportUser(user_id="u-1", name="Ada")
    device = Device(device_id="d-1", device_type="laptop")
    assert user.email is None
    assert device.os is None


def test_ids_and_timestamps_are_created_with_correct_types() -> None:
    issue = ITIssue(title="Network", description="Network unavailable")
    assert isinstance(issue.issue_id, str)
    assert issue.created_at.tzinfo is not None
