"""Unit tests for Human-in-the-Loop (HITL) approval workflows, risk classification, and store."""

from datetime import datetime, timedelta, timezone

import pytest

from mcp_rag_agent.security.approval import (
    ApprovalNotFoundError,
    ApprovalRequest,
    ApprovalService,
    ApprovalStatus,
    ApprovalStore,
    InvalidApprovalStateError,
    RiskPolicy,
)
from mcp_rag_agent.security.rbac import Permission, RiskLevel, Role, SecuritySubject


@pytest.fixture
def approval_service() -> ApprovalService:
    store = ApprovalStore(mongo_client=None)
    return ApprovalService(store=store)


@pytest.fixture
def requester_subject() -> SecuritySubject:
    return SecuritySubject(user_id="EMP-1001", role=Role.EMPLOYEE)


@pytest.fixture
def it_support_subject() -> SecuritySubject:
    return SecuritySubject(user_id="SUPP-2001", role=Role.IT_SUPPORT)


@pytest.fixture
def admin_subject() -> SecuritySubject:
    return SecuritySubject(user_id="ADM-9001", role=Role.IT_ADMIN)


# ---------------------------------------------------------------------------
# 1. Risk Classification & Policy
# ---------------------------------------------------------------------------


def test_risk_classification_tiers():
    """Verify deterministic risk classification."""
    assert RiskPolicy.classify_risk("search_policy_documents") == RiskLevel.LOW
    assert RiskPolicy.classify_risk("check_service_status") == RiskLevel.LOW
    assert RiskPolicy.classify_risk("create_ticket") == RiskLevel.MEDIUM
    assert RiskPolicy.classify_risk("update_ticket") == RiskLevel.MEDIUM
    assert RiskPolicy.classify_risk("password_reset") == RiskLevel.HIGH
    assert RiskPolicy.classify_risk("account_disable") == RiskLevel.HIGH
    assert RiskPolicy.classify_risk("privileged_access_change") == RiskLevel.HIGH


def test_is_approval_required_gate():
    """Verify approval gate decision based on risk level."""
    assert (
        RiskPolicy.is_approval_required(
            "search_knowledge", RiskLevel.LOW, Role.EMPLOYEE
        )
        is False
    )
    assert (
        RiskPolicy.is_approval_required(
            "create_ticket", RiskLevel.MEDIUM, Role.EMPLOYEE
        )
        is False
    )
    assert (
        RiskPolicy.is_approval_required(
            "credential_reset", RiskLevel.HIGH, Role.EMPLOYEE
        )
        is True
    )
    assert (
        RiskPolicy.is_approval_required(
            "revoke_access", RiskLevel.CRITICAL, Role.IT_SUPPORT
        )
        is True
    )


# ---------------------------------------------------------------------------
# 2. Approval Request Lifecycle
# ---------------------------------------------------------------------------


def test_request_approval_creation(approval_service):
    """Test creating a pending approval request."""
    req = approval_service.request_approval(
        user_id="EMP-1001",
        action="password_reset",
        reason="User forgot enterprise SSO password.",
        request_id="req-12345",
        resource="user:EMP-1001",
        risk_level=RiskLevel.HIGH,
    )
    assert req.approval_id.startswith("APP-")
    assert req.status == ApprovalStatus.PENDING
    assert req.user_id == "EMP-1001"
    assert req.action == "password_reset"
    assert req.risk_level == RiskLevel.HIGH

    # Retrieve from store
    fetched = approval_service.get_request(req.approval_id)
    assert fetched.approval_id == req.approval_id


def test_approval_by_authorized_admin(approval_service, admin_subject):
    """Test authorized human admin approval."""
    req = approval_service.request_approval(
        user_id="EMP-1001",
        action="account_unlock",
        reason="Account locked due to 3 failed attempts.",
        request_id="req-123",
    )
    approved_req = approval_service.approve(req.approval_id, approver=admin_subject)
    assert approved_req.status == ApprovalStatus.APPROVED
    assert approved_req.approved_by == admin_subject.user_id
    assert approved_req.approved_at is not None


