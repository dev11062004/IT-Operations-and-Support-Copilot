"""Health and readiness diagnostic endpoints."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from pymongo import MongoClient

from mcp_rag_agent.api.dependencies import get_config
from mcp_rag_agent.api.schemas.health import (
    HealthResponse,
    ReadinessDetails,
    ReadinessResponse,
)
from mcp_rag_agent.core.config import Config

logger = logging.getLogger("HealthRoutes")

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health", response_model=HealthResponse, summary="Liveness Probe")
async def health_check() -> HealthResponse:
    """Fast, low-overhead liveness check confirming the HTTP service is running."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        app_name="MCP RAG Agent",
        app_version="0.1.0",
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness Probe")
async def readiness_check(
    response: Response,
    cfg: Config = Depends(get_config),
) -> ReadinessResponse:
    """Deep readiness probe verifying database connectivity and model configuration."""
    # 1. MongoDB check
    db_status = "disconnected"
    if cfg.db_url and cfg.db_name:
        try:

            def _ping_mongo() -> bool:
                client = MongoClient(
                    cfg.db_url,
                    serverSelectionTimeoutMS=1500,
                    connectTimeoutMS=1500,
                )
                client.admin.command("ping")
                return True

            is_connected = await asyncio.to_thread(_ping_mongo)
            if is_connected:
                db_status = "connected"
        except Exception as e:
            logger.debug(f"[READINESS] Database ping failed: {e}")
            db_status = "degraded" if cfg.ff_session_memory else "disconnected"
    else:
        db_status = "disconnected"

    # 2. Model configuration check
    has_model_key = bool(
        getattr(cfg, "model_api_key", None) or getattr(cfg, "google_api_key", None)
    )
    model_status = "configured" if has_model_key else "unconfigured"

    # 3. Session memory check
    memory_status = "active" if cfg.ff_session_memory else "disabled"

    checks = ReadinessDetails(
        database=db_status,
        model=model_status,
        session_memory=memory_status,
    )

    is_ready = (db_status in ("connected", "degraded")) and (
        model_status == "configured"
    )
    overall_status = "ready" if is_ready else "not_ready"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status=overall_status,
        checks=checks,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
