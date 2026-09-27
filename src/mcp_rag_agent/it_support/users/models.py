"""User domain models and typed schemas for IT support operations."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class SupportTier(str, Enum):
    STANDARD = "standard"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    VIP = "vip"


class UserContextRecord(BaseModel):
    """Pydantic model representing an enterprise employee / support user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    department: str = Field(default="General", min_length=1, max_length=200)
    role: str = Field(default="Employee", min_length=1, max_length=100)
    support_tier: SupportTier = SupportTier.STANDARD
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
