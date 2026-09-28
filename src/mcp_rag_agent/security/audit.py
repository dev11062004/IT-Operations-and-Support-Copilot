"""MongoDB-backed structured audit logging service for enterprise IT operations."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mcp_rag_agent.core.log_setup import mask_sensitive
from mcp_rag_agent.mongodb import MongoDBClient
from mcp_rag_agent.security.rbac import RiskLevel, Role


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_details(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask secrets and remove private credential fields."""
    sanitized: dict[str, Any] = {}
    for key, val in data.items():
        if key.lower() in (
            "password",
            "token",
            "secret",
            "api_key",
            "password_hash",
            "auth_token",
        ):
            sanitized[key] = "***REDACTED***"
        elif isinstance(val, str):
            sanitized[key] = mask_sensitive(val)
        elif isinstance(val, dict):
            sanitized[key] = _sanitize_details(val)
        elif isinstance(val, list):
            sanitized[key] = [
                (
                    mask_sensitive(item)
                    if isinstance(item, str)
                    else _sanitize_details(item) if isinstance(item, dict) else item
                )
                for item in val
            ]
        else:
            sanitized[key] = val
    return sanitized


class AuditEvent(BaseModel):
    """Pydantic model representing an immutable security audit event."""

    model_config = ConfigDict(str_strip_whitespace=True)

    event_id: str = Field(default_factory=lambda: f"AUD-{uuid4().hex[:10].upper()}")
    timestamp: datetime = Field(default_factory=_utc_now)
    request_id: str = Field(min_length=1, max_length=200)
    thread_id: Optional[str] = Field(default=None, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    role: Role = Field(default=Role.EMPLOYEE)
    action: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(default="system", max_length=100)
    resource_id: Optional[str] = Field(default=None, max_length=200)
    authorization_result: str = Field(default="AUTHORIZED", max_length=50)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    approval_id: Optional[str] = Field(default=None, max_length=200)
    status: str = Field(default="success", max_length=50)
    details: dict[str, Any] = Field(default_factory=dict)


class AuditStore:
    """Persistence store for security audit records."""

    def __init__(
        self,
        mongo_client: Optional[MongoDBClient] = None,
        collection_name: str = "it_audit_logs",
    ) -> None:
        self._mongo_client = mongo_client
        self._collection_name = collection_name
        self._in_memory_records: list[AuditEvent] = []

    @property
    def _collection(self) -> Any:
        if self._mongo_client is not None:
            return self._mongo_client.get_collection(self._collection_name)
        return None

    def insert(self, event: AuditEvent) -> AuditEvent:
        if self._collection is not None:
            self._collection.insert_one(event.model_dump(mode="json"))
        else:
            self._in_memory_records.append(event)
        return event

    def query(
        self,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        query_filter: dict[str, Any] = {}
        if user_id:
            query_filter["user_id"] = user_id
        if request_id:
            query_filter["request_id"] = request_id
        if thread_id:
            query_filter["thread_id"] = thread_id
        if action:
            query_filter["action"] = action
        if resource_type:
            query_filter["resource_type"] = resource_type

        time_filter: dict[str, Any] = {}
        if start_time:
            time_filter["$gte"] = start_time.isoformat()
        if end_time:
            time_filter["$lte"] = end_time.isoformat()
        if time_filter:
            query_filter["timestamp"] = time_filter

        if self._collection is not None:
            docs = (
                self._collection.find(query_filter).sort("timestamp", -1).limit(limit)
            )
            results = []
            for doc in docs:
                doc.pop("_id", None)
                results.append(AuditEvent.model_validate(doc))
            return results

        # In-memory filter
        filtered = self._in_memory_records
        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        if request_id:
            filtered = [e for e in filtered if e.request_id == request_id]
        if thread_id:
            filtered = [e for e in filtered if e.thread_id == thread_id]
        if action:
            filtered = [e for e in filtered if e.action == action]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]

        return sorted(filtered, key=lambda x: x.timestamp, reverse=True)[:limit]


class AuditService:
    """Domain service for capturing and querying immutable audit trails."""

    def __init__(self, store: Optional[AuditStore] = None) -> None:
        self._store = store or AuditStore()

    def log_event(
        self,
        user_id: str,
        role: Role,
        action: str,
        request_id: str,
        resource_type: str = "system",
        resource_id: Optional[str] = None,
        authorization_result: str = "AUTHORIZED",
        risk_level: RiskLevel = RiskLevel.LOW,
        approval_id: Optional[str] = None,
        status: str = "success",
        thread_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> AuditEvent:
        """Create and persist a sanitized audit event."""
        sanitized_details = _sanitize_details(details or {})
        event = AuditEvent(
            request_id=request_id,
            thread_id=thread_id,
            user_id=user_id,
            role=role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            authorization_result=authorization_result,
            risk_level=risk_level,
            approval_id=approval_id,
            status=status,
            details=sanitized_details,
        )
        return self._store.insert(event)

    def query_events(
        self,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query historical audit events."""
        return self._store.query(
            user_id=user_id,
            request_id=request_id,
            thread_id=thread_id,
            action=action,
            resource_type=resource_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
