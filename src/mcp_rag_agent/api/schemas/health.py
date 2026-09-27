"""Pydantic schemas for health and readiness endpoints."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for liveness check (/api/v1/health)."""

    status: Literal["healthy"] = "healthy"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of the probe.",
    )
    app_name: str = Field("MCP RAG Agent", description="Application name.")
    app_version: str = Field("0.1.0", description="Application semantic version.")


class ReadinessDetails(BaseModel):
    """Component-level readiness diagnostic status."""

    database: Literal["connected", "degraded", "disconnected"] = Field(
        ..., description="MongoDB connection and index responsiveness."
    )
    model: Literal["configured", "unconfigured"] = Field(
        ..., description="Generative LLM API key status."
    )
    session_memory: Literal["active", "disabled"] = Field(
        ..., description="Conversation persistence state."
    )


class ReadinessResponse(BaseModel):
    """Response model for deep readiness probe (/api/v1/ready)."""

    status: Literal["ready", "not_ready"] = Field(
        ..., description="Aggregate readiness state."
    )
    checks: ReadinessDetails = Field(..., description="Component diagnostics.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of the probe.",
    )
