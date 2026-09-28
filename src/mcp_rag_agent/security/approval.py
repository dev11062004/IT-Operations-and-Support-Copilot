"""Human-in-the-Loop (HITL) approval models, risk policies, store, and approval service."""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mcp_rag_agent.mongodb import MongoDBClient
from mcp_rag_agent.security.rbac import (
    Permission,
    RiskLevel,
    Role,
    SecuritySubject,
    has_permission,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class ApprovalRequest(BaseModel):
    """Pydantic model representing an enterprise Human Approval request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    approval_id: str = Field(default_factory=lambda: f"APP-{uuid4().hex[:8].upper()}")
    request_id: str = Field(min_length=1, max_length=200)
    thread_id: Optional[str] = Field(default=None, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    resource: Optional[str] = Field(default=None, max_length=500)
    risk_level: RiskLevel = RiskLevel.HIGH
    reason: str = Field(min_length=1, max_length=1000)
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime = Field(
        default_factory=lambda: _utc_now() + timedelta(hours=24)
    )
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = Field(default=None, max_length=200)
    rejection_reason: Optional[str] = Field(default=None, max_length=1000)
    executed_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskPolicy:
    """Deterministic enterprise risk classification and approval gate policy."""

    HIGH_RISK_KEYWORDS = {
        "credential_reset",
        "password_reset",
        "account_disable",
        "account_unlock",
        "device_block",
        "access_revocation",
        "delete_resource",
        "privileged_access_change",
        "grant_admin",
        "revoke_admin",
    }

    MEDIUM_RISK_KEYWORDS = {
        "create_ticket",
        "update_ticket",
        "add_comment",
        "get_user_context",
        "assign_team",
        "escalate_ticket",
    }

    @classmethod
    def classify_risk(
        cls, action: str, params: Optional[dict[str, Any]] = None
    ) -> RiskLevel:
        """Classify operational action into risk tiers."""
        cleaned_action = action.lower().strip()
        for kw in cls.HIGH_RISK_KEYWORDS:
            if kw in cleaned_action:
                return RiskLevel.HIGH

        for kw in cls.MEDIUM_RISK_KEYWORDS:
            if kw in cleaned_action:
                return RiskLevel.MEDIUM

        return RiskLevel.LOW

    @classmethod
    def is_approval_required(
        cls, action: str, risk_level: RiskLevel, role: Role
    ) -> bool:
        """Determine if an action strictly requires human approval before execution."""
        # HIGH and CRITICAL risk actions ALWAYS require approval
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True
        return False


class ApprovalNotFoundError(KeyError):
    pass


class InvalidApprovalStateError(ValueError):
    pass


class ApprovalStore:
    """MongoDB persistence adapter for Human Approval requests."""

    def __init__(
        self,
        mongo_client: Optional[MongoDBClient] = None,
        collection_name: str = "it_approvals",
    ) -> None:
        self._mongo_client = mongo_client
        self._collection_name = collection_name
        self._in_memory_records: dict[str, ApprovalRequest] = {}

    @property
    def _collection(self) -> Any:
        if self._mongo_client is not None:
            return self._mongo_client.get_collection(self._collection_name)
        return None

    def create(self, request: ApprovalRequest) -> ApprovalRequest:
        if self._collection is not None:
            self._collection.insert_one(request.model_dump(mode="json"))
        else:
            self._in_memory_records[request.approval_id] = request
        return request

    def get(self, approval_id: str) -> ApprovalRequest:
        if self._collection is not None:
            doc = self._collection.find_one({"approval_id": approval_id})
            if not doc:
                raise ApprovalNotFoundError(
                    f"Approval request '{approval_id}' not found."
                )
            doc.pop("_id", None)
            return ApprovalRequest.model_validate(doc)

        if approval_id not in self._in_memory_records:
            raise ApprovalNotFoundError(f"Approval request '{approval_id}' not found.")
        return self._in_memory_records[approval_id]

    def update(self, request: ApprovalRequest) -> ApprovalRequest:
        if self._collection is not None:
            payload = request.model_dump(mode="json")
            result = self._collection.update_one(
                {"approval_id": request.approval_id}, {"$set": payload}
            )
            if not result.matched_count:
                raise ApprovalNotFoundError(request.approval_id)
        else:
            self._in_memory_records[request.approval_id] = request
        return request

    def list_pending(self, user_id: Optional[str] = None) -> list[ApprovalRequest]:
        query: dict[str, Any] = {"status": ApprovalStatus.PENDING.value}
        if user_id:
            query["user_id"] = user_id

        if self._collection is not None:
            docs = self._collection.find(query)
            results = []
            for doc in docs:
                doc.pop("_id", None)
                results.append(ApprovalRequest.model_validate(doc))
            return results

        return [
            req
            for req in self._in_memory_records.values()
            if req.status == ApprovalStatus.PENDING
            and (not user_id or req.user_id == user_id)
        ]


class ApprovalService:
    """Domain service managing human-in-the-loop approval workflows."""

    def __init__(self, store: Optional[ApprovalStore] = None) -> None:
        self._store = store or ApprovalStore()

    def request_approval(
        self,
        user_id: str,
        action: str,
        reason: str,
        request_id: str,
        resource: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        thread_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ApprovalRequest:
        """Create a new human approval request for a high-risk operation."""
        calculated_risk = risk_level or RiskPolicy.classify_risk(action)
        req = ApprovalRequest(
            request_id=request_id,
            thread_id=thread_id,
            user_id=user_id,
            action=action,
            resource=resource,
            risk_level=calculated_risk,
            reason=reason,
            status=ApprovalStatus.PENDING,
            metadata=metadata or {},
        )
        return self._store.create(req)

    def get_request(self, approval_id: str) -> ApprovalRequest:
        """Retrieve an existing approval request."""
        return self._store.get(approval_id)

    def approve(self, approval_id: str, approver: SecuritySubject) -> ApprovalRequest:
        """Approve a pending request by an authorized human administrator.

        Enforces:
        - Approver must have Permission.APPROVE_HIGH_RISK_ACTION.
        - Requester cannot approve their own action (Separation of duties).
        - Request must be in PENDING state and not expired.
        """
        if not approver or not approver.user_id:
            raise ValueError("Approver identity is required.")

        if not has_permission(approver.role, Permission.APPROVE_HIGH_RISK_ACTION):
            raise PermissionError(
                f"Role '{approver.role.value}' does not have authority to approve high-risk actions."
            )

        req = self._store.get(approval_id)

        # Separation of duties: AI / user cannot approve own request
        if req.user_id == approver.user_id:
            raise PermissionError(
                "Separation of duties violation: Requester cannot approve their own action request."
            )

        now = _utc_now()
        if req.expires_at < now:
            req.status = ApprovalStatus.EXPIRED
            self._store.update(req)
            raise InvalidApprovalStateError("This approval request has expired.")

        if req.status != ApprovalStatus.PENDING:
            raise InvalidApprovalStateError(
                f"Cannot approve request in '{req.status.value}' state."
            )

        req.status = ApprovalStatus.APPROVED
        req.approved_at = now
        req.approved_by = approver.user_id
        return self._store.update(req)

    def reject(
        self, approval_id: str, approver: SecuritySubject, reason: str
    ) -> ApprovalRequest:
        """Reject a pending request."""
        if not approver or not approver.user_id:
            raise ValueError("Approver identity is required.")

        if not has_permission(approver.role, Permission.APPROVE_HIGH_RISK_ACTION):
            raise PermissionError(
                f"Role '{approver.role.value}' does not have authority to reject/review actions."
            )

        req = self._store.get(approval_id)
        if req.status != ApprovalStatus.PENDING:
            raise InvalidApprovalStateError(
                f"Cannot reject request in '{req.status.value}' state."
            )

        req.status = ApprovalStatus.REJECTED
        req.rejection_reason = reason
        req.approved_at = _utc_now()
        req.approved_by = approver.user_id
        return self._store.update(req)

    def execute_approved_action(
        self, approval_id: str, executor: SecuritySubject
    ) -> bool:
        """Verify approved status and transition to EXECUTED upon operation execution."""
        req = self._store.get(approval_id)
        now = _utc_now()

        if req.expires_at < now:
            req.status = ApprovalStatus.EXPIRED
            self._store.update(req)
            raise InvalidApprovalStateError(
                "Approval request has expired and cannot be executed."
            )

        if req.status != ApprovalStatus.APPROVED:
            raise InvalidApprovalStateError(
                f"Cannot execute action: request status is '{req.status.value}', expected 'approved'."
            )

        req.status = ApprovalStatus.EXECUTED
        req.executed_at = now
        self._store.update(req)
        return True

    def list_pending(self, user_id: Optional[str] = None) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        return self._store.list_pending(user_id=user_id)
