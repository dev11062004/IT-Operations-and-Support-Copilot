"""Typed, persistence-free contracts for the IT support domain."""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ITCategory(str, Enum):
    """Stable top-level taxonomy used by Phase 13-A classification."""

    NETWORK = "network"
    VPN = "vpn"
    WIFI = "wifi"
    DNS = "dns"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    ACCOUNT = "account"
    PASSWORD = "password"
    MFA = "mfa"
    ACCESS = "access"
    SECURITY = "security"
    SERVICE_OUTAGE = "service_outage"
    EMAIL = "email"
    COLLABORATION = "collaboration"
    DEVELOPER_TOOLS = "developer_tools"
    OTHER = "other"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class IncidentStatus(str, Enum):
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class ITIssue(BaseModel):
    """An employee-reported problem; it is not a persisted ticket."""

    model_config = ConfigDict(str_strip_whitespace=True)

    issue_id: str = Field(default_factory=lambda: f"issue_{uuid4().hex}")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    category: ITCategory = ITCategory.OTHER
    priority: Priority = Priority.MEDIUM
    user_id: str | None = Field(default=None, max_length=200)
    device_id: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=200)
    platform: str | None = Field(default=None, max_length=100)
    error_code: str | None = Field(default=None, max_length=100)
    status: TicketStatus = TicketStatus.OPEN
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class Ticket(BaseModel):
    """Foundational ticket shape. Persistence and lifecycle logic are future work."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ticket_id: str = Field(default_factory=lambda: f"TKT-{uuid4().hex[:8].upper()}")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    category: ITCategory
    priority: Priority = Priority.MEDIUM
    status: TicketStatus = TicketStatus.OPEN
    requester_id: str | None = Field(default=None, max_length=200)
    assigned_team: str | None = Field(default=None, max_length=200)
    conversation_id: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class Incident(BaseModel):
    """Foundational incident shape; this phase deliberately has no incident store."""

    model_config = ConfigDict(str_strip_whitespace=True)

    incident_id: str = Field(default_factory=lambda: f"INC-{uuid4().hex[:8].upper()}")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    service: str = Field(min_length=1, max_length=200)
    severity: Priority
    status: IncidentStatus = IncidentStatus.INVESTIGATING
    affected_users: int = Field(default=0, ge=0)
    start_time: datetime = Field(default_factory=_utc_now)
    end_time: datetime | None = None
    workaround: str | None = Field(default=None, max_length=4000)


class SupportUser(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    role: str = Field(default="employee", min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=320)


class Device(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_id: str = Field(min_length=1, max_length=200)
    user_id: str | None = Field(default=None, max_length=200)
    device_type: str = Field(min_length=1, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    os: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=100)
    hostname: str | None = Field(default=None, max_length=255)
    status: str = Field(default="active", min_length=1, max_length=100)


class ITEntities(BaseModel):
    """Simple, explainable entity extraction results for Phase 13-A."""

    product: str | None = None
    platform: str | None = None
    error_code: str | None = None
    device_type: str | None = None
    application: str | None = None


class ITIntentResult(BaseModel):
    """Safe classification output; ``reason`` is not model chain-of-thought."""

    intent: Literal["issue", "access_request", "security_report", "unknown"]
    category: ITCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=300)
    entities: ITEntities = Field(default_factory=ITEntities)
    classification_source: Literal["rule", "llm"]
