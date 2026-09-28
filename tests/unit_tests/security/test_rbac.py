"""Unit tests for Role-Based Access Control (RBAC) definitions and permission matrix."""

import pytest
from pydantic import ValidationError

from mcp_rag_agent.security.rbac import (
    ROLE_PERMISSIONS,
    Permission,
    RiskLevel,
    Role,
    SecuritySubject,
    get_current_subject,
    get_role_permissions,
    has_permission,
    set_current_subject,
    with_security_subject,
)


def test_role_enum_values():
    """Verify all 5 enterprise roles are defined as strongly typed enums."""
    assert Role.EMPLOYEE.value == "employee"
    assert Role.IT_SUPPORT.value == "it_support"
    assert Role.IT_ADMIN.value == "it_admin"
    assert Role.SECURITY_ANALYST.value == "security_analyst"
    assert Role.SYSTEM_ADMIN.value == "system_admin"
    assert len(Role) == 5


def test_permission_enum_values():
    """Verify standard granular permissions are defined."""
    expected_permissions = {
        "search_knowledge",
        "view_own_tickets",
        "view_ticket",
        "create_ticket",
        "update_ticket",
        "escalate_ticket",
        "view_incident",
        "view_security_incident",
        "update_security_incident",
        "view_user_context",
        "view_device_context",
        "check_service_status",
        "manage_tickets",
        "manage_incidents",
        "manage_knowledge",
        "execute_high_risk_action",
        "approve_high_risk_action",
        "view_audit_logs",
    }
    actual_permissions = {p.value for p in Permission}
    assert expected_permissions.issubset(actual_permissions)


def test_risk_level_enum():
    """Verify risk classification tiers."""
    assert RiskLevel.LOW.value == "low"
    assert RiskLevel.MEDIUM.value == "medium"
    assert RiskLevel.HIGH.value == "high"
    assert RiskLevel.CRITICAL.value == "critical"


def test_employee_role_permissions():
    """Verify Employee role has minimal, least-privilege permissions."""
    perms = get_role_permissions(Role.EMPLOYEE)
    assert Permission.SEARCH_KNOWLEDGE in perms
    assert Permission.VIEW_OWN_TICKETS in perms
    assert Permission.CREATE_TICKET in perms
    assert Permission.VIEW_DEVICE_CONTEXT in perms
    assert Permission.CHECK_SERVICE_STATUS in perms

    # Employee must NOT have elevated support or admin capabilities
    assert Permission.VIEW_TICKET not in perms
    assert Permission.UPDATE_TICKET not in perms
    assert Permission.ESCALATE_TICKET not in perms
    assert Permission.VIEW_INCIDENT not in perms
    assert Permission.VIEW_SECURITY_INCIDENT not in perms
    assert Permission.MANAGE_TICKETS not in perms
    assert Permission.MANAGE_INCIDENTS not in perms
    assert Permission.APPROVE_HIGH_RISK_ACTION not in perms
    assert Permission.VIEW_AUDIT_LOGS not in perms


def test_it_support_role_permissions():
    """Verify IT Support role permissions."""
    perms = get_role_permissions(Role.IT_SUPPORT)
    assert Permission.SEARCH_KNOWLEDGE in perms
    assert Permission.VIEW_TICKET in perms
    assert Permission.CREATE_TICKET in perms
    assert Permission.UPDATE_TICKET in perms
    assert Permission.ESCALATE_TICKET in perms
    assert Permission.VIEW_INCIDENT in perms
    assert Permission.VIEW_USER_CONTEXT in perms
    assert Permission.VIEW_DEVICE_CONTEXT in perms
    assert Permission.CHECK_SERVICE_STATUS in perms

    # IT Support must NOT have security-restricted or administrative approval authority
    assert Permission.VIEW_SECURITY_INCIDENT not in perms
    assert Permission.MANAGE_KNOWLEDGE not in perms
    assert Permission.APPROVE_HIGH_RISK_ACTION not in perms
    assert Permission.VIEW_AUDIT_LOGS not in perms


