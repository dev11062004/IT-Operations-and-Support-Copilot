"""Device domain models and typed schemas for IT support operations."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceRecord(BaseModel):
    """Pydantic model representing an enterprise device."""

    model_config = ConfigDict(str_strip_whitespace=True)

    device_id: str = Field(
        default_factory=lambda: f"DEV-{uuid4().hex[:8].upper()}",
        min_length=1,
        max_length=200,
    )
    user_id: str | None = Field(default=None, max_length=200)
    device_type: str = Field(default="laptop", min_length=1, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    os: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=100)
    hostname: str | None = Field(default=None, max_length=255)
    status: str = Field(default="active", min_length=1, max_length=100)
    vpn_client_version: str | None = Field(default=None, max_length=100)
    security_status: str = Field(default="compliant", min_length=1, max_length=100)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
