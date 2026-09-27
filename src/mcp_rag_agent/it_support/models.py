"""Core data models for the IT Operations & Support Copilot domain.

Defines strongly-typed Pydantic v2 schemas for all domain entities:
- ITCategory: Classification taxonomy for IT issues
- Priority: Severity/urgency levels
- TicketStatus: Ticket lifecycle state machine states
- ITIssue: Structured representation of a reported IT problem
- Ticket: Support ticket with lifecycle tracking
- SupportUser: Employee user profile for context-aware support
- Device: Managed enterprise device record

These models are the canonical data contracts across the it_support module
and the extended MCP tool layer (Phase 13-D).
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ITCategory(str, Enum):
    """Primary classification taxonomy for IT support issues.

    Derived from ITIL incident classification standards and common
    enterprise IT helpdesk category trees.
    """

    # Hardware
    HARDWARE_FAILURE = "hardware_failure"
    PERIPHERAL = "peripheral"
    MOBILE_DEVICE = "mobile_device"

    # Software
    SOFTWARE_CRASH = "software_crash"
    INSTALLATION = "installation"
    LICENSE = "license"

    # Connectivity
    NETWORK = "network"
    VPN = "vpn"
    WIFI = "wifi"
    EMAIL = "email"

    # Security
    SECURITY_INCIDENT = "security_incident"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_LOCKOUT = "account_lockout"
    PHISHING = "phishing"
    MALWARE = "malware"

    # Access & Identity
    ACCESS_REQUEST = "access_request"
    PERMISSIONS = "permissions"
    MFA = "mfa"

    # Communication & Collaboration
    VIDEO_CONFERENCING = "video_conferencing"
    MESSAGING = "messaging"
    PRINTING = "printing"

    # Policy & Compliance
    POLICY_QUESTION = "policy_question"
    COMPLIANCE = "compliance"

    # Service Degradation
    SERVICE_OUTAGE = "service_outage"
    PERFORMANCE = "performance"

    # Onboarding
    ONBOARDING = "onboarding"
    OFFBOARDING = "offboarding"

    # General / Unclassified
    OTHER = "other"
    UNKNOWN = "unknown"


class Priority(str, Enum):
    """Urgency/impact priority levels aligned with ITIL P1–P4.

    - CRITICAL (P1): Business-stopping, multiple users/systems affected
    - HIGH (P2): Significant business impact, workaround unavailable
    - MEDIUM (P3): Moderate impact, workaround available
    - LOW (P4): Minimal impact, cosmetic or informational
    """

    CRITICAL = "critical"  # P1: production down, security breach
    HIGH = "high"  # P2: major function impaired
    MEDIUM = "medium"  # P3: degraded, workaround exists
    LOW = "low"  # P4: cosmetic, question, enhancement


class TicketStatus(str, Enum):
    """IT support ticket lifecycle state machine.

    Transitions:
        OPEN → IN_PROGRESS → PENDING_USER / RESOLVED → CLOSED
        Any state → ESCALATED → IN_PROGRESS (re-assignment)
        Any state → CANCELLED
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class ITIssue(BaseModel):
    """Structured representation of a reported IT problem.

    Created during intent classification from the user's natural language
    description. Populated progressively as the agent gathers context.
    """

    issue_id: str = Field(
        default_factory=lambda: f"issue_{uuid.uuid4().hex[:12]}",
        description="Unique issue identifier (not a ticket until persisted)",
    )
    raw_description: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Original natural language description from the user",
    )
    normalized_description: str = Field(
        default="",
        description="Cleaned, normalized version of the description",
    )
    category: ITCategory = Field(
        default=ITCategory.UNKNOWN,
        description="Primary ITIL category classification",
    )
    subcategory: Optional[str] = Field(
        default=None,
        description="Optional finer-grained subcategory label",
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Inferred urgency/impact priority level",
    )
    affected_service: Optional[str] = Field(
        default=None,
        description="Name of the enterprise service or application affected",
    )
    affected_device: Optional[str] = Field(
        default=None,
        description="Hostname or asset tag of the affected device",
    )
    error_codes: list[str] = Field(
        default_factory=list,
        description="Error codes or exception messages extracted from the description",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Extracted diagnostic keywords from the issue description",
    )
    intent_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Classifier confidence score (0.0 = unknown, 1.0 = certain)",
    )
    classification_method: str = Field(
        default="unknown",
        description="Method used to classify: 'rule_based', 'llm', or 'hybrid'",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of issue creation",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context metadata (e.g. OS, browser, session info)",
    )


