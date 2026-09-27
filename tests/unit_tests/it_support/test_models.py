"""Unit tests for IT Support domain data models (Phase 13-A).

Tests cover:
- ITCategory enum completeness and value correctness
- Priority enum completeness
- TicketStatus lifecycle state completeness
- ITIssue model creation, defaults, and validation
- Ticket model creation, defaults, and lifecycle state defaults
- SupportUser model creation and defaults
- Device model creation and defaults
- Field constraints (min_length, max_length, ge/le)
- UUID generation uniqueness for auto-generated IDs
- Datetime defaults are UTC-aware

All tests are purely offline — zero external dependencies, network calls, or
database connections. Suitable for CI/CD unit test suite.
"""

import re
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mcp_rag_agent.it_support.models import (
    Device,
    ITCategory,
    ITIssue,
    Priority,
    SupportUser,
    Ticket,
    TicketStatus,
)


# ---------------------------------------------------------------------------
# ITCategory Tests
# ---------------------------------------------------------------------------


class TestITCategory:
    """Tests for ITCategory enumeration."""

    def test_category_values_are_strings(self):
        """All category values must be lowercase strings."""
        for cat in ITCategory:
            assert isinstance(cat.value, str)
            assert cat.value == cat.value.lower()

    def test_critical_categories_exist(self):
        """Minimum required categories for a production IT copilot."""
        required = {
            ITCategory.HARDWARE_FAILURE,
            ITCategory.SOFTWARE_CRASH,
            ITCategory.NETWORK,
            ITCategory.VPN,
            ITCategory.EMAIL,
            ITCategory.SECURITY_INCIDENT,
            ITCategory.PASSWORD_RESET,
            ITCategory.ACCOUNT_LOCKOUT,
            ITCategory.MFA,
            ITCategory.ACCESS_REQUEST,
            ITCategory.PERMISSIONS,
            ITCategory.VIDEO_CONFERENCING,
            ITCategory.PRINTING,
            ITCategory.SERVICE_OUTAGE,
            ITCategory.PERFORMANCE,
            ITCategory.PHISHING,
            ITCategory.MALWARE,
            ITCategory.ONBOARDING,
            ITCategory.OFFBOARDING,
            ITCategory.POLICY_QUESTION,
            ITCategory.UNKNOWN,
        }
        for cat in required:
            assert cat in ITCategory

    def test_unknown_category_is_default_intent(self):
        """UNKNOWN must exist as the 'no match' fallback."""
        assert ITCategory.UNKNOWN.value == "unknown"

    def test_total_category_count_at_least_20(self):
        """We should have a sufficiently rich taxonomy for real IT support."""
        assert len(ITCategory) >= 20


# ---------------------------------------------------------------------------
# Priority Tests
# ---------------------------------------------------------------------------


class TestPriority:
    """Tests for Priority enumeration."""

    def test_four_priority_levels_exist(self):
        """ITIL defines P1–P4 mapped to CRITICAL/HIGH/MEDIUM/LOW."""
        assert Priority.CRITICAL.value == "critical"
        assert Priority.HIGH.value == "high"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.LOW.value == "low"
        assert len(Priority) == 4

    def test_priority_values_are_lowercase(self):
        for p in Priority:
            assert p.value == p.value.lower()


# ---------------------------------------------------------------------------
# TicketStatus Tests
# ---------------------------------------------------------------------------


class TestTicketStatus:
    """Tests for TicketStatus lifecycle state machine."""

    def test_all_required_states_exist(self):
        required = {
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.PENDING_USER,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
            TicketStatus.ESCALATED,
            TicketStatus.CANCELLED,
        }
        for status in required:
            assert status in TicketStatus

    def test_open_is_initial_state(self):
        """OPEN should be the natural initial state value."""
        assert TicketStatus.OPEN.value == "open"


# ---------------------------------------------------------------------------
# ITIssue Model Tests
# ---------------------------------------------------------------------------


