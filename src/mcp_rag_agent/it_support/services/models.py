"""Service status domain models and typed schemas for IT operational monitoring."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ServiceOperationalStatus(str, Enum):
    """Operational status of a monitored synthetic enterprise service."""
    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    OUTAGE = "OUTAGE"
    UNKNOWN = "UNKNOWN"


class ServiceStatusRecord(BaseModel):
    """Pydantic model representing synthetic/demo operational status of an enterprise service."""

    model_config = ConfigDict(str_strip_whitespace=True)

    service_name: str = Field(min_length=1, max_length=200)
    status: ServiceOperationalStatus = ServiceOperationalStatus.OPERATIONAL
    last_updated: datetime = Field(default_factory=_utc_now)
    known_incident_id: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=1000)
    details: dict[str, Any] = Field(default_factory=dict)
