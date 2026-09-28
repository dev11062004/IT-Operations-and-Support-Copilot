"""Role-Based Access Control (RBAC) models, roles, permissions, and authoritative matrix."""

import contextvars
from contextlib import contextmanager
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    """Authoritative enterprise roles for IT Support Copilot."""

    EMPLOYEE = "employee"
    IT_SUPPORT = "it_support"
    IT_ADMIN = "it_admin"
    SECURITY_ANALYST = "security_analyst"
    SYSTEM_ADMIN = "system_admin"


class Permission(str, Enum):
    """Authoritative granular permissions."""

    SEARCH_KNOWLEDGE = "search_knowledge"
    VIEW_OWN_TICKETS = "view_own_tickets"
    VIEW_TICKET = "view_ticket"
    CREATE_TICKET = "create_ticket"
    UPDATE_TICKET = "update_ticket"
    ESCALATE_TICKET = "escalate_ticket"
    VIEW_INCIDENT = "view_incident"
    VIEW_SECURITY_INCIDENT = "view_security_incident"
    UPDATE_SECURITY_INCIDENT = "update_security_incident"
    VIEW_USER_CONTEXT = "view_user_context"
    VIEW_DEVICE_CONTEXT = "view_device_context"
    CHECK_SERVICE_STATUS = "check_service_status"
    MANAGE_TICKETS = "manage_tickets"
    MANAGE_INCIDENTS = "manage_incidents"
    MANAGE_KNOWLEDGE = "manage_knowledge"
    EXECUTE_HIGH_RISK_ACTION = "execute_high_risk_action"
    APPROVE_HIGH_RISK_ACTION = "approve_high_risk_action"
    VIEW_AUDIT_LOGS = "view_audit_logs"


class RiskLevel(str, Enum):
    """Action risk classifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecuritySubject(BaseModel):
    """Represents an authenticated caller/subject in the system."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=200)
    role: Role = Field(default=Role.EMPLOYEE)
    department: Optional[str] = Field(default=None, max_length=200)
    support_tier: Optional[str] = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Authoritative Role-to-Permissions Matrix
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.EMPLOYEE: {
        Permission.SEARCH_KNOWLEDGE,
        Permission.VIEW_OWN_TICKETS,
        Permission.CREATE_TICKET,
        Permission.VIEW_DEVICE_CONTEXT,
        Permission.CHECK_SERVICE_STATUS,
    },
    Role.IT_SUPPORT: {
        Permission.SEARCH_KNOWLEDGE,
        Permission.VIEW_OWN_TICKETS,
        Permission.VIEW_TICKET,
        Permission.CREATE_TICKET,
        Permission.UPDATE_TICKET,
        Permission.ESCALATE_TICKET,
        Permission.VIEW_INCIDENT,
        Permission.VIEW_USER_CONTEXT,
        Permission.VIEW_DEVICE_CONTEXT,
        Permission.CHECK_SERVICE_STATUS,
    },
    Role.SECURITY_ANALYST: {
        Permission.SEARCH_KNOWLEDGE,
        Permission.VIEW_OWN_TICKETS,
        Permission.VIEW_TICKET,
        Permission.CREATE_TICKET,
        Permission.UPDATE_TICKET,
        Permission.ESCALATE_TICKET,
        Permission.VIEW_INCIDENT,
        Permission.VIEW_SECURITY_INCIDENT,
        Permission.UPDATE_SECURITY_INCIDENT,
        Permission.VIEW_USER_CONTEXT,
        Permission.VIEW_DEVICE_CONTEXT,
        Permission.CHECK_SERVICE_STATUS,
        Permission.EXECUTE_HIGH_RISK_ACTION,
        Permission.VIEW_AUDIT_LOGS,
    },
    Role.IT_ADMIN: {
        Permission.SEARCH_KNOWLEDGE,
        Permission.VIEW_OWN_TICKETS,
        Permission.VIEW_TICKET,
        Permission.CREATE_TICKET,
        Permission.UPDATE_TICKET,
        Permission.ESCALATE_TICKET,
        Permission.VIEW_INCIDENT,
        Permission.VIEW_USER_CONTEXT,
        Permission.VIEW_DEVICE_CONTEXT,
        Permission.CHECK_SERVICE_STATUS,
        Permission.MANAGE_TICKETS,
        Permission.MANAGE_INCIDENTS,
        Permission.MANAGE_KNOWLEDGE,
        Permission.APPROVE_HIGH_RISK_ACTION,
        Permission.VIEW_AUDIT_LOGS,
    },
    Role.SYSTEM_ADMIN: {
        Permission.SEARCH_KNOWLEDGE,
        Permission.VIEW_OWN_TICKETS,
        Permission.VIEW_TICKET,
        Permission.CREATE_TICKET,
        Permission.UPDATE_TICKET,
        Permission.ESCALATE_TICKET,
        Permission.VIEW_INCIDENT,
        Permission.VIEW_SECURITY_INCIDENT,
        Permission.UPDATE_SECURITY_INCIDENT,
        Permission.VIEW_USER_CONTEXT,
        Permission.VIEW_DEVICE_CONTEXT,
        Permission.CHECK_SERVICE_STATUS,
        Permission.MANAGE_TICKETS,
        Permission.MANAGE_INCIDENTS,
        Permission.MANAGE_KNOWLEDGE,
        Permission.EXECUTE_HIGH_RISK_ACTION,
        Permission.APPROVE_HIGH_RISK_ACTION,
        Permission.VIEW_AUDIT_LOGS,
    },
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Check whether a given role has the requested permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: Role) -> set[Permission]:
    """Retrieve all granted permissions for a role."""
    return ROLE_PERMISSIONS.get(role, set()).copy()


# ---------------------------------------------------------------------------
# Contextvars request/execution subject tracking
# ---------------------------------------------------------------------------
_current_subject_ctx: contextvars.ContextVar[Optional[SecuritySubject]] = (
    contextvars.ContextVar("current_subject", default=None)
)


def get_current_subject() -> Optional[SecuritySubject]:
    """Retrieve the active SecuritySubject from contextvars if present."""
    return _current_subject_ctx.get()


def set_current_subject(subject: Optional[SecuritySubject]) -> None:
    """Set the active SecuritySubject in contextvars."""
    _current_subject_ctx.set(subject)


@contextmanager
def with_security_subject(subject: Optional[SecuritySubject]):
    """Context manager setting active security subject."""
    token = _current_subject_ctx.set(subject)
    try:
        yield subject
    finally:
        _current_subject_ctx.reset(token)