class TestITIssue:
    """Tests for ITIssue data model."""

    def test_minimal_creation(self):
        """ITIssue can be created with only raw_description."""
        issue = ITIssue(raw_description="My laptop won't turn on.")
        assert issue.raw_description == "My laptop won't turn on."
        assert issue.category == ITCategory.UNKNOWN
        assert issue.priority == Priority.MEDIUM
        assert issue.intent_confidence == 0.0
        # Model default is 'unknown'; classify_issue() sets 'rule_based'
        assert issue.classification_method == "unknown"

    def test_auto_generated_issue_id(self):
        """issue_id must be auto-generated and follow the prefix convention."""
        issue = ITIssue(raw_description="VPN is not connecting.")
        assert issue.issue_id.startswith("issue_")
        assert len(issue.issue_id) == 18  # "issue_" (6) + 12 hex chars

    def test_unique_ids_per_instance(self):
        """Two ITIssue instances must not share the same issue_id."""
        a = ITIssue(raw_description="Issue A")
        b = ITIssue(raw_description="Issue B")
        assert a.issue_id != b.issue_id

    def test_full_creation(self):
        """Full-field ITIssue creation."""
        issue = ITIssue(
            raw_description="Outlook is crashing with error 0xC0000005",
            normalized_description="outlook is crashing with error 0xc0000005",
            category=ITCategory.EMAIL,
            subcategory="outlook_crash",
            priority=Priority.HIGH,
            affected_service="outlook",
            affected_device="LAPTOP-001",
            error_codes=["0xC0000005"],
            keywords=["outlook", "crash", "error"],
            intent_confidence=0.85,
            classification_method="rule_based",
            metadata={"os": "Windows 11"},
        )
        assert issue.category == ITCategory.EMAIL
        assert issue.priority == Priority.HIGH
        assert issue.affected_service == "outlook"
        assert issue.error_codes == ["0xC0000005"]
        assert issue.intent_confidence == 0.85

    def test_confidence_clipped_to_range(self):
        """intent_confidence must be in [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            ITIssue(raw_description="test", intent_confidence=1.5)
        with pytest.raises(ValidationError):
            ITIssue(raw_description="test", intent_confidence=-0.1)

    def test_raw_description_required(self):
        """raw_description is required."""
        with pytest.raises((ValidationError, TypeError)):
            ITIssue()  # type: ignore[call-arg]

    def test_created_at_is_utc_aware(self):
        """created_at must be timezone-aware (UTC)."""
        from datetime import timezone as tz
        issue = ITIssue(raw_description="Test issue")
        assert issue.created_at.tzinfo is not None
        assert issue.created_at.tzinfo == tz.utc

    def test_empty_description_min_length(self):
        """raw_description has min_length=1; classify_issue handles empty gracefully."""
        with pytest.raises(ValidationError):
            ITIssue(raw_description="")

    def test_metadata_defaults_to_empty_dict(self):
        issue = ITIssue(raw_description="Monitor flickering")
        assert isinstance(issue.metadata, dict)
        assert len(issue.metadata) == 0

    def test_error_codes_default_empty_list(self):
        issue = ITIssue(raw_description="Blue screen of death")
        assert isinstance(issue.error_codes, list)
        assert len(issue.error_codes) == 0


# ---------------------------------------------------------------------------
# Ticket Model Tests
# ---------------------------------------------------------------------------


class TestTicket:
    """Tests for Ticket data model."""

    def _make_ticket(self, **kwargs) -> Ticket:
        defaults = dict(
            title="VPN Not Connecting",
            description="Employee cannot connect to VPN from home.",
            category=ITCategory.VPN,
            priority=Priority.HIGH,
        )
        defaults.update(kwargs)
        return Ticket(**defaults)

    def test_minimal_creation(self):
        ticket = self._make_ticket()
        assert ticket.title == "VPN Not Connecting"
        assert ticket.category == ITCategory.VPN
        assert ticket.priority == Priority.HIGH
        assert ticket.status == TicketStatus.OPEN

    def test_auto_generated_ticket_id_format(self):
        """ticket_id must follow TKT-<8 hex uppercase> format."""
        ticket = self._make_ticket()
        assert re.match(r"^TKT-[0-9A-F]{8}$", ticket.ticket_id)

    def test_ticket_ids_are_unique(self):
        a = self._make_ticket()
        b = self._make_ticket()
        assert a.ticket_id != b.ticket_id

    def test_default_status_is_open(self):
        ticket = self._make_ticket()
        assert ticket.status == TicketStatus.OPEN

    def test_status_can_be_updated(self):
        ticket = self._make_ticket(status=TicketStatus.IN_PROGRESS)
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_created_at_is_utc_aware(self):
        ticket = self._make_ticket()
        assert ticket.created_at.tzinfo == timezone.utc

    def test_optional_fields_default_none(self):
        ticket = self._make_ticket()
        assert ticket.reporter_id is None
        assert ticket.assignee_id is None
        assert ticket.affected_device_id is None
        assert ticket.thread_id is None
        assert ticket.ai_summary is None
        assert ticket.resolution_notes is None
        assert ticket.resolved_at is None
        assert ticket.escalated_at is None

    def test_title_min_length(self):
        with pytest.raises(ValidationError):
            self._make_ticket(title="")

    def test_description_min_length(self):
        with pytest.raises(ValidationError):
            self._make_ticket(description="")

    def test_full_ticket_roundtrip(self):
        """Ticket can be serialized and deserialized via model_dump."""
        ticket = self._make_ticket(
            reporter_id="user_abc",
            reporter_name="Alice Smith",
            assignee_id="it_agent_1",
            thread_id="thread_xyz",
            ai_summary="Employee tried restarting VPN client, issue persisted.",
            tags=["vpn", "remote-work"],
        )
        data = ticket.model_dump()
        restored = Ticket(**data)
        assert restored.ticket_id == ticket.ticket_id
        assert restored.reporter_name == "Alice Smith"
        assert "vpn" in restored.tags


# ---------------------------------------------------------------------------
# SupportUser Model Tests
# ---------------------------------------------------------------------------


class TestSupportUser:
    """Tests for SupportUser data model."""

    def test_minimal_creation(self):
        user = SupportUser(user_id="u001", display_name="Bob Jones")
        assert user.user_id == "u001"
        assert user.display_name == "Bob Jones"
        assert user.role == "employee"
        assert user.device_ids == []
        assert user.active_ticket_ids == []

    def test_full_creation(self):
        user = SupportUser(
            user_id="u002",
            display_name="Carol White",
            email="carol@company.com",
            department="Engineering",
            location="London",
            role="it_support",
            device_ids=["dev_001", "dev_002"],
            active_ticket_ids=["TKT-AABB1234"],
        )
        assert user.email == "carol@company.com"
        assert user.role == "it_support"
        assert len(user.device_ids) == 2

    def test_user_id_required(self):
        with pytest.raises((ValidationError, TypeError)):
            SupportUser(display_name="No ID User")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Device Model Tests
# ---------------------------------------------------------------------------


class TestDevice:
    """Tests for Device data model."""

    def test_minimal_creation(self):
        device = Device(device_id="dev_001")
        assert device.device_id == "dev_001"
        assert device.device_type == "workstation"
        assert device.status == "active"
        assert device.hostname is None

    def test_full_creation(self):
        device = Device(
            device_id="dev_002",
            hostname="LAPTOP-IT-001",
            asset_tag="ASSET-4521",
            device_type="laptop",
            operating_system="Windows 11 23H2",
            assigned_user_id="u001",
            department="Finance",
            status="active",
            last_seen=datetime.now(timezone.utc),
        )
        assert device.hostname == "LAPTOP-IT-001"
        assert device.operating_system == "Windows 11 23H2"
        assert device.status == "active"

    def test_device_id_required(self):
        with pytest.raises((ValidationError, TypeError)):
            Device()  # type: ignore[call-arg]

    def test_last_seen_optional(self):
        device = Device(device_id="dev_003")
        assert device.last_seen is None