def test_security_analyst_role_permissions():
    """Verify Security Analyst permissions."""
    perms = get_role_permissions(Role.SECURITY_ANALYST)
    assert Permission.SEARCH_KNOWLEDGE in perms
    assert Permission.VIEW_SECURITY_INCIDENT in perms
    assert Permission.UPDATE_SECURITY_INCIDENT in perms
    assert Permission.ESCALATE_TICKET in perms
    assert Permission.VIEW_USER_CONTEXT in perms
    assert Permission.VIEW_DEVICE_CONTEXT in perms
    assert Permission.EXECUTE_HIGH_RISK_ACTION in perms

    # Security Analyst must NOT approve actions without admin review
    assert Permission.APPROVE_HIGH_RISK_ACTION not in perms
    assert Permission.MANAGE_INCIDENTS not in perms


def test_it_admin_role_permissions():
    """Verify IT Admin permissions."""
    perms = get_role_permissions(Role.IT_ADMIN)
    assert Permission.MANAGE_TICKETS in perms
    assert Permission.MANAGE_INCIDENTS in perms
    assert Permission.MANAGE_KNOWLEDGE in perms
    assert Permission.APPROVE_HIGH_RISK_ACTION in perms
    assert Permission.VIEW_AUDIT_LOGS in perms


def test_system_admin_role_permissions():
    """Verify System Admin has full elevated operational permissions."""
    perms = get_role_permissions(Role.SYSTEM_ADMIN)
    assert Permission.MANAGE_TICKETS in perms
    assert Permission.MANAGE_INCIDENTS in perms
    assert Permission.MANAGE_KNOWLEDGE in perms
    assert Permission.EXECUTE_HIGH_RISK_ACTION in perms
    assert Permission.APPROVE_HIGH_RISK_ACTION in perms
    assert Permission.VIEW_AUDIT_LOGS in perms
    assert Permission.VIEW_SECURITY_INCIDENT in perms


def test_has_permission_helper():
    """Test helper function has_permission."""
    assert has_permission(Role.EMPLOYEE, Permission.SEARCH_KNOWLEDGE) is True
    assert has_permission(Role.EMPLOYEE, Permission.VIEW_AUDIT_LOGS) is False
    assert has_permission(Role.IT_ADMIN, Permission.APPROVE_HIGH_RISK_ACTION) is True
    assert has_permission(Role.IT_SUPPORT, Permission.APPROVE_HIGH_RISK_ACTION) is False


def test_get_role_permissions_is_copy():
    """Verify modifying returned permissions does not alter the master matrix."""
    perms = get_role_permissions(Role.EMPLOYEE)
    perms.add(Permission.APPROVE_HIGH_RISK_ACTION)
    assert Permission.APPROVE_HIGH_RISK_ACTION not in ROLE_PERMISSIONS[Role.EMPLOYEE]


def test_security_subject_validation():
    """Test SecuritySubject Pydantic validation."""
    sub = SecuritySubject(
        user_id="EMP-1001", role=Role.EMPLOYEE, department="Engineering"
    )
    assert sub.user_id == "EMP-1001"
    assert sub.role == Role.EMPLOYEE
    assert sub.department == "Engineering"

    # Empty user_id should fail
    with pytest.raises(ValidationError):
        SecuritySubject(user_id="", role=Role.EMPLOYEE)


def test_subject_contextvars_tracking():
    """Test setting and resetting security subject in execution context."""
    assert get_current_subject() is None

    subject_a = SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)
    with with_security_subject(subject_a):
        assert get_current_subject() == subject_a
        assert get_current_subject().user_id == "EMP-1001"

    # After context exit, context is restored
    assert get_current_subject() is None

    set_current_subject(subject_a)
    assert get_current_subject() == subject_a
    set_current_subject(None)
    assert get_current_subject() is None