def test_separation_of_duties_requester_cannot_approve_own_action(approval_service):
    """Separation of duties: An AI agent or requester cannot approve their own high-risk action."""
    # Even if requester has admin role, they cannot approve their own action request
    rogue_admin = SecuritySubject(user_id="ADM-777", role=Role.IT_ADMIN)
    req = approval_service.request_approval(
        user_id="ADM-777",
        action="privileged_access_change",
        reason="Need temporary root escalation.",
        request_id="req-priv",
    )
    with pytest.raises(PermissionError, match="Separation of duties violation"):
        approval_service.approve(req.approval_id, approver=rogue_admin)


def test_unauthorized_role_cannot_approve(approval_service, it_support_subject):
    """IT Support / Employee roles lack APPROVE_HIGH_RISK_ACTION permission."""
    req = approval_service.request_approval(
        user_id="EMP-1001",
        action="device_block",
        reason="Compromised laptop isolation.",
        request_id="req-sec",
    )
    with pytest.raises(PermissionError, match="does not have authority"):
        approval_service.approve(req.approval_id, approver=it_support_subject)


def test_reject_approval_request(approval_service, admin_subject):
    """Test admin rejection of approval request."""
    req = approval_service.request_approval(
        user_id="EMP-1001",
        action="account_disable",
        reason="Suspicious activity reported.",
        request_id="req-456",
    )
    rejected_req = approval_service.reject(
        req.approval_id, approver=admin_subject, reason="Activity verified as benign."
    )
    assert rejected_req.status == ApprovalStatus.REJECTED
    assert rejected_req.rejection_reason == "Activity verified as benign."


def test_execute_approved_action_workflow(approval_service, admin_subject):
    """Test full workflow: Request -> Approve -> Execute."""
    req = approval_service.request_approval(
        user_id="EMP-1001",
        action="credential_reset",
        reason="MFA token lost.",
        request_id="req-mfa",
    )
    approval_id = req.approval_id

    # Cannot execute while PENDING
    with pytest.raises(InvalidApprovalStateError, match="expected 'approved'"):
        approval_service.execute_approved_action(approval_id, executor=admin_subject)

    # Approve
    approval_service.approve(approval_id, approver=admin_subject)

    # Now execute
    res = approval_service.execute_approved_action(approval_id, executor=admin_subject)
    assert res is True

    # State is EXECUTED
    final_req = approval_service.get_request(approval_id)
    assert final_req.status == ApprovalStatus.EXECUTED
    assert final_req.executed_at is not None

    # Cannot execute twice
    with pytest.raises(InvalidApprovalStateError, match="expected 'approved'"):
        approval_service.execute_approved_action(approval_id, executor=admin_subject)


def test_expired_approval_cannot_be_approved_or_executed(
    approval_service, admin_subject
):
    """Expired requests cannot be approved or executed."""
    # Create request with past expiration
    req = ApprovalRequest(
        request_id="req-exp",
        user_id="EMP-1001",
        action="credential_reset",
        reason="Test expired",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    approval_service._store.create(req)

    with pytest.raises(InvalidApprovalStateError, match="expired"):
        approval_service.approve(req.approval_id, approver=admin_subject)

    updated = approval_service.get_request(req.approval_id)
    assert updated.status == ApprovalStatus.EXPIRED


def test_list_pending_requests(approval_service):
    """Test listing pending requests with and without user_id filter."""
    approval_service.request_approval(
        user_id="EMP-1001", action="action_1", reason="reason 1", request_id="r1"
    )
    approval_service.request_approval(
        user_id="EMP-1002", action="action_2", reason="reason 2", request_id="r2"
    )

    all_pending = approval_service.list_pending()
    assert len(all_pending) == 2

    user1_pending = approval_service.list_pending(user_id="EMP-1001")
    assert len(user1_pending) == 1
    assert user1_pending[0].user_id == "EMP-1001"