class Ticket(BaseModel):
    """IT support ticket with full lifecycle tracking.

    A ticket is a persisted work item created from an ITIssue when the
    user requests formal tracking (Phase 13-B adds MongoDB persistence).
    """

    ticket_id: str = Field(
        default_factory=lambda: f"TKT-{uuid.uuid4().hex[:8].upper()}",
        description="Human-readable unique ticket identifier (e.g. TKT-A3F2B1C9)",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short descriptive title for the ticket",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Full description of the reported issue",
    )
    category: ITCategory = Field(
        ...,
        description="ITIL category classification",
    )
    priority: Priority = Field(
        ...,
        description="Urgency/impact priority level",
    )
    status: TicketStatus = Field(
        default=TicketStatus.OPEN,
        description="Current lifecycle status",
    )
    reporter_id: Optional[str] = Field(
        default=None,
        description="User ID of the employee who reported the issue",
    )
    reporter_name: Optional[str] = Field(
        default=None,
        description="Display name of the reporter",
    )
    assignee_id: Optional[str] = Field(
        default=None,
        description="User ID of the assigned support engineer",
    )
    affected_device_id: Optional[str] = Field(
        default=None,
        description="Asset ID of the affected device (links to Device record)",
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Conversation thread ID that originated this ticket",
    )
    issue_id: Optional[str] = Field(
        default=None,
        description="Reference to the originating ITIssue",
    )
    ai_summary: Optional[str] = Field(
        default=None,
        description="AI-generated troubleshooting summary from the conversation",
    )
    resolution_notes: Optional[str] = Field(
        default=None,
        description="Resolution description (populated when status=RESOLVED)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC ticket creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last status update",
    )
    resolved_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when ticket was resolved",
    )
    escalated_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of escalation (if applicable)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags for filtering and grouping tickets",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured metadata (SLA fields, CMDB links, etc.)",
    )


class SupportUser(BaseModel):
    """Employee user profile for context-aware IT support.

    Populated from the existing MongoDB `users` collection (Phase 13-D
    extends this with live RBAC and device association lookup).
    """

    user_id: str = Field(..., description="Unique identifier for the employee")
    display_name: str = Field(..., description="Full display name")
    email: Optional[str] = Field(default=None, description="Corporate email address")
    department: Optional[str] = Field(
        default=None, description="Organizational department"
    )
    location: Optional[str] = Field(
        default=None, description="Office location or 'remote'"
    )
    role: str = Field(
        default="employee",
        description="RBAC role: 'employee', 'it_support', 'it_admin', 'manager'",
    )
    device_ids: list[str] = Field(
        default_factory=list,
        description="Asset IDs of devices assigned to this user",
    )
    active_ticket_ids: list[str] = Field(
        default_factory=list,
        description="IDs of open/in-progress tickets associated with this user",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional HR or directory metadata",
    )


class Device(BaseModel):
    """Managed enterprise device record from the CMDB (Configuration Management DB).

    Provides device context for accurate troubleshooting in the IT Support
    workflow. Full CMDB integration is planned for Phase 13-D.
    """

    device_id: str = Field(..., description="Unique asset identifier or hostname")
    hostname: Optional[str] = Field(default=None, description="Network hostname")
    asset_tag: Optional[str] = Field(
        default=None, description="Physical asset tag (barcode)"
    )
    device_type: str = Field(
        default="workstation",
        description="Device type: 'workstation', 'laptop', 'mobile', 'server', 'printer'",
    )
    operating_system: Optional[str] = Field(
        default=None, description="OS name and version (e.g. 'Windows 11 23H2')"
    )
    assigned_user_id: Optional[str] = Field(
        default=None, description="User ID of the primary assigned user"
    )
    department: Optional[str] = Field(
        default=None, description="Department owning this device"
    )
    status: str = Field(
        default="active",
        description="Device status: 'active', 'retired', 'lost', 'in_repair'",
    )
    last_seen: Optional[datetime] = Field(
        default=None, description="UTC timestamp of last network check-in"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional CMDB fields (warranty, purchase date, etc.)",
    )
