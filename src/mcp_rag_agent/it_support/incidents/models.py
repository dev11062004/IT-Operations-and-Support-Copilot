"""Persisted incident contracts and structured incident matching criteria."""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mcp_rag_agent.it_support.models import IncidentStatus, ITCategory, Priority


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    service: str = Field(min_length=1, max_length=200)
    severity: Priority
    product: str | None = Field(default=None, max_length=200)
    platform: str | None = Field(default=None, max_length=100)
    category: ITCategory | None = None
    error_code: str | None = Field(default=None, max_length=100)
    affected_users: int = Field(default=0, ge=0)
    workaround: str | None = Field(default=None, max_length=4000)


class IncidentRecord(IncidentCreate):
    incident_id: str = Field(default_factory=lambda: f"INC-{uuid4().hex[:10].upper()}")
    status: IncidentStatus = IncidentStatus.INVESTIGATING
    start_time: datetime = Field(default_factory=_utc_now)
    end_time: datetime | None = None
    updated_at: datetime = Field(default_factory=_utc_now)


class IncidentMatchCriteria(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    service: str = Field(min_length=1, max_length=200)
    product: str | None = None
    platform: str | None = None
    category: ITCategory | None = None
    error_code: str | None = None
